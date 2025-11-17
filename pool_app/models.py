# pool_app/models.py
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
        ('Booked', 'Booked'),
        ('Maintenance', 'Maintenance'),
    ]
    model = models.CharField(max_length=100)
    vehicle_number = models.CharField(max_length=20, unique=True)
    capacity = models.PositiveIntegerField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')

    assigned_driver = models.OneToOneField(
        'Driver',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='driver_assigned_vehicle'
    )

    def __str__(self):
        return f"{self.model} ({self.vehicle_number})"

    class Meta:
        verbose_name_plural = "Vehicles"


class Driver(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    license_no = models.CharField(max_length=50, unique=True)
    status = models.CharField(
        max_length=20,
        choices=[('Active', 'Active'), ('Inactive', 'Inactive')],
        default='Active'
    )

    assigned_vehicle = models.OneToOneField(
        'Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='vehicle_assigned_driver'
    )

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Drivers"


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

    def save(self, *args, **kwargs):
        if self.pk and self.status == 'Approved' and self.vehicle:
            if self.vehicle.status != 'Booked':
                self.vehicle.status = 'Booked'
                self.vehicle.save(update_fields=['status'])
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} → {self.vehicle}"

    class Meta:
        ordering = ['-created_at']


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


from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=Booking)
def schedule_vehicle_auto_release(sender, instance, created, **kwargs):
    if not created and instance.status == 'Approved' and instance.vehicle:
        _release_vehicle_after_delay(instance.id)