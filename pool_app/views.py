# pool_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import User, Driver, Vehicle, Booking, TripReport
from .forms import BookingForm, TripReportForm


# ======================
# AUTO UPDATE EXPIRED BOOKINGS (GLOBAL)
# ======================
def update_expired_bookings():
    """Auto-complete bookings whose end_time has passed and free the vehicle"""
    now = timezone.now()
    expired = Booking.objects.filter(
        status='Approved',
        end_time__lt=now
    ).select_related('vehicle')

    for booking in expired:
        if booking.vehicle:
            booking.vehicle.status = 'Available'
            booking.vehicle.save(update_fields=['status'])
        booking.status = 'Completed'
        booking.save(update_fields=['status'])


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
    messages.success(request, 'You have been logged out.')
    return redirect('home')


@login_required
def dashboard(request):
    update_expired_bookings()
    if request.user.is_superuser or request.user.role == 'Admin':
        return redirect('admin_dashboard')
    elif request.user.role in ['Employee', 'Manager', 'HR']:
        return redirect('user_dashboard')
    messages.error(request, 'Access denied.')
    return redirect('home')


# ======================
# USER VIEWS
# ======================
@login_required
def user_dashboard(request):
    update_expired_bookings()
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    vehicles = Vehicle.objects.select_related('assigned_driver').all()
    return render(request, 'user/dashboard.html', {'vehicles': vehicles})


@login_required
def user_bookings(request):
    update_expired_bookings()
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    bookings = Booking.objects.filter(employee=request.user).select_related('vehicle').order_by('-created_at')
    return render(request, 'user/bookings.html', {'bookings': bookings})


@login_required
def user_reports(request):
    update_expired_bookings()
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    reports = TripReport.objects.filter(booking__employee=request.user).select_related('booking__vehicle').order_by('-completed_at')
    return render(request, 'user/reports.html', {'reports': reports})


@login_required
def request_vehicle(request, vehicle_id):
    update_expired_bookings()
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status='Available')
    
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.employee = request.user
            booking.vehicle = vehicle
            booking.status = 'Pending'
            booking.save()
            messages.success(request, f'Booking request for {vehicle.model} submitted!')
            return redirect('user_bookings')
    else:
        form = BookingForm()
    
    return render(request, 'user/request_form.html', {'form': form, 'vehicle': vehicle})


