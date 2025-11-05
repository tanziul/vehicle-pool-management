from django.urls import path
from . import views

urlpatterns = [
    path('', views.home, name='home'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register_view, name='register'),
    path('logout/', views.logout_view, name='logout'),
    path('dashboard/', views.dashboard, name='dashboard'),
    path('booking/create/', views.booking_create, name='booking_create'),
    path('employee/dashboard/', views.employee_dashboard, name='employee_dashboard'),
    path('admin/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/assign/<int:pk>/', views.assign_vehicle, name='assign_vehicle'),
    path('admin/complete/<int:pk>/', views.complete_trip, name='complete_trip'),
]