# pool_app/forms.py — FINAL & PERFECT
from django import forms
from django.contrib.auth.forms import PasswordResetForm
from django.contrib.auth import get_user_model
from .models import Booking, Vehicle, Driver

class CustomPasswordResetForm(PasswordResetForm):
    email = forms.CharField(
        label="Username or Email",
        max_length=254,
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Enter your username or email'}),
    )

    def clean_email(self):
        email = self.cleaned_data.get('email')
        User = get_user_model()

       
        user = User.objects.filter(username=email).first()
        if not user:
            user = User.objects.filter(email=email).first()

        if not user:
            raise forms.ValidationError("No user found with this username or email.")

        if not user.is_active:
            raise forms.ValidationError("This account is inactive.")

        if not user.email:
            raise forms.ValidationError("This user does not have an email address set. Please contact an administrator to reset your password.")

        return user.email


class BookingForm(forms.ModelForm):
    class Meta:
        model = Booking
        fields = ['start_time', 'end_time', 'destination', 'purpose']
        widgets = {
            'start_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M'
            ),
            'end_time': forms.DateTimeInput(
                attrs={'type': 'datetime-local', 'class': 'form-control'},
                format='%Y-%m-%dT%H:%M'
            ),
            'destination': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Where are you going?'}),
            'purpose': forms.Textarea(attrs={'rows': 3, 'class': 'form-control', 'placeholder': 'Purpose of trip...'}),
        }

    def clean(self):
        cleaned_data = super().clean()
        start_time = cleaned_data.get('start_time')
        end_time = cleaned_data.get('end_time')

        if start_time and end_time:
            if end_time <= start_time:
                raise forms.ValidationError("End time must be after start time.")

        return cleaned_data


class VehicleForm(forms.ModelForm):
    class Meta:
        model = Vehicle
        fields = ['model', 'vehicle_number', 'capacity', 'status', 'photo']
        widgets = {
            'model': forms.TextInput(attrs={'class': 'form-control'}),
            'vehicle_number': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform: uppercase;'}),
            'capacity': forms.NumberInput(attrs={'min': 1, 'class': 'form-control'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }


class DriverForm(forms.ModelForm):
    class Meta:
        model = Driver
        fields = ['name', 'phone', 'license_no', 'status', 'photo']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'phone': forms.TextInput(attrs={'class': 'form-control'}),
            'license_no': forms.TextInput(attrs={'class': 'form-control', 'style': 'text-transform: uppercase;'}),
            'status': forms.Select(attrs={'class': 'form-select'}),
            'photo': forms.FileInput(attrs={'class': 'form-control', 'accept': 'image/*'}),
        }
