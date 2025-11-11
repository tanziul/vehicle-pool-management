# pool_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from .models import User, Driver, Vehicle, Booking, TripReport
from .forms import BookingForm, VehicleForm, TripReportForm

# ======================
# AUTH & NAVIGATION
# ======================
def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        if user and user.is_active:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials or account inactive.')
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def dashboard(request):
    if request.user.is_superuser or request.user.role == 'Admin':
        return redirect('admin_dashboard')
    elif request.user.role in ['Employee', 'Manager', 'HR']:
        return redirect('user_dashboard')
    messages.error(request, 'Access denied.')
    return redirect('home')

# ======================
# USER DASHBOARD
# ======================
@login_required
def user_dashboard(request):
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    vehicles = Vehicle.objects.select_related('assigned_driver').all()
    return render(request, 'user/dashboard.html', {'vehicles': vehicles})

@login_required
def user_bookings(request):
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    bookings = Booking.objects.filter(employee=request.user).order_by('-created_at')
    return render(request, 'user/bookings.html', {'bookings': bookings})

@login_required
def user_reports(request):
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    reports = TripReport.objects.filter(booking__employee=request.user).order_by('-completed_at')
    return render(request, 'user/reports.html', {'reports': reports})

@login_required
def request_vehicle(request, vehicle_id):
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status='Available')
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.employee = request.user
            booking.vehicle = vehicle
            booking.save()
            messages.success(request, 'Booking request submitted!')
            return redirect('user_bookings')
    else:
        form = BookingForm()
    return render(request, 'user/request_form.html', {'form': form, 'vehicle': vehicle})

