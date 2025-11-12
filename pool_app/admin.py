# pool_app/admin.py
from django.contrib import admin
from .models import Vehicle, Driver, Booking, TripReport, User

@admin.register(Vehicle)
class VehicleAdmin(admin.ModelAdmin):
    list_display = ('model', 'vehicle_number', 'capacity', 'status', 'get_driver')
    def get_driver(self, obj):
        return obj.assigned_driver.name if obj.assigned_driver else "—"
    get_driver.short_description = 'Driver'

@admin.register(Driver)
class DriverAdmin(admin.ModelAdmin):
    list_display = ('name', 'phone', 'license_no', 'status', 'get_vehicle')
    def get_vehicle(self, obj):
        return obj.assigned_vehicle if obj.assigned_vehicle else "—"
    get_vehicle.short_description = 'Vehicle'

@admin.register(Booking)
class BookingAdmin(admin.ModelAdmin):
    list_display = ('id', 'employee', 'vehicle', 'start_time', 'status', 'priority')
    list_filter = ('status', 'priority')

@admin.register(TripReport)
class TripReportAdmin(admin.ModelAdmin):
    list_display = ('booking', 'get_distance', 'get_fuel', 'completed_at')
    def get_distance(self, obj):
        return f"{obj.distance_travelled} km" if obj.distance_travelled else "—"
    get_distance.short_description = 'Distance'
    def get_fuel(self, obj):
        return f"{obj.fuel_used} L" if obj.fuel_used else "—"
    get_fuel.short_description = 'Fuel'