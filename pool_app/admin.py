from django.contrib import admin
from .models import User, Vehicle, Booking, TripReport

@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ('username', 'get_full_name', 'email', 'role', 'is_staff')
    list_filter = ('role', 'is_staff')
    search_fields = ('username', 'email', 'first_name', 'last_name')

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('vehicle_number', 'model', 'capacity', 'status', 'driver')
    list_filter = ('status', 'model')
    search_fields = ('vehicle_number', 'model')

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('employee', 'destination', 'start_time', 'status', 'priority', 'vehicle')
    list_filter = ('status', 'priority', 'start_time')
    search_fields = ('employee__username', 'destination')

@admin.register(TripReport)
class TripReportAdmin(admin.ModelAdmin):
    list_display = ('booking', 'distance', 'fuel_used', 'completed_at')
    readonly_fields = ('completed_at',)