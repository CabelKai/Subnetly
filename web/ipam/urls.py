from django.urls import path

from . import views

app_name = "ipam"

urlpatterns = [
    path("", views.index, name="index"),
    path("pool/<int:pool_id>/", views.pool_detail, name="pool_detail"),
    path("pool/<int:pool_id>/assign/new/", views.assignment_new, name="assignment_new"),
    path("assignment/<int:assignment_id>/edit/", views.assignment_edit, name="assignment_edit"),
    path("anwendungen/", views.application_list, name="application_list"),
    path("anwendung/<int:application_id>/", views.application_detail, name="application_detail"),
    path("anwendung/new/", views.application_new, name="application_new"),
    path("anwendung/<int:application_id>/edit/", views.application_edit, name="application_edit"),
]
