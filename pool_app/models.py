from django.db import models
from django.contrib.auth.models import AbstractUser

class User(AbstractUser):
    ROLE_CHOICES = [
        ('Admin', 'Admin'), ('Manager', 'Manager'), ('HR', 'HR'),
        ('Employee', 'Employee'), ('Driver', 'Driver')
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Employee')

    groups = models.ManyToManyField('auth.Group', related_name='pool_user_groups', blank=True)
    user_permissions = models.ManyToManyField('auth.Permission', related_name='pool_user_perms', blank=True)

    def __str__(self):
        return f"{self.get_full_name()} ({self.role})"

    def save(self, *args, **kwargs):
        if self.role == 'Driver':
            self.is_active = False
        super().save(*args, **kwargs)


class Vehicle(models.Model):
    vehicle_number = models.CharField(max_length=20, unique=True)
    model = models.CharField(max_length=50)
    capacity = models.IntegerField()
    status = models.CharField(max_length=20, choices=[
        ('Available', 'Available'), ('Booked', 'Booked'), ('Maintenance', 'Maintenance')
    ], default='Available')
    driver = models.OneToOneField(User, on_delete=models.SET_NULL, null=True, blank=True,
                                  limit_choices_to={'role': 'Driver'}, related_name='vehicle')

    def __str__(self):
        return f"{self.model} ({self.vehicle_number})"


class Booking(models.Model):
    PRIORITY_CHOICES = [('High', 'High'), ('Medium', 'Medium'), ('Low', 'Low')]
    STATUS_CHOICES = [('Pending', 'Pending'), ('Approved', 'Approved'), ('Completed', 'Completed'), ('Rejected', 'Rejected')]

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, blank=True)
    destination = models.CharField(max_length=200)
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    reason = models.TextField()
    priority = models.CharField(max_length=10, choices=PRIORITY_CHOICES, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
    approved_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='approved')
    created_at = models.DateTimeField(auto_now_add=True)

    def save(self, *args, **kwargs):
        if not self.priority:
            p = {'Admin': 'High', 'Manager': 'High', 'HR': 'Medium', 'Employee': 'Low'}
            self.priority = p.get(self.employee.role, 'Low')
        super().save(*args, **kwargs)


class TripReport(models.Model):
    booking = models.OneToOneField(Booking, on_delete=models.CASCADE)
    distance = models.FloatField()
    fuel_used = models.FloatField()
    notes = models.TextField(blank=True)
    completed_at = models.DateTimeField(auto_now_add=True)