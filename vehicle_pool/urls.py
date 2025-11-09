from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # NO admin.site.urls
    path('', include('pool_app.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)