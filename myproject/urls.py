"""
URL configuration for myproject project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.0/topics/http/urls/
"""

from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.conf.urls.i18n import i18n_patterns
from django.views.generic import RedirectView

urlpatterns = [
    # مسار تبديل اللغة
    path('i18n/', include('django.conf.urls.i18n')),
    
    # 🔴 الحل الجذري: توجيه تلقائي من الجذر (الرابط الفارغ) إلى اللغة الافتراضية (مثل /ar/)
    path('', RedirectView.as_view(url='/ar/', permanent=False)),
]

# تغليف مسارات المتجر ولوحة التحكم بنظام اللغات
urlpatterns += i18n_patterns(
    path("admin/", admin.site.urls),
    path("", include("products.urls")),
    prefix_default_language=True,
)

# عرض الصور والملفات الثابتة
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)