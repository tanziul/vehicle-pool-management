from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    path('user/', views.user_dashboard, name='user_dashboard'),
    path('user/bookings/', views.user_bookings, name='user_bookings'),
    path('user/reports/', views.user_reports, name='user_reports'),
    path('request/<int:vehicle_id>/', views.request_vehicle, name='request_vehicle'),

    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/bookings/', views.admin_bookings, name='admin_bookings'),
    path('admin/vehicles/', views.admin_vehicles, name='admin_vehicles'),
    path('admin/vehicles/edit/<int:pk>/', views.edit_vehicle, name='edit_vehicle'),
    path('admin/drivers/', views.admin_drivers, name='admin_drivers'),
    path('admin/users/', views.admin_users, name='admin_users'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),

    path('admin/bookings/approve/<int:pk>/', views.approve_booking, name='approve_booking'),
    path('admin/bookings/reject/<int:pk>/', views.reject_booking, name='reject_booking'),
    path('admin/bookings/complete/<int:pk>/', views.complete_trip, name='complete_trip'),
]