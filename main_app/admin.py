from django.contrib import admin
from .models import Program, Machine, Material, Job, RunLog

@admin.register(Program)
class ProgramAdmin(admin.ModelAdmin):
    list_display = ("part_no","revision","owner","units","created_at")
    list_filter = ("units","owner")
    search_fields = ("part_no","revision")

@admin.register(Machine)
class MachineAdmin(admin.ModelAdmin):
    list_display = ("name","max_rpm","max_feed","rapid_xy","rapid_z","safe_z")
    search_fields = ("name",)

@admin.register(Material)
class MaterialAdmin(admin.ModelAdmin):
    list_display = ("name","hardness")
    search_fields = ("name","hardness")

@admin.register(Job)
class JobAdmin(admin.ModelAdmin):
    list_display = ("id","program","owner","machine","material","status","created_at")
    list_filter = ("status","machine","material","owner")
    search_fields = ("program__part_no",)

@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ("job","user","action","ts")
    list_filter = ("action","user")
