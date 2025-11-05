from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from .models import Booking, Vehicle, TripReport
from .forms import UserRegisterForm, BookingForm, VehicleAssignForm, TripReportForm



def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials')
    return render(request, 'login.html')

def register_view(request):
    if request.method == 'POST':
        form = UserRegisterForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Registration successful! Please login.')
            return redirect('login')
    else:
        form = UserRegisterForm()
    return render(request, 'register.html', {'form': form})

@login_required
def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def employee_dashboard(request):
    bookings = Booking.objects.filter(employee=request.user).order_by('-created_at')
    return render(request, 'employee/dashboard.html', {'bookings': bookings})

@login_required
def booking_create(request):
    if request.method == 'POST':
        form = BookingForm(request.POST, request.FILES)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.employee = request.user
            booking.save()
            messages.success(request, 'Booking request submitted!')
            return redirect('employee_dashboard')
    else:
        form = BookingForm()
    return render(request, 'employee/booking_form.html', {'form': form})

@user_passes_test(lambda u: u.role == 'Admin')
def admin_dashboard(request):
    pending = Booking.objects.filter(status='Pending').order_by('-priority', 'start_time')
    return render(request, 'admin/dashboard.html', {'pending': pending})

@user_passes_test(lambda u: u.role == 'Admin')
def assign_vehicle(request, pk):
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    if request.method == 'POST':
        form = VehicleAssignForm(request.POST, instance=booking)
        if form.is_valid():
            vehicle = form.cleaned_data['vehicle']
            vehicle.status = 'Booked'
            vehicle.save()
            booking.status = 'Approved'
            booking.approved_by = request.user
            booking.save()
            messages.success(request, f'Vehicle {vehicle} assigned!')
            return redirect('admin_dashboard')
    else:
        form = VehicleAssignForm(instance=booking)
    return render(request, 'admin/assign_vehicle.html', {'form': form, 'booking': booking})

@user_passes_test(lambda u: u.role == 'Admin')
def complete_trip(request, pk):
    booking = get_object_or_404(Booking, pk=pk, status='Approved')
    if request.method == 'POST':
        form = TripReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.booking = booking
            report.save()
            booking.status = 'Completed'
            booking.vehicle.status = 'Available'
            booking.vehicle.save()
            booking.save()
            messages.success(request, 'Trip completed!')
            return redirect('admin_dashboard')
    else:
        form = TripReportForm()
    return render(request, 'admin/complete_trip.html', {'form': form, 'booking': booking})

@login_required
def dashboard(request):
    if request.user.role == 'Admin':
        return redirect('admin_dashboard')
    return redirect('employee_dashboard')