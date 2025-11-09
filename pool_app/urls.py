from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),

    # User
    path('user/', views.user_dashboard, name='user_dashboard'),
    path('user/bookings/', views.user_bookings, name='user_bookings'),
    path('user/reports/', views.user_reports, name='user_reports'),
    path('user/request/<int:vehicle_id>/', views.request_vehicle, name='request_vehicle'),

    # Admin
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/bookings/', views.admin_bookings, name='admin_bookings'),
    path('admin/vehicles/', views.admin_vehicles, name='admin_vehicles'),
    path('admin/drivers/', views.admin_drivers, name='admin_drivers'),
    path('admin/reports/', views.admin_reports, name='admin_reports'),
    path('admin/users/', views.admin_users, name='admin_users'),

    # CRUD
    path('admin/add-user/', views.add_user, name='add_user'),
    path('admin/edit-user/<int:pk>/', views.edit_user, name='edit_user'),
    path('admin/delete-user/<int:pk>/', views.delete_user, name='delete_user'),
    path('admin/approve/<int:pk>/', views.approve_booking, name='approve_booking'),
    path('admin/reject/<int:pk>/', views.reject_booking, name='reject_booking'),
]