# ======================
# ADMIN VIEWS
# ======================
@login_required
def admin_dashboard(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    now = timezone.now()
    stats = {
        'total_vehicles': Vehicle.objects.count(),
        'available_vehicles': Vehicle.objects.filter(status='Available').count(),
        'booked_vehicles': Vehicle.objects.filter(status='Booked').count(),
        'maintenance_vehicles': Vehicle.objects.filter(status='Maintenance').count(),
        'total_drivers': Driver.objects.count(),
        'active_drivers': Driver.objects.filter(status='Active').count(),
        'inactive_drivers': Driver.objects.filter(status='Inactive').count(),
        'pending_requests': Booking.objects.filter(status='Pending').count(),
        'approved_requests': Booking.objects.filter(status='Approved').count(),
        'completed_requests': Booking.objects.filter(status='Completed').count(),
        'completed_this_month': TripReport.objects.filter(completed_at__year=now.year, completed_at__month=now.month).count(),
    }
    return render(request, 'admin/dashboard.html', stats)


@login_required
def admin_bookings(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    bookings = Booking.objects.select_related('employee', 'vehicle', 'approved_by').all().order_by('-priority', 'start_time')
    available_vehicles = Vehicle.objects.filter(status='Available').select_related('assigned_driver')
    return render(request, 'admin/bookings.html', {
        'bookings': bookings,
        'vehicles': available_vehicles,
        'now': timezone.now()
    })


@login_required
def admin_vehicles(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    vehicles = Vehicle.objects.select_related('assigned_driver').all().order_by('-id')
    available_drivers = Driver.objects.filter(status='Active', assigned_vehicle__isnull=True).order_by('name')
    
    for v in vehicles:
        v.is_in_use = v.bookings.filter(status='Approved').exists()
        v.pending_bookings_count = v.bookings.filter(status='Pending').count()

    if request.method == 'POST':
        try:
            with transaction.atomic():
                vehicle = Vehicle(
                    model=request.POST['model'].strip(),
                    vehicle_number=request.POST['vehicle_number'].strip(),
                    capacity=int(request.POST['capacity']),
                    status='Available'
                )
                vehicle.save()

                driver_id = request.POST.get('assigned_driver')
                if driver_id:
                    driver = get_object_or_404(Driver, id=driver_id, assigned_vehicle__isnull=True)
                    vehicle.assigned_driver = driver
                    vehicle.save()

                messages.success(request, f'Vehicle "{vehicle.model}" added.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('admin_vehicles')
    
    return render(request, 'admin/vehicles.html', {'vehicles': vehicles, 'drivers': available_drivers})


@login_required
def edit_vehicle(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    vehicle = get_object_or_404(Vehicle, pk=pk)
    available_drivers = Driver.objects.filter(status='Active', assigned_vehicle__isnull=True).exclude(id=vehicle.assigned_driver_id if vehicle.assigned_driver else None)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                vehicle.model = request.POST['model'].strip()
                vehicle.vehicle_number = request.POST['vehicle_number'].strip()
                vehicle.capacity = int(request.POST['capacity'])
                new_status = request.POST.get('status')
                if new_status in dict(Vehicle.STATUS_CHOICES):
                    vehicle.status = new_status
                
                driver_id = request.POST.get('assigned_driver')
                if driver_id:
                    driver = get_object_or_404(Driver, id=driver_id, assigned_vehicle__isnull=True)
                    if vehicle.assigned_driver:
                        vehicle.assigned_driver = None
                    vehicle.assigned_driver = driver
                else:
                    vehicle.assigned_driver = None
                
                vehicle.save()
            messages.success(request, f'Vehicle "{vehicle.model}" updated.')
        except Exception as e:
            messages.error(request, f'Update failed: {e}')
    
    return redirect('admin_vehicles')


@login_required
def update_vehicle_status(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == 'POST':
        new_status = request.POST.get('status')
        if new_status in dict(Vehicle.STATUS_CHOICES):
            if new_status == 'Available' and vehicle.bookings.filter(status='Approved').exists():
                messages.error(request, f'Cannot free {vehicle.model}: Active trip in progress.')
            else:
                vehicle.status = new_status
                vehicle.save()
                messages.success(request, f'Status: {new_status}')
    return redirect('admin_vehicles')


@login_required
def delete_vehicle(request, pk):
    update_expired_bookings()
    if not (request.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    vehicle = get_object_or_404(Vehicle, pk=pk)
    if request.method == 'POST':
        with transaction.atomic():
            pending_count = vehicle.bookings.filter(status='Pending').count()
            vehicle.bookings.filter(status='Pending').update(status='Cancelled')
            if vehicle.assigned_driver:
                vehicle.assigned_driver = None
            vehicle_name = f"{vehicle.model} ({vehicle.vehicle_number})"
            vehicle.delete()
        messages.success(request, f'Vehicle "{vehicle_name}" deleted. {pending_count} pending booking(s) cancelled.')
    return redirect('admin_vehicles')


@login_required
def admin_drivers(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    drivers = Driver.objects.select_related('assigned_vehicle').all().order_by('-status', 'name')
    return render(request, 'admin/drivers.html', {'drivers': drivers})


@login_required
def add_driver(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    if request.method == 'POST':
        try:
            Driver.objects.create(
                name=request.POST['name'].strip(),
                phone=request.POST['phone'].strip(),
                license_no=request.POST['license_no'].strip(),
                status=request.POST.get('status', 'Active')
            )
            messages.success(request, 'Driver added.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_drivers')


@login_required
def edit_driver(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    driver = get_object_or_404(Driver, pk=pk)
    if request.method == 'POST':
        try:
            driver.name = request.POST['name'].strip()
            driver.phone = request.POST['phone'].strip()
            driver.license_no = request.POST['license_no'].strip()
            driver.status = request.POST['status']
            driver.save()
            messages.success(request, f'Driver "{driver.name}" updated.')
        except Exception as e:
            messages.error(request, f'Error: {e}')
    return redirect('admin_drivers')


@login_required
def delete_driver(request, driver_id):
    update_expired_bookings()
    driver = get_object_or_404(Driver, id=driver_id)
    if request.method == "POST":
        vehicle_info = f"{driver.assigned_vehicle.model} ({driver.assigned_vehicle.vehicle_number})" if driver.assigned_vehicle else None
        driver.delete()
        if vehicle_info:
            messages.success(request, f"Driver deleted. Vehicle '{vehicle_info}' is now unassigned.")
        else:
            messages.success(request, "Driver deleted.")
    return redirect('admin_drivers')


@login_required
def admin_reports(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    reports = TripReport.objects.select_related('booking__vehicle', 'booking__employee').all().order_by('-completed_at')
    return render(request, 'admin/reports.html', {'reports': reports})


@login_required
def admin_users(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    users = User.objects.all().order_by('role', 'username')
    return render(request, 'admin/users.html', {'users': users, 'ROLE_CHOICES': User.ROLE_CHOICES})


@login_required
def add_user(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    if request.method == 'POST':
        try:
            user = User.objects.create_user(
                username=request.POST['username'].strip(),
                password=request.POST['password'],
                first_name=request.POST.get('first_name', '').strip(),
                last_name=request.POST.get('last_name', '').strip(),
                email=request.POST.get('email', '').strip(),
                role=request.POST['role']
            )
            user.is_active = True
            user.save()
            messages.success(request, f'User "{user.get_full_name() or user.username}" created.')
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
    return redirect('admin_users')


@login_required
def edit_user(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    if request.method == 'POST':
        try:
            user.username = request.POST['username'].strip()
            user.first_name = request.POST['first_name'].strip()
            user.last_name = request.POST['last_name'].strip()
            user.email = request.POST.get('email', '').strip()
            user.role = request.POST['role']
            if request.POST.get('password'):
                user.set_password(request.POST['password'])
            user.save()
            messages.success(request, f'User "{user.get_full_name() or user.username}" updated.')
        except Exception as e:
            messages.error(request, f'Update failed: {e}')
    return redirect('admin_users')


@login_required
def delete_user(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    user = get_object_or_404(User, pk=pk)
    if user == request.user:
        messages.error(request, 'You cannot delete your own account.')
    else:
        username = user.get_full_name() or user.username
        user.delete()
        messages.success(request, f'User "{username}" deleted.')
    return redirect('admin_users')


@login_required
def approve_booking(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    if request.method == 'POST':
        vehicle = booking.vehicle
        if not vehicle or vehicle.status != 'Available':
            messages.error(request, 'Vehicle no longer available.')
            return redirect('admin_bookings')
        with transaction.atomic():
            booking.status = 'Approved'
            booking.approved_by = request.user
            booking.approved_at = timezone.now()
            booking.save()
            vehicle.status = 'Booked'
            vehicle.save()
        messages.success(request, f'Approved! {vehicle.model} assigned to {booking.employee.get_full_name()}')
    return redirect('admin_bookings')


@login_required
def reject_booking(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    booking.status = 'Rejected'
    booking.save()
    messages.success(request, f'Booking #{booking.id} rejected.')
    return redirect('admin_bookings')


@login_required
def complete_trip(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    booking = get_object_or_404(Booking, pk=pk, status='Approved')
    vehicle = booking.vehicle
    if request.method == 'POST':
        form = TripReportForm(request.POST)
        if form.is_valid():
            with transaction.atomic():
                report = form.save(commit=False)
                report.booking = booking
                report.completed_at = timezone.now()
                report.save()
                booking.status = 'Completed'
                booking.save()
                if vehicle:
                    vehicle.status = 'Available'
                    vehicle.save()
            messages.success(request, f'Trip #{booking.id} completed. {vehicle.model} is now Available.')
            return redirect('admin_bookings')
        else:
            messages.error(request, 'Please correct the form errors.')
    else:
        form = TripReportForm()
    return render(request, 'admin/complete_trip.html', {'form': form, 'booking': booking, 'vehicle': vehicle})