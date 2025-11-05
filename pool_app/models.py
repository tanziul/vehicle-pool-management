from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('Admin', 'Admin'),
        ('Manager', 'Manager'),
        ('HR', 'HR'),
        ('Employee', 'Employee'),
        ('Driver', 'Driver'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Employee')

    groups = models.ManyToManyField(
        'auth.Group', related_name='pool_app_user_set', blank=True
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission', related_name='pool_app_user_permissions_set', blank=True
    )

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

class Vehicle(models.Model):
    vehicle_number = models.CharField(max_length=20, unique=True)
    model = models.CharField(max_length=50)
    capacity = models.IntegerField()
    status = models.CharField(
        max_length=20,
        choices=[('Available', 'Available'), ('Booked', 'Booked'), ('Maintenance', 'Maintenance')],
        default='Available'
    )
    driver = models.OneToOneField(
        User, on_delete=models.SET_NULL, null=True, blank=True,
        limit_choices_to={'role': 'Driver'}
    )

    def __str__(self):
        return f"{self.vehicle_number} - {self.model}"

class Booking(models.Model):
    PRIORITY_CHOICES = [('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')]
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Completed', 'Completed'),
        ('Rejected', 'Rejected')
    ]

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    destination = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reason = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True)
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved_bookings')
    created_at = models.DateTimeField(auto_now_add=True)
    fuel_receipt = models.FileField(upload_to='receipts/', null=True, blank=True)

    class Meta:
        ordering = ['-priority', 'start_time']

    def save(self, *args, **kwargs):
        if not self.priority:
            role_priority = {'Admin': 'High', 'Manager': 'High', 'HR': 'Medium', 'Employee': 'Low'}
            self.priority = role_priority.get(self.employee.role, 'Low')
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.employee} → {self.destination}"

class TripReport(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    distance = models.FloatField(help_text="Distance in KM")
    fuel_used = models.FloatField(help_text="Fuel in liters")
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Trip Report - {self.booking}"