# ======================
# ADMIN DASHBOARD
# ======================
@login_required
def admin_dashboard(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    stats = {
        'total_vehicles': Vehicle.objects.count(),
        'available_vehicles': Vehicle.objects.filter(status='Available').count(),
        'total_drivers': Driver.objects.count(),
        'active_drivers': Driver.objects.filter(status='Active').count(),
        'pending_requests': Booking.objects.filter(status='Pending').count(),
        'completed_this_month': TripReport.objects.filter(completed_at__month=timezone.now().month).count(),
    }
    return render(request, 'admin/dashboard.html', stats)

@login_required
def admin_bookings(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    bookings = Booking.objects.select_related('employee', 'vehicle').all().order_by('-priority', 'start_time')
    available_vehicles = Vehicle.objects.filter(status='Available').select_related('assigned_driver')
    return render(request, 'admin/bookings.html', {
        'bookings': bookings,
        'vehicles': available_vehicles
    })

@login_required
def admin_vehicles(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    vehicles = Vehicle.objects.select_related('assigned_driver').all().order_by('-id')
    form = VehicleForm()
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            vehicle = form.save()
            messages.success(request, f'Vehicle {vehicle.model} added.')
            return redirect('admin_vehicles')
    return render(request, 'admin/vehicles.html', {
        'vehicles': vehicles,
        'form': form
    })

@login_required
def edit_vehicle(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == 'POST':
        vehicle.vehicle_number = request.POST['vehicle_number']
        vehicle.model = request.POST['model']
        vehicle.capacity = request.POST['capacity']
        vehicle.save()
        messages.success(request, f'Vehicle {vehicle.model} updated.')
        return redirect('admin_vehicles')
    return redirect('admin_vehicles')

@login_required
def admin_drivers(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    drivers = Driver.objects.select_related('assigned_vehicle').all().order_by('-status', 'name')
    available_vehicles = Vehicle.objects.filter(status='Available')
    return render(request, 'admin/drivers.html', {
        'drivers': drivers,
        'available_vehicles': available_vehicles
    })

@login_required
def add_driver(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    if request.method == 'POST':
        vehicle = None
        if request.POST.get('assigned_vehicle'):
            vehicle = get_object_or_404(Vehicle, id=request.POST['assigned_vehicle'], status='Available')
        Driver.objects.create(
            name=request.POST['name'],
            phone=request.POST['phone'],
            license_no=request.POST['license_no'],
            status=request.POST.get('status', 'Active'),
            assigned_vehicle=vehicle
        )
        messages.success(request, 'Driver added.')
    return redirect('admin_drivers')

@login_required
def edit_driver(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == 'POST':
        old_vehicle = driver.assigned_vehicle
        new_vehicle = None
        if request.POST.get('assigned_vehicle'):
            new_vehicle = get_object_or_404(Vehicle, id=request.POST['assigned_vehicle'], status='Available')
        if old_vehicle and old_vehicle != new_vehicle:
            if old_vehicle.status != 'Booked':
                old_vehicle.assigned_driver = None
                old_vehicle.save()
        driver.name = request.POST['name']
        driver.phone = request.POST['phone']
        driver.license_no = request.POST['license_no']
        driver.status = request.POST['status']
        driver.assigned_vehicle = new_vehicle
        driver.save()
        messages.success(request, 'Driver updated.')
    return redirect('admin_drivers')

@login_required
def delete_driver(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    driver = get_object_or_404(Driver, pk=pk)
    vehicle = driver.assigned_vehicle
    driver.delete()
    if vehicle and vehicle.status != 'Booked':
        vehicle.assigned_driver = None
        vehicle.save()
    messages.success(request, 'Driver deleted.')
    return redirect('admin_drivers')

@login_required
def admin_reports(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    reports = TripReport.objects.select_related('booking__vehicle').all().order_by('-completed_at')
    return render(request, 'admin/reports.html', {'reports': reports})

@login_required
def admin_users(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    users = User.objects.all().order_by('role', 'username')
    return render(request, 'admin/users.html', {
        'users': users,
        'ROLE_CHOICES': User.ROLE_CHOICES
    })

@login_required
def add_user(request):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    if request.method == 'POST':
        try:
            user = User.objects.create_user(
                username=request.POST['username'],
                password=request.POST['password'],
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', ''),
                email=request.POST.get('email', ''),
                role=request.POST['role']
            )
            user.is_active = True
            user.save()
            messages.success(request, f'User {user.get_full_name()} created.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_users')

@login_required
def edit_user(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        user.username = request.POST['username']
        user.first_name = request.POST['first_name']
        user.last_name = request.POST['last_name']
        user.email = request.POST.get('email', '')
        user.role = request.POST['role']
        if request.POST.get('password'):
            user.set_password(request.POST['password'])
        user.save()
        messages.success(request, 'User updated.')
    return redirect('admin_users')

@login_required
def delete_user(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    if user != request.user:
        user.delete()
        messages.success(request, 'User deleted.')
    else:
        messages.error(request, 'Cannot delete your own account.')
    return redirect('admin_users')

@login_required
def approve_booking(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    if request.method == 'POST':
        vehicle_id = request.POST.get('vehicle')
        if not vehicle_id:
            messages.error(request, 'Please select a vehicle.')
            return redirect('admin_bookings')
        vehicle = get_object_or_404(Vehicle, id=vehicle_id, status='Available')
        booking.vehicle = vehicle
        booking.status = 'Approved'
        booking.approved_by = request.user
        vehicle.status = 'Booked'
        vehicle.save()
        booking.save()
        messages.success(request, f'Booking approved with {vehicle}.')
    return redirect('admin_bookings')

@login_required
def reject_booking(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    booking.status = 'Rejected'
    booking.save()
    messages.success(request, 'Booking rejected.')
    return redirect('admin_bookings')

@login_required
def complete_trip(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    booking = get_object_or_404(Booking, pk=pk, status='Approved')
    if request.method == 'POST':
        form = TripReportForm(request.POST)
        if form.is_valid():
            report = form.save(commit=False)
            report.booking = booking
            report.save()
            booking.status = 'Completed'
            if booking.vehicle:
                booking.vehicle.status = 'Available'
                booking.vehicle.save()
            booking.save()
            messages.success(request, f'Trip completed! Vehicle is now Available.')
            return redirect('admin_bookings')
    else:
        form = TripReportForm()
    return render(request, 'admin/complete_trip.html', {
        'form': form,
        'booking': booking
    })