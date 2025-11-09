from django import forms
from .models import Booking, Vehicle, User

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['destination', 'start_time', 'end_time', 'reason']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['vehicle_number', 'model', 'capacity', 'driver']