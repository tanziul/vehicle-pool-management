from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q

from django.utils.timezone import localtime
from .models import User, Driver, Vehicle, Booking, TripReport
from .forms import BookingForm   





@login_required
def profile(request):
    user = request.user

    if request.method == 'POST':
        if 'profile_picture' in request.FILES and (user.role == 'Admin' or user.is_superuser):
            user.profile_picture = request.FILES['profile_picture']
            user.save()
            messages.success(request, "Profile picture updated successfully!")
        return redirect('profile')

    context = {
        'total_bookings_made': user.bookings_made.count(),
        'pending_bookings_made': user.bookings_made.filter(status='Pending').count(),
        'completed_bookings_made': user.bookings_made.filter(status='Completed').count(),
        'recent_bookings': user.bookings_made.select_related('vehicle').order_by('-created_at')[:8],
    }

    if user.role == 'Admin' or user.is_superuser:
        context['bookings_approved'] = user.approved_bookings.count()
        context['total_vehicles_managed'] = Vehicle.objects.count()

    context.update(get_notifications(request))  # Added notifications
    return render(request, 'profile.html', context)

# SEARCH FUNCTION — FIXED
def search_queryset(queryset, fields, q):
    if not q:
        return queryset
    query = Q()
    for field in fields:
        query |= Q(**{f"{field}__icontains": q})
    return queryset.filter(query)

# AUTO UPDATE EXPIRED BOOKINGS 
def update_expired_bookings():
    """Auto-release vehicles and mark bookings as completed when end_time passes"""
    now = timezone.now()
    expired = Booking.objects.filter(
        status='Approved', 
        end_time__lt=now
    ).select_related('vehicle')
    
    for booking in expired:
        if booking.vehicle and booking.vehicle.status != 'Available':
            booking.vehicle.status = 'Available'
            booking.vehicle.save(update_fields=['status'])
        
        if booking.status != 'Completed':
            booking.status = 'Completed'
            booking.save()
        
        # Create TripReport if it doesn't exist
        if not hasattr(booking, 'trip_report'):
            TripReport.objects.create(
                booking=booking,
                completed_at=now
            )

# ====================== NOTIFICATIONS ======================
def get_notifications(request):
    notifications = []
    count = 0
    
    if request.user.is_staff:  # Admin sees pending requests
        pending = Booking.objects.filter(status='Pending').select_related('employee', 'vehicle')[:10]
        for b in pending:
            notifications.append({
                'type': 'pending',
                'message': f"{b.employee.get_full_name() or b.employee.username} requested {b.vehicle.model}",
                'time': localtime(b.created_at).strftime("%b %d, %H:%M"),
                'link': '/admin/bookings/'
            })
        count = pending.count()
    else:  # Employee sees approved/rejected from last 7 days
        recent_cutoff = timezone.now() - timezone.timedelta(days=7)
        recent = Booking.objects.filter(
            employee=request.user,
            status__in=['Approved', 'Rejected'],
            approved_at__gte=recent_cutoff
        ).select_related('vehicle')[:10]
        for b in recent:
            status_text = "approved" if b.status == 'Approved' else "rejected"
            notifications.append({
                'type': 'approved' if b.status == 'Approved' else 'rejected',
                'message': f"Your booking for {b.vehicle.model} was {status_text}",
                'time': localtime(b.approved_at).strftime("%b %d, %H:%M"),
                'link': '/user/bookings/'
            })
        count = recent.count()
    
    return {'notifications': notifications, 'notification_count': count}

# ====================== AUTH ======================
def home(request):
    return render(request, 'home.html')

def login_view(request):
    if request.method == 'POST':
        user = authenticate(request, username=request.POST['username'], password=request.POST['password'])
        if user and user.is_active:
            login(request, user)
            return redirect('dashboard')
        messages.error(request, 'Invalid credentials.')
    return render(request, 'home.html')

@login_required
def logout_view(request):
    logout(request)

    list(messages.get_messages(request))  
    messages.success(request, 'Logged out successfully.')
    return redirect('home')
@login_required
def dashboard(request):
    update_expired_bookings()
    if request.user.is_superuser or request.user.role == 'Admin':
        return redirect('admin_dashboard')
    elif request.user.role in ['Employee', 'Manager', 'HR']:
        return redirect('user_dashboard')
    return redirect('home')


