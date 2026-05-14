from django.urls import path
from . import views

urlpatterns = [
    # This will result in /sheet/timesheet/new/
    path('timesheet/new/', views.submit_timesheet, name='submit_timesheet'),

    # This will result in /sheet/timesheet/edit/ID/
    path('timesheet/edit/<str:pk>/', views.submit_timesheet, name='edit_timesheet'),

    # This will result in /sheet/timesheet/review/ID/
    path('timesheet/review/<str:pk>/', views.review_timesheet, name='review_timesheet'),

    # This will result in /sheet/timesheet/finalize/ID/
    path('timesheet/finalize/<str:pk>/', views.finalize_timesheet, name='finalize_timesheet'),

    path('history/', views.history_view, name='timesheet_history'),
]