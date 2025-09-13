from django.contrib import admin
from .models import Program, ProgramVersion, Machine, Material, Job, RunLog

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("id", "part_no", "revision", "owner", "units", "created_at")
    list_filter = ("units", "owner")
    search_fields = ("part_no", "revision", "owner__username")
    date_hierarchy = "created_at"
    autocomplete_fields = ("owner",)
    list_select_related = ("owner",)

@admin.register(ProgramVersion)
class ProgramVersionAdmin(admin.ModelAdmin):
    list_display = ("id", "program", "created_at", "comment")
    search_fields = ("program_part_no", "program_revision", "comment")
    date_hierarchy = "created_at"
    list_select_related = ("program",)

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "max_rpm", "max_feed", "rapid_xy", "rapid_z", "safe_z")
    search_fields = ("name",)

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "hardness")
    search_fields = ("name", "hardness")

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id", "program", "owner", "machine", "material", "status", "created_at")
    list_filter = ("status", "machine", "material", "owner")
    search_fields = ("program_part_no", "programrevision", "owner_username")
    date_hierarchy = "created_at"
    autocomplete_fields = ("program", "owner", "machine", "material")
    list_select_related = ("program", "owner", "machine", "material")

@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    # Use the actual timestamp field on your model: 'ts'
    list_display = ("id", "job", "user", "action", "ts")
    list_filter = ("action", "user")
    search_fields = ("job_id", "jobprogrampart_no", "user_username", "action", "notes")
    date_hierarchy = "ts"
    autocomplete_fields = ("job", "user")
    list_select_related = ("job", "user")