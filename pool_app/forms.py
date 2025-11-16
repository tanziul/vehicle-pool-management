# pool_app/forms.py
from django import forms
from .models import Booking, Vehicle, TripReport


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_time', 'end_time', 'destination', 'purpose']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'purpose': forms.Textarea(attrs={'rows': 3}),
        }


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['model', 'vehicle_number', 'capacity']
        widgets = {
            'capacity': forms.NumberInput(attrs={'min': 1}),
        }


class TripReportForm(forms.ModelForm):
    class Meta:
        model = TripReport
        fields = ['start_odometer', 'end_odometer', 'fuel_used', 'notes']
        widgets = {
            'start_odometer': forms.NumberInput(attrs={'min': 0}),
            'end_odometer': forms.NumberInput(attrs={'min': 0}),
            'fuel_used': forms.NumberInput(attrs={'step': '0.01'}),
            'notes': forms.Textarea(attrs={'rows': 3}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start = cleaned_data.get('start_odometer')
        end = cleaned_data.get('end_odometer')

        if start is not None and end is not None and end < start:
            raise forms.ValidationError("End odometer must be greater than start odometer.")

        return cleaned_data