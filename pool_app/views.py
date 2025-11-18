# pool_app/views.py
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from .models import User, Driver, Vehicle, Booking, TripReport
from .forms import BookingForm, TripReportForm


def update_expired_bookings():
    """Auto-complete expired bookings and free vehicles"""
    from django.db import transaction

    now = timezone.now()
    expired_bookings = Booking.objects.filter(
        status='Approved',
        end_time__lt=now
    ).select_related('vehicle')

    updated = 0
    for booking in expired_bookings:
        changed = False

        # Free the vehicle
        if booking.vehicle and booking.vehicle.status != 'Available':
            booking.vehicle.status = 'Available'
            booking.vehicle.save(update_fields=['status'])
            changed = True

        # Mark booking as Completed (bypass save() method to avoid conflict)
        if booking.status != 'Completed':
            Booking.objects.filter(pk=booking.pk).update(status='Completed')
            changed = True

        if changed:
            updated += 1
            print(f"AUTO-FREED: Booking #{booking.id} | Vehicle: {booking.vehicle} → AVAILABLE")

    if updated:
        print(f"UPDATE_EXPIRED_BOOKINGS: {updated} booking(s) auto-completed at {now}")
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
    
    
    vehicles = Vehicle.objects.filter(status='Available').select_related('assigned_driver')
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
    
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status='Available')  # Only truly Available
    
    if request.method == 'POST':
        form = BookingForm(request.POST)
        if form.is_valid():
            booking = form.save(commit=False)
            booking.employee = request.user
            booking.vehicle = vehicle
            booking.status = 'Pending'

            
            if request.user.role == 'HR':
                booking.priority = 1
            elif request.user.role == 'Manager':
                booking.priority = 2
            else:
                booking.priority = 4

            booking.save()
            vehicle.status = 'Reserved'
            vehicle.save()

            messages.success(request, f"Request submitted! Vehicle is now reserved for approval.")
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
    
   
    available_drivers = Driver.objects.filter(
        status='Active',
        assigned_vehicle__isnull=True
    ).order_by('name')

    for v in vehicles:
        v.is_in_use = v.bookings.filter(status='Approved').exists()
        v.pending_bookings_count = v.bookings.filter(status='Pending').count()

    if request.method == 'POST':
        try:
            with transaction.atomic():
                vehicle = Vehicle.objects.create(
                    model=request.POST['model'].strip(),
                    vehicle_number=request.POST['vehicle_number'].strip().upper(),
                    capacity=int(request.POST['capacity']),
                    status='Available'
                )

                driver_id = request.POST.get('assigned_driver')
                if driver_id:
                    driver = get_object_or_404(
                        Driver,
                        id=driver_id,
                        status='Active',
                        assigned_vehicle__isnull=True
                    )
                    driver.assigned_vehicle = vehicle
                    driver.save()
                    messages.success(request, f'Vehicle added and assigned to {driver.name}')
                else:
                    messages.success(request, 'Vehicle added successfully')

        except Exception as e:
            messages.error(request, f'Error: {e}')
        return redirect('admin_vehicles')
    
    return render(request, 'admin/vehicles.html', {
        'vehicles': vehicles,
        'drivers': available_drivers
    })


@login_required
def edit_vehicle(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    vehicle = get_object_or_404(Vehicle, pk=pk)

    try:
        current_driver = vehicle.assigned_driver  
    except Driver.DoesNotExist:
        current_driver = None
    available_drivers = Driver.objects.filter(
        status='Active',
        assigned_vehicle__isnull=True
    )
    if current_driver:
        available_drivers = available_drivers | Driver.objects.filter(id=current_driver.id)
    available_drivers = available_drivers.distinct().order_by('name')

    if request.method == 'POST':
        try:
            with transaction.atomic():
               
                vehicle.model = request.POST['model'].strip()
                vehicle.vehicle_number = request.POST['vehicle_number'].strip().upper()
                vehicle.capacity = int(request.POST['capacity'])

                
 
                # In edit_vehicle POST
                new_status = request.POST.get('status')
                if new_status in ['Available', 'Maintenance']:
                   if new_status == 'Available' and vehicle.bookings.filter(status='Approved').exists():
                      messages.error(request, "Cannot set to Available — vehicle is in use!")
                else:
                   vehicle.status = new_status
                   vehicle.save()

              
                driver_id = request.POST.get('assigned_driver')
                
                if driver_id:
                    driver_id = int(driver_id)
                    new_driver = get_object_or_404(Driver, id=driver_id, status='Active')
                    
                    
                    if new_driver.assigned_vehicle and new_driver.assigned_vehicle != vehicle:
                        messages.error(request, f'Driver {new_driver.name} is already assigned to another vehicle.')
                        return redirect('admin_vehicles')
                    
                    
                    if current_driver and current_driver != new_driver:
                        current_driver.assigned_vehicle = None
                        current_driver.save()
                    
                   
                    new_driver.assigned_vehicle = vehicle
                    new_driver.save()
                    
                else:
                    
                    if current_driver:
                        current_driver.assigned_vehicle = None
                        current_driver.save()

                vehicle.save()
                messages.success(request, f'Vehicle "{vehicle.model}" updated successfully.')
                
        except ValueError:
            messages.error(request, 'Invalid capacity value.')
        except Exception as e:
            messages.error(request, f'Update failed: {str(e)}')
        
        return redirect('admin_vehicles')

    
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
    
   
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        messages.error(request, "You don't have permission to delete vehicles.")
        return redirect('admin_vehicles')
    
    vehicle = get_object_or_404(Vehicle, pk=pk)
    
    if request.method == 'POST':
        try:
            with transaction.atomic():
                vehicle_name = f"{vehicle.model} ({vehicle.vehicle_number})"
                
                
                if hasattr(vehicle, 'assigned_driver') and vehicle.assigned_driver:
                    driver = vehicle.assigned_driver
                    driver.assigned_vehicle = None
                    driver.save()
                
                
                pending_count = vehicle.bookings.filter(status='Pending').count()
                vehicle.bookings.filter(status='Pending').update(status='Cancelled')
                
                vehicle.delete()
                
                messages.success(
                    request,
                    f'Vehicle "{vehicle_name}" deleted successfully. '
                    f'{pending_count} pending booking(s) cancelled.'
                )
        except Exception as e:
            messages.error(request, f'Error deleting vehicle: {e}')
        
        return redirect('admin_vehicles')
    
    
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
        with transaction.atomic():
            booking.status = 'Approved'
            booking.approved_by = request.user
            booking.approved_at = timezone.now()
            booking.save()
            vehicle.status = 'Booked'
            vehicle.save()
        messages.success(request, f'Approved! {vehicle.model} assigned.')
    return redirect('admin_bookings')

@login_required
def reject_booking(request, pk):
    update_expired_bookings()
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    if request.method == 'POST':
        with transaction.atomic():
            booking.status = 'Rejected'
            booking.save()
            booking.vehicle.status = 'Available'
            booking.vehicle.save()
        messages.success(request, 'Booking rejected. Vehicle is now available.')
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