from django.conf import settings
from django.contrib import admin
from django.urls import path, include
from rest_framework import routers
from library import views

router = routers.DefaultRouter()
router.register(r'authors', views.AuthorViewSet, basename='author')
router.register(r'books', views.BookViewSet, basename='book')
router.register(r'members', views.MemberViewSet, basename='member')
router.register(r'loans', views.LoanViewSet, basename='loan')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/', include(router.urls)),
    # Celery task endpoints
    path('api/tasks/overdue-reminders/', views.trigger_overdue_reminders, name='trigger-overdue-reminders'),
    path('api/tasks/monthly-report/', views.trigger_monthly_report, name='trigger-monthly-report'),
    path('api/tasks/inventory-check/', views.trigger_inventory_check, name='trigger-inventory-check'),
    path('api/tasks/fetch-metadata/', views.fetch_metadata, name='fetch-metadata'),
]

# Add debug toolbar URLs in development
if settings.DEBUG:
    import debug_toolbar
    urlpatterns = [
        path('__debug__/', include(debug_toolbar.urls)),
    ] + urlpatterns