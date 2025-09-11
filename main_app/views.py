# main_app/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
from .models import Program
import math
from django.http import FileResponse, Http404
from django.utils.text import slugify
from django import forms

from .models import Program, Job, Machine, Material, RunLog


# ---- ownership helpers ----
class OwnerQS:
    def get_queryset(self):
        return super().get_queryset().filter(owner=self.request.user)

class OwnerReq(UserPassesTestMixin):
    def test_func(self):
        return self.get_object().owner_id == self.request.user.id

# ---- programs ----
class ProgramList(LoginRequiredMixin, OwnerQS, ListView):
    model = Program
    ordering = ["-created_at"]

class ProgramDetail(LoginRequiredMixin, OwnerReq, DetailView):
    model = Program

@login_required
def program_new(request):
    if request.method == "POST":
        uploaded = request.FILES["file"]
        p = Program.objects.create(
            owner=request.user,
            part_no=request.POST.get("part_no") or "UNSET",
            revision=request.POST.get("revision") or "",
            file=uploaded,
        )
        with open(p.file.path, "r", encoding="utf-8", errors="ignore") as fh:
            parsed = tiny_parse_gcode(fh)
        p.units = parsed["units"]
        p.abs_mode = parsed["abs"]
        p.bbox_json = parsed["bbox"]
        p.meta_json = parsed["meta"]
        p.est_time_s = parsed["est_time_s"]
        p.save()
        return redirect(reverse("program_detail", args=[p.pk]))
    return render(request, "main_app/program_form.html")

@login_required
def program_preview_json(request, pk):
    p = get_object_or_404(Program, pk=pk, owner=request.user)
    with open(p.file.path, "r", encoding="utf-8", errors="ignore") as fh:
        parsed = tiny_parse_gcode(fh)
    return JsonResponse({
        "segments":   parsed["segments"],        # 2D (XY)
        "bbox":       parsed["bbox"],            # 2D bbox
        "segments3d": parsed["segments3d_mm"],   # 3D in mm
        "bbox_mm":    parsed["bbox_mm"],         # 3D bbox in mm
    })


# ---- tiny MVP parser: G20/21, G90/91, G0/G1 ----
def tiny_parse_gcode(fh, rapid_xy=3000.0, rapid_z=1500.0):
    units = "mm"; abs_mode = True
    x = y = z = 0.0
    feed = 1000.0  # mm/min

    bbox    = {"xmin": 0, "xmax": 0, "ymin": 0, "ymax": 0, "zmin": 0, "zmax": 0}
    bbox_mm = {"xmin": 0, "xmax": 0, "ymin": 0, "ymax": 0, "zmin": 0, "zmax": 0}

    segs2d    = []   # XY segments (original units) for 2D canvas
    segs3d_mm = []   # 3D segments (mm) for Three.js

    def bb(px, py, pz):
        bbox["xmin"] = min(bbox["xmin"], px); bbox["xmax"] = max(bbox["xmax"], px)
        bbox["ymin"] = min(bbox["ymin"], py); bbox["ymax"] = max(bbox["ymax"], py)
        bbox["zmin"] = min(bbox["zmin"], pz); bbox["zmax"] = max(bbox["zmax"], pz)

    def bb_mm(px, py, pz, conv):
        X, Y, Z = px*conv, py*conv, pz*conv
        bbox_mm["xmin"] = min(bbox_mm["xmin"], X); bbox_mm["xmax"] = max(bbox_mm["xmax"], X)
        bbox_mm["ymin"] = min(bbox_mm["ymin"], Y); bbox_mm["ymax"] = max(bbox_mm["ymax"], Y)
        bbox_mm["zmin"] = min(bbox_mm["zmin"], Z); bbox_mm["zmax"] = max(bbox_mm["zmax"], Z)

    bb(x, y, z); bb_mm(x, y, z, 1.0)

    cut_len = rxy = rz = 0.0

    for raw in fh:
        line = raw.strip()
        if "(" in line:
            line = line.split("(")[0].strip()
        if not line:
            continue

        U = line.upper()
        if "G20" in U: units = "in"
        if "G21" in U: units = "mm"
        if "G90" in U: abs_mode = True
        if "G91" in U: abs_mode = False

        nx, ny, nz = x, y, z
        code = None
        for t in U.replace(";", " ").split():
            if t in ("G0","G00"):   code = "G0"
            elif t in ("G1","G01"): code = "G1"
            elif t.startswith("X"):
                v = float(t[1:]); nx = (x + v) if not abs_mode else v
            elif t.startswith("Y"):
                v = float(t[1:]); ny = (y + v) if not abs_mode else v
            elif t.startswith("Z"):
                v = float(t[1:]); nz = (z + v) if not abs_mode else v
            elif t.startswith("F"):
                try: feed = float(t[1:])
                except ValueError: pass

        if code is None or (nx, ny, nz) == (x, y, z):
            continue

        # 2D XY segment (original units)
        segs2d.append({"k": code, "frm": [x, y], "to": [nx, ny]})

        # 3D segment (mm)
        conv = 25.4 if units == "in" else 1.0
        segs3d_mm.append({"k": code,
                          "frm": [x*conv,  y*conv,  z*conv],
                          "to":  [nx*conv, ny*conv, nz*conv]})

        # time distances (mm)
        dx, dy, dz = (nx-x)*conv, (ny-y)*conv, (nz-z)*conv
        if code == "G1":
            cut_len += (dx*dx + dy*dy + dz*dz) ** 0.5
        else:
            if nz != z: rz += abs(dz)
            if nx != x or ny != y: rxy += (dx*dx + dy*dy) ** 0.5

        x, y, z = nx, ny, nz
        bb(x, y, z); bb_mm(x, y, z, conv)

    t_cut   = (cut_len / max(feed, 1e-6)) * 60.0
    t_rapid = (rxy / rapid_xy + rz / rapid_z) * 60.0

    return {
        "units": units,
        "abs": abs_mode,
        "bbox": bbox,
        "bbox_mm": bbox_mm,
        "segments": segs2d,
        "segments3d_mm": segs3d_mm,
        "meta": {"counts": {"G0": 0, "G1": 0}},
        "est_time_s": t_cut + t_rapid,
    }


