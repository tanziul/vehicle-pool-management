# pool_app/models.py

from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone


class User(AbstractUser):
    """
    Custom User model for employees (Admin, Manager, HR, Employee).
    Drivers are NOT users.
    """
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Manager', 'Manager'),
        ('HR', 'HR'),
        ('Employee', 'Employee'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Employee')

    groups = models.ManyToManyField(
        'auth.Group',
        related_name='pool_user_groups',
        blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        related_name='pool_user_perms',
        blank=True
    )

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"


class Driver(models.Model):
    """
    Driver — NOT a User. No login.
    """
    name = models.CharField(max_length=100)
    phone = models.CharField(max_length=15, unique=True)
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
        related_name='assigned_driver'  # UNIQUE reverse name
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-status', 'name']

    def __str__(self):
        return f"{self.name} ({self.license_no})"


class Vehicle(models.Model):
    """
    Vehicle in the pool.
    One driver via assigned_vehicle → assigned_driver
    """
    vehicle_number = models.CharField(max_length=20, unique=True)
    model = models.CharField(max_length=50)
    capacity = models.IntegerField(help_text="Number of seats")
    status = models.CharField(
           max_length=20,
        choices=[
        ('Available', 'Available'),
        ('Booked', 'Booked'),
        ('Maintenance', 'Maintenance')
    ],
    default='Available'
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['status', 'model']

    def __str__(self):
        return f"{self.model} ({self.vehicle_number})"

    # ACCESS DRIVER VIA: vehicle.assigned_driver
    @property
    def driver(self):
        return self.assigned_driver


class Booking(models.Model):
    PRIORITY_CHOICES = [
        ('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')
    ]
    STATUS_CHOICES = [
        ('Pending', 'Pending'), ('Approved', 'Approved'),
        ('Completed', 'Completed'), ('Rejected', 'Rejected')
    ]

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='bookings',
        limit_choices_to={'role__in': ['Employee', 'Manager', 'HR']}
    )
    vehicle = models.ForeignKey(
        Vehicle,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='bookings'
    )
    destination = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reason = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='approved_bookings',
        limit_choices_to={'role': 'Admin'}
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def save(self, *args, **kwargs):
        if not self.priority:
            priority_map = {
                'Admin': 'High', 'Manager': 'High',
                'HR': 'Medium', 'Employee': 'Low'
            }
            self.priority = priority_map.get(self.employee.role, 'Low')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} → {self.destination}"


class TripReport(models.Model):
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='trip_report'
    )
    distance = models.FloatField(help_text="KM")
    fuel_used = models.FloatField(help_text="Liters")
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def __str__(self):
        return f"Trip: {self.booking} ({self.distance} KM)"
    
    
