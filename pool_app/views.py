from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import authenticate, login, logout, update_session_auth_hash
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from django.db import transaction
from django.db.models import Q
from django.utils.timezone import localtime
from .models import User, Driver, Vehicle, Booking, TripReport, Notification
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

    context.update(get_notifications(request))
    return render(request, 'profile.html', context)

# SEARCH FUNCTION 
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
        

        try:
            booking.trip_report
        except TripReport.DoesNotExist:
            TripReport.objects.create(
                booking=booking,
                completed_at=now
            )

# ====================== NOTIFICATIONS ======================
def get_notifications(request):
    notifications = []
    count = 0

    unread_notifications = Notification.objects.filter(
        user=request.user,
        read=False
    ).select_related('booking__employee', 'booking__vehicle')[:10]

    for notif in unread_notifications:
        if notif.type == 'pending':
            message = f"{notif.booking.employee.get_full_name() or notif.booking.employee.username} requested {notif.booking.vehicle.model}"
            link = '/admin/bookings/'
        elif notif.type == 'approved':
            message = f"Your booking for {notif.booking.vehicle.model} was approved"
            link = '/user/bookings/'
        elif notif.type == 'rejected':
            message = f"Your booking for {notif.booking.vehicle.model} was rejected"
            link = '/user/bookings/'

        notifications.append({
            'type': notif.type,
            'message': message,
            'time': localtime(notif.created_at).strftime("%b %d, %H:%M"),
            'link': link
        })

    count = unread_notifications.count()

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

   
    Notification.objects.filter(
        user=request.user,
        type__in=['approved', 'rejected'],
        read=False
    ).update(read=True)

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
    
    from django.utils.timezone import localtime
    from pytz import utc
    from calendar import monthrange
    from datetime import datetime, time, timedelta

    now = localtime(timezone.now())
    today = now.date()


    today_start_utc = datetime.combine(today, time.min).replace(tzinfo=utc)
    today_end_utc = datetime.combine(today, time.max).replace(tzinfo=utc) + timedelta(microseconds=1)

 
    first_day = today.replace(day=1)
    last_day = today.replace(day=monthrange(today.year, today.month)[1])
    month_start_utc = datetime.combine(first_day, time.min).replace(tzinfo=utc)
    month_end_utc = datetime.combine(last_day, time.max).replace(tzinfo=utc) + timedelta(microseconds=1)

    completed_this_month = TripReport.objects.filter(
        completed_at__gte=month_start_utc,
        completed_at__lt=month_end_utc
    ).count()

    approved_today_count = Booking.objects.filter(
        approved_at__gte=today_start_utc,
        approved_at__lt=today_end_utc
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
    
    stats.update(get_notifications(request))  
    return render(request, 'admin/dashboard.html', stats)


@login_required
def admin_bookings(request):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')

 
    Notification.objects.filter(
        user=request.user,
        type='pending',
        read=False
    ).update(read=True)

    bookings = Booking.objects.select_related('employee', 'vehicle', 'approved_by').all().order_by('-created_at')
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
    drivers_unassigned = Driver.objects.filter(status='Active', assigned_vehicle__isnull=True)
    drivers_all_active = Driver.objects.filter(
        Q(status='Active', assigned_vehicle__isnull=True) | Q(status='Active', id__in=vehicles.values_list('assigned_driver', flat=True))
    ).distinct()

    if request.method == 'POST':
        try:
            with transaction.atomic():
                vehicle = Vehicle.objects.create(
                    model=request.POST['model'].strip(),
                    vehicle_number=request.POST['vehicle_number'].strip().upper(),
                    capacity=int(request.POST['capacity']),
                    status='Available'
                )
                # Handle photo upload
                if 'photo' in request.FILES:
                    vehicle.photo = request.FILES['photo']
                    vehicle.save()
                driver_id = request.POST.get('assigned_driver')
                if driver_id:
                    driver = get_object_or_404(Driver, id=driver_id)
                    driver.assigned_vehicle = vehicle
                    driver.save()
                messages.success(request, "Vehicle added!")
        except Exception as e:
            messages.error(request, f"Error: {e}")
        return redirect('admin_vehicles')

    context = {'vehicles': vehicles, 'drivers_unassigned': drivers_unassigned, 'drivers_all_active': drivers_all_active}
    context.update(get_notifications(request))
    return render(request, 'admin/vehicles.html', context)

@login_required
def edit_vehicle(request, pk):
    update_expired_bookings()
    if not (request.user.is_superuser or request.user.role == 'Admin'):
        return redirect('dashboard')

    vehicle = get_object_or_404(Vehicle, pk=pk)
  
    drivers = Driver.objects.all()

    if request.method == 'POST':
        try:
            with transaction.atomic():
             
                try:
                    current_driver = vehicle.assigned_driver
                except:
                    current_driver = None

                # Update basic vehicle info
                vehicle.model = request.POST['model'].strip()
                vehicle.vehicle_number = request.POST['vehicle_number'].strip().upper()
                vehicle.capacity = int(request.POST['capacity'])
                new_status = request.POST['status']

           
                driver_id = request.POST.get('assigned_driver', '').strip()

               
                if not driver_id:
                    if current_driver:
                        current_driver.assigned_vehicle = None
                        current_driver.save(update_fields=['assigned_vehicle'])

         
                else:
                    new_driver = get_object_or_404(Driver, id=int(driver_id))

                    
                    if new_driver.assigned_vehicle and new_driver.assigned_vehicle != vehicle:
                        messages.error(request, f"Driver {new_driver.name} is already assigned to another vehicle!")
                        return redirect('admin_vehicles')

                  
                    if current_driver and current_driver != new_driver:
                        current_driver.assigned_vehicle = None
                        current_driver.save(update_fields=['assigned_vehicle'])

                    new_driver.assigned_vehicle = vehicle
                    new_driver.save(update_fields=['assigned_vehicle'])

                vehicle.refresh_from_db()

            
                if new_status in ['Maintenance', 'Out of Service']:
                    try:
                        assigned_driver = vehicle.assigned_driver
                        vehicle.last_assigned_driver = assigned_driver
                        assigned_driver.assigned_vehicle = None
                        assigned_driver.save(update_fields=['assigned_vehicle'])
                    except:
                       
                        vehicle.last_assigned_driver = None

                # Handle photo upload
                if 'photo' in request.FILES:
                    vehicle.photo = request.FILES['photo']

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
            driver = Driver.objects.create(
                name=request.POST['name'].strip(),
                phone=request.POST['phone'].strip(),
                license_no=request.POST['license_no'].strip(),
                status=request.POST.get('status', 'Active')
            )
            
            if 'photo' in request.FILES:
                driver.photo = request.FILES['photo']
                driver.save()
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
        # Handle photo upload
        if 'photo' in request.FILES:
            driver.photo = request.FILES['photo']
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
            
            # profile picture upload
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