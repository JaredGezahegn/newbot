from django.contrib import admin
from django.urls import path
from bot.views import webhook, test

urlpatterns = [
    path("", test),
    path("admin/", admin.site.urls),
    path("webhook/", webhook),
    path("test/", test),
]
