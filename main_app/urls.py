#main_app/urls.py
from django.urls import path
from . import views

urlpatterns = [
    path("", views.ProgramList.as_view(), name="program_list"),
    path("programs/new/", views.program_new, name="program_new"),
    path("programs/<int:pk>/", views.ProgramDetail.as_view(), name="program_detail"),
    path("programs/<int:pk>/preview.json", views.program_preview_json, name="program_preview_json"),
    path("jobs/", views.JobList.as_view(), name="job_list"),
    path("jobs/new/<int:program_id>/", views.JobCreate.as_view(), name="job_new_for_program"),
    path("jobs/<int:pk>/", views.JobDetail.as_view(), name="job_detail"),
    path("jobs/<int:pk>/edit/", views.JobUpdate.as_view(), name="job_edit"),
    path("jobs/<int:pk>/delete/", views.JobDelete.as_view(), name="job_delete"),
    path("jobs/<int:pk>/submit/", views.job_submit, name="job_submit"),
    path("jobs/<int:pk>/approve/", views.job_approve, name="job_approve"),
    path("jobs/<int:pk>/packet/", views.job_packet, name="job_packet"),
]