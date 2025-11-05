from django import forms
from django.contrib.auth.forms import UserCreationForm
from .models import Booking, Vehicle, TripReport, User  # User last

class UserRegisterForm(UserCreationForm):
    role = forms.ChoiceField(choices=User.ROLE_CHOICES)
    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'role', 'password1', 'password2']

class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['destination', 'start_time', 'end_time', 'reason', 'fuel_receipt']
        widgets = {
            'start_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'end_time': forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
            'reason': forms.Textarea(attrs={'rows': 3}),
        }

class VehicleAssignForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['vehicle']
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['vehicle'].queryset = Vehicle.objects.filter(status='Available')

class TripReportForm(forms.ModelForm):
    class Meta:
        model = TripReport
        fields = ['distance', 'fuel_used', 'notes']