class JobList(LoginRequiredMixin, OwnerQS, ListView):
    model = Job
    ordering = ["-created_at"]

class JobDetail(LoginRequiredMixin, OwnerReq, DetailView):
    model = Job
    template_name = "main_app/job_detail.html"

class JobCreate(LoginRequiredMixin, CreateView):
    model = Job
    fields = ["machine","material","stock_lwh_mm","qty","wcs"]
    template_name = "main_app/job_form.html"

    def get_initial(self):
        return {"stock_lwh_mm":{"L":100,"W":60,"H":12}, "qty":1, "wcs":"G54"}

    def form_valid(self, form):
        form.instance.owner = self.request.user
        program = get_object_or_404(Program, pk=self.kwargs["program_id"], owner=self.request.user)
        form.instance.program = program
        resp = super().form_valid(form)
        RunLog.objects.create(job=self.object, user=self.request.user, action="create", notes="")
        return resp

    def get_success_url(self):
        return reverse("job_detail", args=[self.object.pk])

class JobUpdate(LoginRequiredMixin, OwnerReq, UpdateView):
    model = Job
    fields = ["machine","material","stock_lwh_mm","qty","wcs","status"]
    template_name = "main_app/job_form.html"
    def form_valid(self, form):
        resp = super().form_valid(form)
        RunLog.objects.create(job=self.object, user=self.request.user, action="update", notes="")
        return resp
    def get_success_url(self):
        return reverse("job_detail", args=[self.object.pk])

class JobDelete(LoginRequiredMixin, OwnerReq, DeleteView):
    model = Job
    success_url = reverse_lazy("job_list")

@login_required
def job_submit(request, pk):
    job = get_object_or_404(Job, pk=pk, owner=request.user)
    if job.status == "draft":
        job.status = "submitted"; job.save()
        RunLog.objects.create(job=job, user=request.user, action="submit", notes="")
    return redirect("job_detail", pk=pk)

@login_required
def job_approve(request, pk):
    job = get_object_or_404(Job, pk=pk, owner=request.user)
    if job.status == "submitted":
        job.status = "approved"; job.save()
        RunLog.objects.create(job=job, user=request.user, action="approve", notes="")
    return redirect("job_detail", pk=pk)

@login_required
def job_packet(request, pk):
    job = get_object_or_404(Job, pk=pk, owner=request.user)
    return render(request, "main_app/job_packet.html", {"job": job})


# --- Program Update / Delete ---
class ProgramEditForm(forms.ModelForm):
    # allow optional re-upload (keeps file if left empty)
    file = forms.FileField(required=False, help_text="Upload to replace the current file.")
    class Meta:
        model = Program
        fields = ["part_no", "revision", "file"]

class ProgramUpdate(LoginRequiredMixin, OwnerReq, UpdateView):
    model = Program
    form_class = ProgramEditForm
    template_name = "main_app/program_edit.html"

    def form_valid(self, form):
        resp = super().form_valid(form)
        # If file replaced, re-parse
        if form.cleaned_data.get("file"):
            with open(self.object.file.path, "r", encoding="utf-8", errors="ignore") as fh:
                parsed = tiny_parse_gcode(fh)
            self.object.units = parsed["units"]
            self.object.abs_mode = parsed["abs"]
            self.object.bbox_json = parsed["bbox"]
            self.object.meta_json = parsed["meta"]
            self.object.est_time_s = parsed["est_time_s"]
            self.object.save(update_fields=["units","abs_mode","bbox_json","meta_json","est_time_s"])
        return resp

    def get_success_url(self):
        return reverse("program_detail", args=[self.object.pk])

class ProgramDelete(LoginRequiredMixin, OwnerReq, DeleteView):
    model = Program
    template_name = "main_app/program_confirm_delete.html"
    success_url = reverse_lazy("program_list")

@login_required
def program_download(request, pk):
    p = get_object_or_404(Program, pk=pk, owner=request.user)
    try:
        fname = f"{slugify(p.part_no)}-{slugify(p.revision or 'rev')}.nc"
        return FileResponse(open(p.file.path, "rb"), as_attachment=True, filename=fname)
    except FileNotFoundError:
        raise Http404("Program file missing.")