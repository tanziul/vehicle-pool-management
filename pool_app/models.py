# pool_app/models.py
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils import timezone
import threading
from urllib.parse import quote


class User(AbstractUser):
    ROLE_CHOICES = [
        ('Employee', 'Employee'),
        ('Manager', 'Manager'),
        ('HR', 'HR'),
        ('Admin', 'Admin'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='Employee')
    profile_picture = models.ImageField(
        upload_to='profile_pictures/',
        null=True,
        blank=True,
    )
    
    def get_profile_picture_url(self):
        """Return profile picture URL or default avatar URL"""
        if self.profile_picture and hasattr(self.profile_picture, 'url'):
            return self.profile_picture.url
        return '/static/pool_app/image/default_avatar.png'
    
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
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Available')  # Fixed typo from 'vailable'
    photo = models.ImageField(
        upload_to='vehicle_photos/',
        null=True,
        blank=True,
    )

    last_assigned_driver = models.ForeignKey(
        'Driver',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='previously_assigned_vehicles',
        help_text="Shows previous driver when vehicle is Out of Service"
    )

    def get_photo_url(self):
        """Return photo URL or default avatar URL"""
        if self.photo and hasattr(self.photo, 'url'):
            return self.photo.url
        return f"https://ui-avatars.com/api/?name={quote(self.model)}&background=3b82f6&color=fff&size=100"

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
    photo = models.ImageField(
        upload_to='driver_photos/',
        null=True,
        blank=True,
    )


    assigned_vehicle = models.OneToOneField(
        'Vehicle',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='assigned_driver'
    )

    def get_photo_url(self):
        """Return photo URL or default avatar URL"""
        if self.photo and hasattr(self.photo, 'url'):
            return self.photo.url
        return f"https://ui-avatars.com/api/?name={quote(self.name)}&background=10b981&color=fff&size=100"

    def __str__(self):
        return self.name
    
    
class Booking(models.Model):
    STATUS_CHOICES = [
        ('Pending', 'Pending'),
        ('Approved', 'Approved'),
        ('Rejected', 'Rejected'),
        ('Cancelled', 'Cancelled'),
        ('Completed', 'Completed'),
    ]
    PRIORITY_CHOICES = [(1, '1'), (2, '2'), (3, '3'), (4, '4'), (5, '5')]

    employee = models.ForeignKey(User, on_delete=models.CASCADE, related_name='bookings_made')
    vehicle = models.ForeignKey(Vehicle, on_delete=models.SET_NULL, null=True, related_name='bookings')
    destination = models.CharField(max_length=200)
    purpose = models.TextField()
    start_time = models.DateTimeField()
    end_time = models.DateTimeField()
    priority = models.IntegerField(choices=PRIORITY_CHOICES, default=3)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='Pending')
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
                becoming_rejected = (old.status != 'Rejected' and self.status == 'Rejected')
                becoming_pending = (old.status != 'Pending' and self.status == 'Pending')
            except Booking.DoesNotExist:
                becoming_approved = (self.status == 'Approved')
                becoming_rejected = (self.status == 'Rejected')
                becoming_pending = (self.status == 'Pending')
        else:
            becoming_approved = (self.status == 'Approved')
            becoming_rejected = (self.status == 'Rejected')
            becoming_pending = (self.status == 'Pending')

        if becoming_approved and self.vehicle:
            if self.vehicle.status != 'Booked':
                self.vehicle.status = 'Booked'
                self.vehicle.save(update_fields=['status'])

        super().save(*args, **kwargs)

        # Notifications after saving
        if becoming_pending:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            admins = User.objects.filter(is_staff=True)
            for admin in admins:
                Notification.objects.create(
                    user=admin,
                    booking=self,
                    type='pending'
                )
        elif becoming_approved:
            Notification.objects.create(
                user=self.employee,
                booking=self,
                type='approved'
            )
        elif becoming_rejected:
            Notification.objects.create(
                user=self.employee,
                booking=self,
                type='rejected'
            )

    

class TripReport(models.Model):
    booking = models.OneToOneField(
        Booking,
        on_delete=models.CASCADE,
        related_name='trip_report'
    )
    completed_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-completed_at']

    def save(self, *args, **kwargs):
        if not self.completed_at:
            self.completed_at = self.booking.end_time  # Use actual trip end time
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Trip Report - {self.booking.vehicle} - {self.booking.employee} - {self.completed_at.date()}"


class Notification(models.Model):
    TYPE_CHOICES = [
        ('pending', 'Pending'),
        ('approved', 'Approved'),
        ('rejected', 'Rejected'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='notifications')
    booking = models.ForeignKey(Booking, on_delete=models.CASCADE, related_name='notifications')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES)
    read = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.type} notification for {self.user.username} - {self.booking.vehicle}"

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