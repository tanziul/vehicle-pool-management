# pool_app/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import threading
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import threading


class User(AbstractUser):
    ROLE_CHOICES = [
        ('Employee', 'Employee'),
        ('Manager', 'Manager'),
        ('HR', 'HR'),
        ('Admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Employee')

    def __str__(self):
        return self.get_full_name() or self.username


class Vehicle(models.Model):
    STATUS_CHOICES = [
        ('Available', 'Available'),
        ('Reserved', 'Reserved'),        
        ('Booked', 'Booked'),
        ('Maintenance', 'Maintenance'),
        ('Out of Service', 'Out of Service'),
    ]
    model = models.CharField(max_length=100)
    vehicle_number = models.CharField(max_length=20, unique=True)
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')

    # FIXED: Use string 'Driver' to avoid circular import
    last_assigned_driver = models.ForeignKey(
        'Driver',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previously_assigned_vehicles',
        help_text="Shows previous driver when vehicle is Out of Service"
    )

    def __str__(self):
        return f"{self.model} ({self.vehicle_number})"


class Driver(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    license_no = models.CharField(max_length=50, unique=True)
    status = models.CharField(
        max_length=20,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Active'
    )

    # FIXED: Use string 'Vehicle' to break circular import
    assigned_vehicle = models.OneToOneField(
        'Vehicle',  
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_driver'
    )

    def __str__(self):
        return self.name
    
    
class Booking(models.Model):
    PRIORITY_CHOICES = [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')]

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_made')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, related_name='bookings')
    destination = models.CharField(max_length=200)
     
    purpose = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3)
    status = models.CharField(max_length=20, default='Pending')
    approved_by = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_bookings'
    )
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} → {self.vehicle}"

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        """
        ONLY set vehicle to 'Booked' when status CHANGES TO 'Approved'
        Never touch vehicle when status becomes 'Completed'
        """
       
        if self.pk:
            try:
                old = Booking.objects.get(pk=self.pk)
                becoming_approved = (old.status != 'Approved' and self.status == 'Approved')
            except Booking.DoesNotExist:
                becoming_approved = (self.status == 'Approved')
        else:
            becoming_approved = (self.status == 'Approved')

       
        if becoming_approved and self.vehicle:
            if self.vehicle.status != 'Booked':
                self.vehicle.status = 'Booked'
                self.vehicle.save(update_fields=['status'])

        super().save(*args, **kwargs)

    


class TripReport(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE, related_name='trip_report')
    start_odometer = models.PositiveIntegerField()
    end_odometer = models.PositiveIntegerField()
    fuel_used = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trip Report for {self.booking}"

    class Meta:
        verbose_name_plural = "Trip Reports"


# AUTO-RELEASE VEHICLE AFTER END_TIME
def _release_vehicle_after_delay(booking_id):
    def run_release():
        from .models import Booking
        try:
            booking = Booking.objects.select_related('vehicle').get(id=booking_id)
            if booking.end_time <= timezone.now() and booking.vehicle:
                booking.vehicle.status = 'Available'
                booking.vehicle.save(update_fields=['status'])
                booking.status = 'Completed'
                booking.save(update_fields=['status'])
        except Booking.DoesNotExist:
            pass

    try:
        booking = Booking.objects.get(id=booking_id)
        if booking.end_time and booking.end_time > timezone.now():
            delay = (booking.end_time - timezone.now()).total_seconds()
            timer = threading.Timer(delay, run_release)
            timer.daemon = True
            timer.start()
    except Booking.DoesNotExist:
        pass