# ====================== USER VIEWS ======================
@login_required
def user_dashboard(request):
    update_expired_bookings()
    if request.user.role not in ['Employee', 'Manager', 'HR']:
        return redirect('dashboard')

    vehicles = Vehicle.objects.filter(status='Available').select_related('assigned_driver')
    context = {'vehicles': vehicles}
    context.update(get_notifications(request))
    return render(request, 'user/dashboard.html', context)

@login_required
def user_bookings(request):
    update_expired_bookings()
    bookings = Booking.objects.filter(employee=request.user).select_related('vehicle').order_by('-created_at')
    q = request.GET.get('q', '').strip()
    if q:
        bookings = search_queryset(bookings, [
            'vehicle__model', 'vehicle__vehicle_number', 'destination', 'purpose'
        ], q)
    context = {'bookings': bookings}
    context.update(get_notifications(request))
    return render(request, 'user/bookings.html', context)

@login_required
def request_vehicle(request, vehicle_id):
    update_expired_bookings()
    vehicle = get_object_or_404(Vehicle, id=vehicle_id, status='Available')
    
    form = BookingForm(request.POST or None)
    
    if request.method == 'POST':
        if form.is_valid():
            booking = form.save(commit=False)
            booking.employee = request.user
            booking.vehicle = vehicle
            booking.status = 'Pending'
            booking.priority = 1 if request.user.role == 'HR' else 2 if request.user.role == 'Manager' else 4
            booking.save()
            vehicle.status = 'Reserved'
            vehicle.save()
            messages.success(request, "Request submitted successfully!")
            return redirect('user_dashboard')
    
    vehicles = Vehicle.objects.filter(status='Available').select_related('assigned_driver')
    context = {
        'vehicles': vehicles,
        'form': form,
        'modal_vehicle_id': vehicle_id if form.is_bound and not form.is_valid() else None
    }
    context.update(get_notifications(request))
    return render(request, 'user/dashboard.html', context)


@login_required
def admin_dashboard(request):
    update_expired_bookings()
    
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    
    now = timezone.now()
    today = now.date()
    
    # 1. Trips This Month - KEPT YOUR ORIGINAL LOOP (as requested)
    completed_this_month = 0
    for booking in Booking.objects.filter(status='Completed'):
        if booking.end_time.year == now.year and booking.end_time.month == now.month:
            completed_this_month += 1
    
    # 2. Approved Today
    import datetime
    from django.utils.timezone import make_aware
    
    today_start = make_aware(datetime.datetime.combine(today, datetime.datetime.min.time()))
    today_end = make_aware(datetime.datetime.combine(today, datetime.datetime.max.time()))
    
    approved_today_count = Booking.objects.filter(
        status='Approved',
        approved_at__isnull=False,
        approved_at__gte=today_start,
        approved_at__lte=today_end
    ).count()
    
    stats = {
        'total_vehicles': Vehicle.objects.count(),
        'available_vehicles': Vehicle.objects.filter(status='Available').count(),
        'booked_vehicles': Vehicle.objects.filter(status='Booked').count(),
        'maintenance_vehicles': Vehicle.objects.filter(status='Maintenance').count(),
        'total_drivers': Driver.objects.count(),
        'active_drivers': Driver.objects.filter(status='Active').count(),
        'pending_requests': Booking.objects.filter(status='Pending').count(),
        'completed_this_month': completed_this_month,
        'approved_today': approved_today_count,
        'total_completed': Booking.objects.filter(status='Completed').count(),
    }
    
    stats['inactive_drivers'] = stats['total_drivers'] - stats['active_drivers']
    stats['pending_bookings'] = Booking.objects.filter(
        status='Pending'
    ).select_related('employee', 'vehicle').order_by('-created_at')[:10]
    
    stats['today'] = now
    
    stats.update(get_notifications(request))  # Added notifications
    return render(request, 'admin/dashboard.html', stats)


