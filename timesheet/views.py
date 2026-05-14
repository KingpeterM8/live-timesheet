from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import TimesheetEntry, TradeAllocation
from django.utils import timezone
from datetime import date, timedelta, datetime
from django.db.models import Sum


@login_required
def submit_timesheet(request, pk=None):
    instance = get_object_or_404(TimesheetEntry, pk=pk, user=request.user) if pk else None

    # --- 1. INITIALIZE EVERYTHING WITH DEFAULTS ---
    p_start = ""
    p_end = ""
    p_l_start = ""
    p_l_end = ""
    active_preset = ""

    # --- 2. FILL VARIABLES IF DATA EXISTS ---
    if instance:
        p_start = instance.start_time.strftime('%H:%M') if instance.start_time else ""
        p_end = instance.end_time.strftime('%H:%M') if instance.end_time else ""
        p_l_start = instance.lunch_start_time.strftime('%H:%M') if instance.lunch_start_time else ""

        if instance.lunch_duration == 30:
            active_preset = 30
        elif instance.lunch_duration == 60:
            active_preset = 60

        # Calculate end time for the form UI
        if instance.lunch_start_time:
            temp_dt = datetime.combine(date.today(), instance.lunch_start_time)
            end_dt = temp_dt + timedelta(minutes=instance.lunch_duration)
            p_l_end = end_dt.strftime('%H:%M')

    # --- 3. BUILD THE CONTEXT ENVELOPE ---
    context = {
        'instance': instance,
        'p_start': p_start,
        'p_end': p_end,
        'p_l_start': p_l_start,
        'p_l_end': p_l_end,
        'active_preset': active_preset,
    }

    if request.method == 'POST':
        date_worked = request.POST.get('date')
        job_description = request.POST.get('job')
        start_time = request.POST.get('start_time')
        end_time = request.POST.get('end_time')
        total_hours = request.POST.get('total_hours')
        trade_types = request.POST.getlist('trade_type[]')
        trade_hours = request.POST.getlist('trade_hours[]')

        if not trade_types or not trade_hours:
            messages.error(request, "You must allocate at least one trade.")
            return render(request, 'timesheet/timesheet_form.html', {'instance': instance})

        l_start = request.POST.get('lunch_start_time')
        l_end = request.POST.get('lunch_end_time')

        def time_to_minutes(time_str):
            h, m = map(int, time_str.split(':'))
            return h * 60 + m

        s_mins = time_to_minutes(start_time)
        e_mins = time_to_minutes(end_time)

        # Midnight crossover logic
        if e_mins < s_mins:
            e_mins += 1440  # Add 24 hours in minutes

        total_shift_mins = e_mins - s_mins

        # Back-end 16 hour check
        if total_shift_mins > 960:  # 16 hours * 60
            messages.error(request, "Shift cannot exceed 16 hours.")
            return render(request, 'timesheet/timesheet_form.html', {'instance': instance})

        # 2. Dynamic duration calculation
        duration = 0
        lunch_start_obj = None  # Store this in a temporary variable

        if l_start and l_end:
            ls_mins = time_to_minutes(l_start)
            le_mins = time_to_minutes(l_end)

            if ls_mins < s_mins and e_mins > 1440:
                ls_mins += 1440
                le_mins += 1440

            duration = le_mins - ls_mins

            try:
                lunch_start_obj = datetime.strptime(l_start, '%H:%M').time()
            except (ValueError, TypeError):
                lunch_start_obj = None

        # 1. Look for an existing entry on this date (excluding the current one if we are just editing)
        existing_entry = TimesheetEntry.objects.filter(
            user=request.user,
            date_worked=date_worked
        ).exclude(pk=pk).first()

        # 2. If it exists and they haven't confirmed an override yet, send them back with a warning
        if existing_entry and request.POST.get('confirm_override') != 'true':
            # We pack up everything they just typed so the form doesn't wipe blank
            preserved_trades = zip(trade_types, trade_hours)
            return render(request, 'timesheet/timesheet_form.html', {
                'instance': instance,
                'override_warning': True,
                'existing_date': date_worked,
                'p_date': date_worked,
                'p_job': job_description,
                'p_start': start_time,
                'p_end': end_time,
                'p_l_start': l_start,
                'p_l_end': l_end,
                'p_trades': preserved_trades,
            })

        # 3. If they confirmed the override, we swap the instance to the old entry!
        # Your existing transaction block below will now safely OVERWRITE the old one.
        if existing_entry and request.POST.get('confirm_override') == 'true':
            instance = existing_entry

        try:
            with transaction.atomic():
                if instance:
                    # Update existing instance
                    instance.date_worked = date_worked
                    instance.task_description = job_description
                    instance.start_time = start_time
                    instance.end_time = end_time
                    instance.lunch_duration = duration
                    instance.lunch_start_time = lunch_start_obj  # ASSIGN HERE
                    instance.hours_worked = total_hours
                    instance.status = 'DRAFT'
                    instance.save()
                    instance.trade_allocations.all().delete()
                    timesheet = instance
                else:
                    # Create new draft
                    timesheet = TimesheetEntry.objects.create(
                        user=request.user,
                        date_worked=date_worked,
                        task_description=job_description,
                        start_time=start_time,
                        end_time=end_time,
                        lunch_duration=duration,
                        lunch_start_time=lunch_start_obj,  # ASSIGN HERE
                        hours_worked=total_hours,
                        status='DRAFT'
                    )

                for t_type, t_hours in zip(trade_types, trade_hours):
                    if t_type and float(t_hours) > 0:
                        TradeAllocation.objects.create(
                            timesheet=timesheet,
                            trade_type=t_type,
                            hours_allocated=t_hours
                        )

            # Redirect to the review page instead of the form
            return redirect('review_timesheet', pk=timesheet.pk)

        except Exception as e:
            messages.error(request, f"An error occurred: {str(e)}")
            return render(request, 'timesheet/timesheet_form.html', {'instance': instance})

    return render(request, 'timesheet/timesheet_form.html', context)

