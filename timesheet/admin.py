import calendar
from django.contrib import admin
from django.http import HttpResponse
from openpyxl import Workbook
from openpyxl.styles import Font, Alignment, Border, Side, PatternFill
from openpyxl.utils import get_column_letter
from openpyxl.cell.cell import MergedCell
from datetime import timedelta, date
from collections import defaultdict
from .models import TimesheetEntry, TradeAllocation

# 1. Action for Bulk Approval
@admin.action(description="Approve Selected Timesheets")
def approve_timesheets(modeladmin, request, queryset):
    queryset.update(status='APPROVED')
    modeladmin.message_user(request, "Selected timesheets have been approved.")


@admin.action(description="Export Semi-Monthly Payroll with Side-Panel Matrix")
def export_to_excel(modeladmin, request, queryset):
    if not queryset.exists():
        modeladmin.message_user(request, "No records selected.", level='warning')
        return

    # 1. Period Detection (1-15 or 16-End)
    latest_entry_date = queryset.order_by('-date_worked').first().date_worked
    year, month = latest_entry_date.year, latest_entry_date.month
    if latest_entry_date.day <= 15:
        start_date, end_date = date(year, month, 1), date(year, month, 15)
    else:
        start_date = date(year, month, 16)
        end_date = date(year, month, calendar.monthrange(year, month)[1])

    wb = Workbook()
    wb.remove(wb.active)

    # Styles
    bold_font = Font(bold=True)
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="F97316", end_color="F97316", fill_type="solid")
    stripe_fill = PatternFill(start_color="F2F2F2", end_color="F2F2F2", fill_type="solid")
    center_aligned = Alignment(horizontal="center", vertical="center")
    left_aligned = Alignment(horizontal="left", vertical="center")
    thin_border = Border(left=Side(style='thin'), right=Side(style='thin'),
                         top=Side(style='thin'), bottom=Side(style='thin'))

    data_by_user = defaultdict(list)
    period_queryset = queryset.filter(date_worked__range=(start_date, end_date)).order_by('date_worked')
    for entry in period_queryset:
        data_by_user[entry.user].append(entry)

    for user, entries in data_by_user.items():
        ws = wb.create_sheet(title=str(user.username)[:31])

        # --- Layout Setup ---
        ws.row_dimensions[1].height = 15
        ws.column_dimensions['A'].width = 3.00
        ws.column_dimensions['J'].width = 3.00
        ws.column_dimensions['K'].width = 3.00

        # --- Header Section ---
        ws.merge_cells('B2:H2')
        ws['B2'] = "Empyreal Painting & Construction"
        ws['B2'].font = Font(size=14, bold=True)
        ws.merge_cells('B3:H3')
        ws['B3'] = '"Built on trust, focused on quality."'
        ws['B3'].font = Font(size=11, italic=True)

        ws['B5'], ws['C5'] = "Employee Name:", f"{user.first_name} {user.last_name}"

        # Updated Pay Period Label and Range
        ws['B6'] = "Pay Period:"
        ws.merge_cells('C6:D6')
        ws['C6'] = f"{start_date.strftime('%m/%d/%Y')} - {end_date.strftime('%m/%d/%Y')}"

        ws['B5'].font = ws['B6'].font = bold_font
        ws['C6'].alignment = left_aligned

        # --- Main Hours Table ---
        headers = ['Day of Week', 'Date', 'Job', 'In', 'Lunch Start', 'Lunch End', 'Out', 'Hours']
        for col_num, text in enumerate(headers, 2):
            cell = ws.cell(row=8, column=col_num, value=text)
            cell.font, cell.fill, cell.border, cell.alignment = header_font, header_fill, thin_border, center_aligned

        ws.merge_cells('B16:I16')
        cutoff_cell = ws['B16']
        cutoff_cell.value = "---Week Cutoff---"
        cutoff_cell.font = bold_font
        cutoff_cell.alignment = center_aligned

        entries_dict = {e.date_worked: e for e in entries}
        current_date = start_date
        row_num = 9
        max_job_length = 0

        while current_date <= end_date:
            if row_num == 16:
                row_num += 1

            entry = entries_dict.get(current_date)
            job_address = entry.task_description if entry else ""
            if job_address:
                max_job_length = max(max_job_length, len(str(job_address)))

            # Calculate Lunch End based on Duration
            lunch_end_str = ""
            if entry and entry.lunch_start_time and hasattr(entry, 'lunch_duration'):
                import datetime
                dummy = datetime.date.today()
                start_dt = datetime.datetime.combine(dummy, entry.lunch_start_time)
                end_dt = start_dt + datetime.timedelta(minutes=entry.lunch_duration)
                lunch_end_str = end_dt.strftime('%I:%M %p')

            row_data = [
                current_date.strftime('%A'),
                current_date.strftime('%m/%d/%Y'),
                job_address,
                entry.start_time.strftime('%I:%M %p') if entry and entry.start_time else "",
                entry.lunch_start_time.strftime('%I:%M %p') if entry and entry.lunch_start_time else "",
                lunch_end_str,
                entry.end_time.strftime('%I:%M %p') if entry and entry.end_time else "",
                float(entry.hours_worked) if entry and entry.hours_worked else None
            ]

            is_stripe_row = (row_num % 2 == 0)
            for col_offset, value in enumerate(row_data, 2):
                cell = ws.cell(row=row_num, column=col_offset, value=value)
                cell.border, cell.alignment = thin_border, center_aligned
                if is_stripe_row:
                    cell.fill = stripe_fill
                if col_offset == 9 and value is not None:
                    cell.number_format = '0.00'
            current_date += timedelta(days=1)
            row_num += 1

        # Total Row
        ws.cell(row=row_num, column=8, value="TOTAL:").font = bold_font
        sum_cell = ws.cell(row=row_num, column=9, value=f"=SUM(I9:I{row_num - 1})")
        sum_cell.font, sum_cell.border, sum_cell.alignment = bold_font, thin_border, center_aligned
        sum_cell.number_format = '0.00'

        # --- Side-Panel L&I Trade Matrix ---
        ws.merge_cells('L6:M6')
        ws['L6'] = "L&I Trade Matrix"
        ws['L6'].font = bold_font

        matrix_header_row = 8
        for col, val in [(12, "Trade Type"), (13, "Total Hours")]:
            cell = ws.cell(row=matrix_header_row, column=col, value=val)
            cell.font, cell.fill, cell.border, cell.alignment = header_font, header_fill, thin_border, center_aligned

        trades = ['Painting - Interior', 'Painting - Exterior', 'Roofing', 'Framing',
                  'Finish Carpentry', 'Flooring', 'Fencing', 'Remodel / Repair', 'Estimator']

        trade_totals = defaultdict(float)
        for entry in entries:
            allocations = TradeAllocation.objects.filter(timesheet=entry)
            for alloc in allocations:
                trade_totals[alloc.trade_type] += float(alloc.hours_allocated)

        matrix_row = 9
        for trade in trades:
            is_stripe_row = (matrix_row % 2 == 0)
            cell_l = ws.cell(row=matrix_row, column=12, value=trade)
            cell_m = ws.cell(row=matrix_row, column=13, value=trade_totals.get(trade, 0) or "")

            for cell in [cell_l, cell_m]:
                cell.border = thin_border
                if is_stripe_row:
                    cell.fill = stripe_fill
                if cell.column == 13:
                    cell.alignment = center_aligned
                    cell.number_format = '0.00'
            matrix_row += 1

        ws.cell(row=18, column=12, value="TOTAL:").font = bold_font
        matrix_sum_cell = ws.cell(row=18, column=13, value="=SUM(M9:M17)")
        matrix_sum_cell.font, matrix_sum_cell.border, matrix_sum_cell.alignment = bold_font, thin_border, center_aligned
        matrix_sum_cell.number_format = '0.00'

        # --- Final Column Sizing ---
        ws.column_dimensions['B'].width = 17
        ws.column_dimensions['C'].width = 12
        ws.column_dimensions['D'].width = max_job_length + 4 if max_job_length > 12 else 12
        for col in ['E', 'F', 'G', 'H', 'I']:
            ws.column_dimensions[col].width = 12
        ws.column_dimensions['L'].width = 20
        ws.column_dimensions['M'].width = 15

    response = HttpResponse(content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')
    response['Content-Disposition'] = f'attachment; filename="Empyreal_Payroll_{end_date}.xlsx"'
    wb.save(response)
    return response


# Standard Admin configuration
class TradeAllocationInline(admin.TabularInline):
    model = TradeAllocation
    extra = 0


@admin.register(TimesheetEntry)
class TimesheetEntryAdmin(admin.ModelAdmin):
    # This controls what you see in the main list
    list_display = ('user', 'date_worked', 'hours_worked', 'status')

    # This adds the filter sidebar for easy navigation
    list_filter = ('user', 'status', 'date_worked')

    # This adds your new tools to the "Action" dropdown
    actions = [approve_timesheets, export_to_excel]

    inlines = [TradeAllocationInline]