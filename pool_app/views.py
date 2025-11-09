from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.utils import timezone
from .models import User, Vehicle, Booking, TripReport
from .forms import BookingForm, VehicleForm

def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user:
            # Allow login only for active users (except drivers)
            if user.is_active or user.role == 'Driver':
                login(request, user)
                return redirect('dashboard')
            else:
                messages.error(request, 'Account is inactive.')
        else:
            messages.error(request, 'Invalid credentials.')
    return render(request, 'login.html')

@login_required
def logout_view(request):
    logout(request)
    return redirect('home')

@login_required
def dashboard(request):
    # SUPERUSER or role='Admin' → Admin Panel
    if request.user.is_superuser or request.user.role == 'Admin':
        return redirect('admin_dashboard')
    
    # Employee/Manager/HR
    elif request.user.role in ['Employee', 'Manager', 'HR']:
        return redirect('user_dashboard')
    
    # Fallback
    messages.error(request, "Access denied.")
    return redirect('home')


# USER DASHBOARD (Employee/Manager/HR)
@login_required
@user_passes_test(lambda u: u.role in ['Employee', 'Manager', 'HR'])
def user_dashboard(request):
    vehicles = Vehicle.objects.all()
    return render(request, 'user/dashboard.html', {'vehicles': vehicles})

@login_required
@user_passes_test(lambda u: u.role in ['Employee', 'Manager', 'HR'])
def user_bookings(request):
    bookings = Booking.objects.filter(employee=request.user).order_by('-created_at')
    return render(request, 'user/bookings.html', {'bookings': bookings})

@login_required
@user_passes_test(lambda u: u.role in ['Employee', 'Manager', 'HR'])
def user_reports(request):
    reports = TripReport.objects.filter(booking__employee=request.user).order_by('-completed_at')
    return render(request, 'user/reports.html', {'reports': reports})

@login_required
@user_passes_test(lambda u: u.role in ['Employee', 'Manager', 'HR'])
def request_vehicle(request, vehicle_id):
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status='Available')
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.employee = request.user
            booking.vehicle = vehicle
            booking.save()
            messages.success(request, 'Request submitted!')
            return redirect('user_bookings')
    else:
        form = BookingForm()
    return render(request, 'user/request_form.html', {'form': form, 'vehicle': vehicle})


# ADMIN DASHBOARD
@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def admin_dashboard(request):
    stats = {
        'total_vehicles': Vehicle.objects.count(),
        'available_vehicles': Vehicle.objects.filter(status='Available').count(),
        'total_drivers': User.objects.filter(role='Driver').count(),
        'available_drivers': User.objects.filter(role='Driver', vehicle__isnull=True).count(),
        'pending_requests': Booking.objects.filter(status='Pending').count(),
        'completed_this_month': TripReport.objects.filter(completed_at__month=timezone.now().month).count(),
    }
    return render(request, 'admin/dashboard.html', stats)
@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def admin_bookings(request):
    bookings = Booking.objects.all().order_by('-priority', 'start_time')
    available_vehicles = Vehicle.objects.filter(status='Available')
    return render(request, 'admin/bookings.html', {
        'bookings': bookings,
        'vehicles': available_vehicles
    })
@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def admin_vehicles(request):
    vehicles = Vehicle.objects.all()
    form = VehicleForm()
    if request.method == 'POST':
        form = VehicleForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, 'Vehicle added.')
            return redirect('admin_vehicles')
    return render(request, 'admin/vehicles.html', {'vehicles': vehicles, 'form': form})

@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def admin_drivers(request):
    drivers = User.objects.filter(role='Driver')
    return render(request, 'admin/drivers.html', {'drivers': drivers})

@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def admin_reports(request):
    reports = TripReport.objects.all().order_by('-completed_at')
    return render(request, 'admin/reports.html', {'reports': reports})

@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def admin_users(request):
    users = User.objects.all().order_by('role', 'username')
    return render(request, 'admin/users.html', {
        'users': users,
        'ROLE_CHOICES': User.ROLE_CHOICES  # Pass choices to template
    })

# CRUD
@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def add_user(request):
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
            # Auto-activate non-drivers
            if user.role != 'Driver':
                user.is_active = True
            user.save()
            messages.success(request, f'{user.get_full_name()} created successfully.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_users')

@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def edit_user(request, pk):
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
@user_passes_test(lambda u: u.role == 'Admin')
def delete_user(request, pk):
    user = get_object_or_404(User, pk=pk)
    if user != request.user and user.role != 'Admin':
        user.delete()
        messages.success(request, 'User deleted.')
    else:
        messages.error(request, 'Cannot delete this user.')
    return redirect('admin_users')
@login_required
@user_passes_test(lambda u: u.role == 'Admin')
def approve_booking(request, pk):
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
@user_passes_test(lambda u: u.role == 'Admin')
def reject_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk)
    booking.status = 'Rejected'
    booking.save()
    messages.success(request, 'Booking rejected.')
    return redirect('admin_bookings')