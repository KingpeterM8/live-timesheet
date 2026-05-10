from django.contrib import admin
from .models import TimesheetEntry, TradeAllocation

# This allows you to see the Trade Rows inside the Timesheet page
class TradeAllocationInline(admin.TabularInline):
    model = TradeAllocation
    extra = 0

@admin.register(TimesheetEntry)
class TimesheetEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'date_worked', 'hours_worked', 'status')
    inlines = [TradeAllocationInline]