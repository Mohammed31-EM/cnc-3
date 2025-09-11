# main_app/models.py
from django.db import models
from django.contrib.auth import get_user_model
from django.conf import settings
User = get_user_model()

class Program(models.Model):
    owner      = models.ForeignKey(User, on_delete=models.CASCADE, related_name="programs")
    part_no    = models.CharField(max_length=80)
    revision   = models.CharField(max_length=10, blank=True)
    file       = models.FileField(upload_to="programs/")
    units      = models.CharField(max_length=2, default="mm")   # "mm" or "in"
    abs_mode   = models.BooleanField(default=True)               # G90 (True) / G91 (False)
    bbox_json  = models.JSONField(default=dict)                  # {xmin,xmax,ymin,ymax,zmin,zmax}
    meta_json  = models.JSONField(default=dict)                  # tools/feeds/counts/lints (later)
    est_time_s = models.FloatField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.part_no} {self.revision}".strip()


class Machine(models.Model):
    name = models.CharField(max_length=80)
    max_rpm = models.IntegerField(default=12000)
    max_feed = models.IntegerField(default=4000)   # mm/min
    rapid_xy = models.IntegerField(default=3000)   # mm/min
    rapid_z  = models.IntegerField(default=1500)   # mm/min
    safe_z   = models.FloatField(default=5.0)
    def __str__(self): return self.name

class Material(models.Model):
    name = models.CharField(max_length=80)
    hardness = models.CharField(max_length=40, blank=True)
    feedspeeds_json = models.JSONField(default=dict, blank=True)
    def __str__(self): return self.name

class Job(models.Model):
    STATUS = [("draft","Draft"), ("submitted","Submitted"), ("approved","Approved")]
    owner    = models.ForeignKey(User, on_delete=models.CASCADE, related_name="jobs")
    program  = models.ForeignKey("Program", on_delete=models.CASCADE)
    machine  = models.ForeignKey(Machine, on_delete=models.PROTECT)
    material = models.ForeignKey(Material, on_delete=models.PROTECT)
    stock_lwh_mm = models.JSONField(default=dict)     
    qty      = models.IntegerField(default=1)
    wcs      = models.CharField(max_length=8, default="G54")  
    status   = models.CharField(max_length=10, choices=STATUS, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"Job {self.pk} — {self.program}"

class RunLog(models.Model):
    job  = models.ForeignKey(Job, on_delete=models.CASCADE, related_name="logs")
    user = models.ForeignKey(User, on_delete=models.PROTECT)
    action = models.CharField(max_length=20)  
    notes  = models.TextField(blank=True)
    ts = models.DateTimeField(auto_now_add=True)
    def __str__(self): return f"{self.ts:%Y-%m-%d %H:%M} {self.action}"


class ProgramVersion(models.Model):
    program = models.ForeignKey("Program", on_delete=models.CASCADE, related_name="versions")
    file = models.FileField(upload_to="program_versions/")
    comment = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def _str_(self):
        return f"v{self.pk} of {self.program.part_no} {self.program.revision}"