@login_required
def review_timesheet(request, pk):
    # This matches the 'review_timesheet' name in your urls.py
    timesheet = get_object_or_404(TimesheetEntry, pk=pk, user=request.user)
    return render(request, 'timesheet/review_timesheet.html', {'timesheet': timesheet})

@login_required
def finalize_timesheet(request, pk):
    if request.method == 'POST':
        timesheet = get_object_or_404(TimesheetEntry, pk=pk, user=request.user)
        timesheet.status = 'PENDING'
        timesheet.save()
        messages.success(request, "Timesheet finalized! Sent to payroll for review.")
        return redirect('home')
    return redirect('review_timesheet', pk=pk)

@login_required
def timesheet_history(request):
    today = date.today()

    # Calculate the 2-week pay period window
    if today.day <= 15:
        period_start = today.replace(day=1)
        period_end = today.replace(day=15)
    else:
        period_start = today.replace(day=16)
        # Safely calculate the last day of the current month
        if today.month == 12:
            next_month_start = date(today.year + 1, 1, 1)
        else:
            next_month_start = date(today.year, today.month + 1, 1)
        period_end = next_month_start - timedelta(days=1)

    # Fetch entries ONLY for the logged-in user within this date range
    entries = TimesheetEntry.objects.filter(
        user=request.user,
        date_worked__range=[period_start, period_end]
    ).order_by('-date_worked')

    return render(request, 'timesheet/history.html', {
        'entries': entries,
        'period_start': period_start,
        'period_end': period_end
    })

@login_required
def history_view(request):
    today = date.today()

    # --- NEW: Calculate the ACTUAL current pay period for the static header ---
    if today.day <= 15:
        curr_start = today.replace(day=1)
        curr_end = today.replace(day=15)
    else:
        curr_start = today.replace(day=16)
        next_month = today.replace(day=28) + timedelta(days=4)
        curr_end = next_month - timedelta(days=next_month.day)

    # --- Existing logic for the period the user is LOOKING at ---
    view_date_str = request.GET.get('date')
    view_date = date.fromisoformat(view_date_str) if view_date_str else today

    # (Keep your existing start_date/end_date calculation logic here...)
    if view_date.day <= 15:
        start_date = view_date.replace(day=1)
        end_date = view_date.replace(day=15)
        prev_period_date = (start_date - timedelta(days=1)).replace(day=16)
        next_period_date = view_date.replace(day=16)
    else:
        start_date = view_date.replace(day=16)
        next_month = view_date.replace(day=28) + timedelta(days=4)
        end_date = next_month - timedelta(days=next_month.day)
        prev_period_date = view_date.replace(day=1)
        next_period_date = (end_date + timedelta(days=1))

    # (Keep your existing show_previous/show_next logic here...)
    earliest_entry = TimesheetEntry.objects.filter(user=request.user).order_by('date_worked').first()
    earliest_date = earliest_entry.date_worked if earliest_entry else today
    show_previous = prev_period_date >= earliest_date.replace(day=1)
    show_next = next_period_date <= today

    entries = TimesheetEntry.objects.filter(
        user=request.user,
        date_worked__range=[start_date, end_date]  # Use the corrected field name 'date_worked'
    ).order_by('-date_worked')

    total_hours = entries.aggregate(Sum('hours_worked'))['hours_worked__sum'] or 0

    return render(request, 'timesheet/history.html', {
        'entries': entries,
        'total_hours': total_hours,  # Pass this to the template
        'prev_period_date': prev_period_date.isoformat(),
        'next_period_date': next_period_date.isoformat(),
        'show_previous': show_previous,
        'show_next': show_next,
        'start_date': start_date,  # Used for the navigation label
        'end_date': end_date,  # Used for the navigation label
        'curr_start': curr_start,  # NEW: Used for the static header
        'curr_end': curr_end,  # NEW: Used for the static header
        'curr_start': curr_start,
        'curr_end': curr_end,
    })