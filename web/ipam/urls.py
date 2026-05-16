from django.urls import path

from . import views

app_name = "ipam"

urlpatterns = [
    path("", views.index, name="index"),
    path("pool/<int:pool_id>/", views.pool_detail, name="pool_detail"),
    path("pool/<int:pool_id>/assign/new/", views.assignment_new, name="assignment_new"),
    path("assignment/<int:assignment_id>/edit/", views.assignment_edit, name="assignment_edit"),
    path("customers/", views.customer_list, name="customer_list"),
    path("customer/<int:customer_id>/", views.customer_detail, name="customer_detail"),
]
