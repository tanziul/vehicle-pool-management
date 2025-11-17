# pool_app/utils.py
from django.utils import timezone
from .models import Booking

def update_expired_bookings():
    """
    Automatically mark expired Approved bookings as Completed
    and free the vehicle (set status to Available)
    """
    now = timezone.now()
    expired = Booking.objects.filter(
        status='Approved',
        end_time__lt=now
    ).select_related('vehicle')

    for booking in expired:
        if booking.vehicle:
            booking.vehicle.status = 'Available'
            booking.vehicle.save(update_fields=['status'])
        booking.status = 'Completed'
        booking.save(update_fields=['status'])