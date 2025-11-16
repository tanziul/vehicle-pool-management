
from django.urls import path
from . import views

urlpatterns = [
    # === PUBLIC ===
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # === USER DASHBOARD ===
    path('user/', views.user_dashboard, name='user_dashboard'),
    path('user/bookings/', views.user_bookings, name='user_bookings'),
    path('user/reports/', views.user_reports, name='user_reports'),
    path('user/request/<int:vehicle_id>/', views.request_vehicle, name='request_vehicle'),

    # === ADMIN DASHBOARD ===
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/bookings/', views.admin_bookings, name='admin_bookings'),
    path('admin/vehicles/', views.admin_vehicles, name='admin_vehicles'),
    path('admin/vehicles/update-status/<int:pk>/',  views.update_vehicle_status, name='update_vehicle_status'),  
    path('admin/edit-vehicle/<int:pk>/', views.edit_vehicle, name='edit_vehicle'),
    path('admin/vehicles/delete/<int:pk>/', views.delete_vehicle, name='delete_vehicle'),



    # === DRIVERS ===
    path('admin/drivers/', views.admin_drivers, name='admin_drivers'),
    path('admin/drivers/add/', views.add_driver, name='add_driver'),
    path('admin/drivers/edit/<int:pk>/', views.edit_driver, name='edit_driver'),
    path('admin/drivers/delete/<int:pk>/', views.delete_driver, name='delete_driver'),

    # === USERS ===
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/add-user/', views.add_user, name='add_user'),
    path('admin/edit-user/<int:pk>/', views.edit_user, name='edit_user'),
    path('admin/delete-user/<int:pk>/', views.delete_user, name='delete_user'),

    # === BOOKING ACTIONS ===
    path('admin/approve-booking/<int:pk>/', views.approve_booking, name='approve_booking'),
    path('admin/reject-booking/<int:pk>/', views.reject_booking, name='reject_booking'),
    path('admin/complete-trip/<int:pk>/', views.complete_trip, name='complete_trip'),

    # === REPORTS ===
    path('admin/reports/', views.admin_reports, name='admin_reports'),
]