@login_required
def admin_bookings(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')

    bookings = Booking.objects.select_related('employee', 'vehicle', 'approved_by').all().order_by('-priority', 'start_time')
    q = request.GET.get('q', '').strip()
    if q:
        bookings = search_queryset(bookings, [
            'employee__first_name', 'employee__last_name', 'employee__username',
            'vehicle__model', 'vehicle__vehicle_number', 'destination', 'purpose'
        ], q)
    status_filter = request.GET.get('status', '')
    if status_filter:
        if status_filter == 'Completed Trips':
            bookings = bookings.filter(status='Completed')
        elif status_filter in ['Pending', 'Approved']:
            bookings = bookings.filter(status=status_filter)
    available_vehicles = Vehicle.objects.filter(status='Available').select_related('assigned_driver')
    context = {'bookings': bookings, 'vehicles': available_vehicles, 'now': timezone.now()}
    context.update(get_notifications(request))
    return render(request, 'admin/bookings.html', context)

@login_required
def admin_vehicles(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    vehicles = Vehicle.objects.select_related('assigned_driver', 'last_assigned_driver').all()
    q = request.GET.get('q', '').strip()
    if q:
        vehicles = search_queryset(vehicles, ['model', 'vehicle_number', 'assigned_driver__name'], q)
    status_filter = request.GET.get('status', '')
    if status_filter:
        vehicles = vehicles.filter(status=status_filter)
    vehicles = vehicles.order_by('-id')
    drivers = Driver.objects.filter(status='Active', assigned_vehicle__isnull=True)

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
                    driver = get_object_or_404(Driver, id=driver_id)
                    driver.assigned_vehicle = vehicle
                    driver.save()
                messages.success(request, "Vehicle added!")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('admin_vehicles')

    context = {'vehicles': vehicles, 'drivers': drivers}
    context.update(get_notifications(request))
    return render(request, 'admin/vehicles.html', context)

@login_required
def edit_vehicle(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')

    vehicle = get_object_or_404(Vehicle, pk=pk)
    drivers = Driver.objects.filter(status='Active')

    if request.method == 'POST':
        try:
            with transaction.atomic():
               
                vehicle.model = request.POST['model'].strip()
                vehicle.vehicle_number = request.POST['vehicle_number'].strip().upper()
                vehicle.capacity = int(request.POST['capacity'])
                new_status = request.POST['status']

         
                driver_id = request.POST.get('assigned_driver', '')

                
                current_driver = vehicle.assigned_driver if hasattr(vehicle, 'assigned_driver') else None

              
                if not driver_id:
                    if current_driver:
                        current_driver.assigned_vehicle = None
                        current_driver.save(update_fields=['assigned_vehicle'])

                
                else:
                    new_driver = get_object_or_404(Driver, id=int(driver_id), status='Active')

                    if new_driver.assigned_vehicle and new_driver.assigned_vehicle != vehicle:
                        messages.error(request, f"Driver {new_driver.name} is already assigned to another vehicle!")
                        return redirect('admin_vehicles')

                   
                    if current_driver and current_driver != new_driver:
                        current_driver.assigned_vehicle = None
                        current_driver.save(update_fields=['assigned_vehicle'])

                    
                    new_driver.assigned_vehicle = vehicle
                    new_driver.save(update_fields=['assigned_vehicle'])

               
                if new_status in ['Maintenance', 'Out of Service'] and current_driver:
                    vehicle.last_assigned_driver = current_driver
                    current_driver.assigned_vehicle = None
                    current_driver.save(update_fields=['assigned_vehicle'])

                vehicle.status = new_status
                vehicle.save()

                messages.success(request, "Vehicle updated successfully!")
        except Exception as e:
            messages.error(request, f"Error: {str(e)}")

        return redirect('admin_vehicles')

    return redirect('admin_vehicles')

@login_required
def admin_drivers(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')

    drivers = Driver.objects.select_related('assigned_vehicle').all()
    q = request.GET.get('q', '').strip()
    if q:
        drivers = search_queryset(drivers, ['name', 'license_no', 'phone'], q)
    drivers = drivers.order_by('-status', 'name')

    # ADD DRIVER
    if request.method == 'POST' and 'add_driver' in request.POST:
        try:
            Driver.objects.create(
                name=request.POST['name'].strip(),
                phone=request.POST['phone'].strip(),
                license_no=request.POST['license_no'].strip(),
                status=request.POST.get('status', 'Active')
            )
            messages.success(request, "Driver added!")
        except Exception as e:
            messages.error(request, f"Error: {e}")

    # EDIT DRIVER
    if request.method == 'POST' and 'edit_driver' in request.POST:
        driver = get_object_or_404(Driver, id=request.POST['driver_id'])
        driver.name = request.POST['name'].strip()
        driver.phone = request.POST['phone'].strip()
        driver.license_no = request.POST['license_no'].strip()
        driver.status = request.POST['status']
        driver.save()
        messages.success(request, "Driver updated!")

    context = {'drivers': drivers}
    context.update(get_notifications(request))
    return render(request, 'admin/drivers.html', context)

@login_required
def admin_users(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')

    users = User.objects.all().order_by('-is_active', 'role', 'username')
    q = request.GET.get('q', '').strip()
    if q:
        users = search_queryset(users, ['username', 'first_name', 'last_name', 'email'], q)

    # === EDIT EXISTING USER ===
    if request.method == 'POST' and 'edit_user' in request.POST:
        user = get_object_or_404(User, id=request.POST['user_id'])
        user.username = request.POST['username'].strip()
        user.email = request.POST.get('email', '')
        user.first_name = request.POST.get('first_name', '')
        user.last_name = request.POST.get('last_name', '')
        user.role = request.POST['role']
        user.is_active = 'is_active' in request.POST

        # Handle profile picture upload
        if 'profile_picture' in request.FILES:
            user.profile_picture = request.FILES['profile_picture']

        if request.POST.get('password'):
            user.set_password(request.POST['password'])
        
        user.save()
        messages.success(request, f"User '{user.username}' updated successfully!")
        return redirect('admin_users')

    # === ADD NEW USER ===
    if request.method == 'POST' and 'add_user' in request.POST:
        try:
            user = User.objects.create_user(
                username=request.POST['username'].strip(),
                password=request.POST['password'],
                email=request.POST.get('email', ''),
                first_name=request.POST.get('first_name', ''),
                last_name=request.POST.get('last_name', ''),
                role=request.POST['role'],
                is_active=True
            )
            
            # Handle profile picture upload
            if 'profile_picture' in request.FILES:
                user.profile_picture = request.FILES['profile_picture']
                user.save()
            
            messages.success(request, f"User '{user.username}' created successfully!")
        except Exception as e:
            messages.error(request, f"Error creating user: {e}")
        return redirect('admin_users')

    context = {'users': users, 'ROLE_CHOICES': User.ROLE_CHOICES}
    context.update(get_notifications(request))
    return render(request, 'admin/users.html', context)

@login_required
def reports(request):
    if not request.user.is_staff:
        messages.error(request, "Access denied.")
        return redirect('user_bookings')

    reports = TripReport.objects.select_related(
        'booking__employee', 'booking__vehicle', 'booking__vehicle__assigned_driver'
    ).order_by('-completed_at')

    q = request.GET.get('q', '').strip()
    if q:
        reports = search_queryset(reports, [
            'booking__employee__first_name', 'booking__employee__last_name', 'booking__employee__username',
            'booking__vehicle__model', 'booking__vehicle__vehicle_number', 'booking__destination', 'booking__purpose'
        ], q)

    context = {'reports': reports}
    context.update(get_notifications(request))
    return render(request, 'reports.html', context)

@login_required
def approve_booking(request, pk):
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    if request.method == 'POST':
        try:
            booking.status = 'Approved'
            booking.approved_by = request.user
            booking.approved_at = timezone.now()
            booking.save()
            booking.vehicle.status = 'Booked'
            booking.vehicle.save()
            messages.success(request, f"Booking approved for {booking.employee.get_full_name() or booking.employee.username}!")
        except Exception as e:
            messages.error(request, f"Error approving booking: {e}")
    return redirect('admin_dashboard') 

@login_required
def reject_booking(request, pk):
    update_expired_bookings()
    booking = get_object_or_404(Booking, pk=pk, status='Pending')
    if request.method == 'POST':
        booking.status = 'Rejected'
        booking.save()
        booking.vehicle.status = 'Available'
        booking.vehicle.save()
        messages.success(request, f"Booking rejected for {booking.employee.get_full_name() or booking.employee.username}!")
    return redirect('admin_bookings')


@login_required
def cancel_booking(request, pk):
    update_expired_bookings()
    booking = get_object_or_404(Booking, pk=pk, employee=request.user, status='Pending')
    if request.method == 'POST':
        booking.status = 'Cancelled'
        booking.save()
        booking.vehicle.status = 'Available'
        booking.vehicle.save()
        messages.success(request, "Booking cancelled successfully!")
        return redirect('user_bookings')
    return redirect('user_bookings')