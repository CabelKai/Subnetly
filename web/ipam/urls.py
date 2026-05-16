from django.urls import path

from . import views

app_name = "ipam"

urlpatterns = [
    path("", views.index, name="index"),
    path("pool/<int:pool_id>/", views.pool_detail, name="pool_detail"),
]
