
from django import forms
from .models import Booking, Vehicle
from .models import TripReport


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['destination', 'start_time', 'end_time', 'reason']
        widgets = {
            'start_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'end_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'
            ),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['vehicle_number', 'model', 'capacity']

class TripReportForm(forms.ModelForm):
    class Meta:
        model = TripReport
        fields = ['distance', 'fuel_used', 'notes']
        widgets = {
            'distance': forms.NumberInput(attrs={'placeholder': 'e.g. 120.5', 'step': '0.1'}),
            'fuel_used': forms.NumberInput(attrs={'placeholder': 'e.g. 15.2', 'step': '0.1'}),
            'notes': forms.Textarea(attrs={'rows': 3, 'placeholder': 'Any issues, route taken, etc...'}),
        }
      