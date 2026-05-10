from django.db import models
from django.conf import settings
from django.core.validators import FileExtensionValidator
import string, random

def generate_short_id():
    # Generates an 10-character code (e.g., 'K9xP2mQz7L')
    chars = string.ascii_letters + string.digits
    return ''.join(random.choice(chars) for _ in range(10))

class TimesheetEntry(models.Model):

    id = models.CharField(
        primary_key=True,
        max_length=12,
        default=generate_short_id,
        editable=False
    )

    STATUS_CHOICES = [
        ('PENDING', 'Pending Review'),
        ('APPROVED', 'Approved'),
        ('REJECTED', 'Rejected'),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='timesheets'
    )

    start_time = models.TimeField(null=True, blank=True)
    end_time = models.TimeField(null=True, blank=True)

    lunch_duration = models.IntegerField(default=0)

    date_worked = models.DateField()
    hours_worked = models.DecimalField(max_digits=5, decimal_places=2)
    task_description = models.TextField(blank=True)  # This is your "Job" field

    paystub_attachment = models.FileField(
        upload_to='paystubs/%Y/%m/',
        null=True,
        blank=True,
        validators=[FileExtensionValidator(allowed_extensions=['pdf'])]
    )

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default='PENDING')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Timesheet Entries"


class TradeAllocation(models.Model):
    timesheet = models.ForeignKey(TimesheetEntry, on_delete=models.CASCADE, related_name='trade_allocations')
    trade_type = models.CharField(max_length=100)
    hours_allocated = models.DecimalField(max_digits=5, decimal_places=2)