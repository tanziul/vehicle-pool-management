# pool_app/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser


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

    # ADMIN ASSIGNS DRIVER HERE
    assigned_driver = models.OneToOneField(
        'Driver',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_vehicle'
    )

    def __str__(self):
        return f"{self.model} ({self.vehicle_number})"

    class Meta:
        verbose_name_plural = "Vehicles"


class Driver(models.Model):
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15)
    license_no = models.CharField(max_length=50, unique=True)
    status = models.CharField(max_length=20, choices=[
        ('Active', 'Active'),
        ('Inactive', 'Inactive'),
    ], default='Active')

    def __str__(self):
        return self.name

    class Meta:
        verbose_name_plural = "Drivers"


class Booking(models.Model):
    PRIORITY_CHOICES = [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')]
    employee = models.ForeignKey(User, on_delete=models.CASCADE)
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, related_name='bookings')
    destination = models.CharField(max_length=200)
    purpose = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3)
    status = models.CharField(max_length=20, default='Pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name='approved_bookings')
    approved_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.employee} → {self.vehicle}"

class TripReport(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    start_odometer = models.PositiveIntegerField()
    end_odometer = models.PositiveIntegerField()
    fuel_used = models.DecimalField(max_digits=5, decimal_places=2, null=True, blank=True)
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)