# pool_app/forms.py
from django import forms
from .models import Booking, Vehicle, TripReport

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_time', 'end_time', 'destination', 'purpose',]
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'purpose': forms.Textarea(attrs={'rows': 3}),
        }

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['model', 'vehicle_number', 'capacity']

class TripReportForm(forms.ModelForm):
    class Meta:
        model = TripReport
        fields = ['distance_travelled', 'fuel_used', 'notes']
        widgets = {
            'notes': forms.Textarea(attrs={'rows': 3}),
        }