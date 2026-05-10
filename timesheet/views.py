from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db import transaction
from .models import TimesheetEntry, TradeAllocation


@login_required
def submit_timesheet(request, pk=None):
    # Check if we are editing an existing draft
    instance = get_object_or_404(TimesheetEntry, pk=pk, user=request.user) if pk else None

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

        # Calculate lunch duration based on the hidden inputs sent by JS
        l_out = request.POST.get('lunch_out')
        l_in = request.POST.get('lunch_in')

        duration = 0
        if l_out == "12:00":
            if l_in == "12:30":
                duration = 30
            elif l_in == "13:00":
                duration = 60

        try:
            with transaction.atomic():
                if instance:
                    # Update existing instance
                    instance.date_worked = date_worked
                    instance.task_description = job_description
                    instance.start_time = start_time  # THIS WAS MISSING
                    instance.end_time = end_time      # THIS WAS MISSING
                    instance.lunch_duration = duration
                    instance.hours_worked = total_hours
                    instance.status = 'DRAFT'
                    instance.save()
                    # Wipe old allocations to avoid duplicates on re-save
                    instance.trade_allocations.all().delete()
                    timesheet = instance
                else:
                    # Create new draft
                    timesheet = TimesheetEntry.objects.create(
                        user=request.user,
                        date_worked=date_worked,
                        task_description=job_description,
                        start_time=start_time,        # THIS WAS MISSING
                        end_time=end_time,            # THIS WAS MISSING
                        lunch_duration=duration,
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

    return render(request, 'timesheet/timesheet_form.html', {'instance': instance})

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