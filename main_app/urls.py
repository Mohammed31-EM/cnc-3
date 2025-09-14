from django.urls import path
from . import views

urlpatterns = [
    # --- Programs ---
    path("", views.ProgramList.as_view(), name="program_list"),
    path("programs/new/", views.program_new, name="program_new"),
    path("programs/<int:pk>/", views.ProgramDetail.as_view(), name="program_detail"),
    path("programs/<int:pk>/edit/", views.ProgramUpdate.as_view(), name="program_edit"),
    path("programs/<int:pk>/delete/", views.ProgramDelete.as_view(), name="program_delete"),
    path("programs/<int:pk>/download/", views.program_download, name="program_download"),
    path("programs/<int:pk>/preview.json", views.program_preview_json, name="program_preview_json"),
    path("programs/<int:pk>/preview/", views.program_preview, name="program_preview"),

    # Program history & diff
    path("programs/<int:pk>/history/", views.program_history, name="program_history"),
    path("programs/<int:pk>/versions/<int:ver_id>/diff/", views.program_diff, name="program_diff"),
    path("programs/<int:pk>/versions/<int:ver_id>/download/", views.program_version_download, name="program_version_download"),

    # --- Jobs ---
    path("jobs/", views.JobList.as_view(), name="job_list"),
    path("jobs/<int:pk>/", views.JobDetail.as_view(), name="job_detail"),
    path("programs/<int:program_id>/jobs/new/", views.JobCreate.as_view(), name="job_new_for_program"),
    path("jobs/<int:pk>/edit/", views.JobUpdate.as_view(), name="job_edit"),
    path("jobs/<int:pk>/delete/", views.JobDelete.as_view(), name="job_delete"),
    path("jobs/<int:pk>/submit/", views.job_submit, name="job_submit"),
    path("jobs/<int:pk>/approve/", views.job_approve, name="job_approve"),
    path("jobs/<int:pk>/packet/", views.job_packet, name="job_packet"),
    path("jobs/<int:pk>/packet.pdf", views.job_packet_pdf, name="job_packet_pdf"),
    path("jobs/<int:pk>/lint.json", views.job_lint_json, name="job_lint_json"),

    # --- Attachments ---
    path("jobs/<int:job_id>/attachments/add/", views.attachment_upload, name="attachment_add"),
    path("attachments/<int:pk>/download/", views.attachment_download, name="attachment_download"),
    path("attachments/<int:pk>/delete/", views.attachment_delete, name="attachment_delete"),
]