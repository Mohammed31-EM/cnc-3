# main_app/views.py
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView
from django.shortcuts import render, redirect, get_object_or_404
from django.http import JsonResponse
from django.urls import reverse, reverse_lazy
import math

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
    return JsonResponse({"segments": parsed["segments"], "bbox": parsed["bbox"]})

# ---- tiny MVP parser: G20/21, G90/91, G0/G1 ----
def tiny_parse_gcode(fh, rapid_xy=3000.0, rapid_z=1500.0):
    units="mm"; abs_mode=True
    x=y=z=0.0; feed=1000.0
    bbox={"xmin":0,"xmax":0,"ymin":0,"ymax":0,"zmin":0,"zmax":0}
    def bb(px,py,pz):
        bbox["xmin"]=min(bbox["xmin"],px); bbox["xmax"]=max(bbox["xmax"],px)
        bbox["ymin"]=min(bbox["ymin"],py); bbox["ymax"]=max(bbox["ymax"],py)
        bbox["zmin"]=min(bbox["zmin"],pz); bbox["zmax"]=max(bbox["zmax"],pz)
    bb(x,y,z)

    segs=[]; cut_len=0.0; rxy=0.0; rz=0.0
    seen={"M3":False,"M5":False,"M8":False,"M9":False,"WCS":False}
    first_100_lines=[]
    line_no=0

    for raw in fh:
        line_no+=1
        line=raw.strip()
        if "(" in line: line=line.split("(")[0].strip()
        if not line: continue
        U=line.upper()

        # modal switches
        if "G20" in U: units="in"
        if "G21" in U: units="mm"
        if "G90" in U: abs_mode=True
        if "G91" in U: abs_mode=False

        if any(g in U for g in ("G54","G55","G56","G57","G58","G59")):
            seen["WCS"]=True
        if "M3" in U: seen["M3"]=True
        if "M5" in U: seen["M5"]=True
        if "M8" in U: seen["M8"]=True
        if "M9" in U: seen["M9"]=True
        if line_no <= 100: first_100_lines.append(U)

        nx,ny,nz=x,y,z; code=None
        for t in U.replace(";"," ").split():
            if t in ("G0","G00"): code="G0"
            elif t in ("G1","G01"): code="G1"
            elif t.startswith("X"):
                v=float(t[1:]); nx=(x+v) if not abs_mode else v
            elif t.startswith("Y"):
                v=float(t[1:]); ny=(y+v) if not abs_mode else v
            elif t.startswith("Z"):
                v=float(t[1:]); nz=(z+v) if not abs_mode else v
            elif t.startswith("F"):
                try: feed=float(t[1:])
                except ValueError: pass

        if code is None or (nx,ny,nz)==(x,y,z): continue
        segs.append({"k":code,"frm":[x,y],"to":[nx,ny]})

        conv=25.4 if units=="in" else 1.0
        dx,dy,dz=(nx-x)*conv,(ny-y)*conv,(nz-z)*conv
        if code=="G1":
            cut_len += (dx*dx+dy*dy+dz*dz)**0.5
        else:
            if nz!=z: rz += abs(dz)
            if nx!=x or ny!=y: rxy += (dx*dx+dy*dy)**0.5

        x,y,z=nx,ny,nz; bb(x,y,z)

    t_cut  = (cut_len/max(feed,1e-6))*60.0
    t_rapid= (rxy/rapid_xy + rz/rapid_z)*60.0

    lints=[]
    if not seen["WCS"]:
        lints.append({"code":"WCS_NOT_SET","level":"warn","msg":"No G54..G59 work offset found."})
    else:
        if not any(any(g in l for g in ("G54","G55","G56","G57","G58","G59")) for l in first_100_lines):
            lints.append({"code":"WCS_LATE","level":"info","msg":"Work offset appears after first 100 lines."})
    if seen["M3"] and not seen["M5"]:
        lints.append({"code":"SPINDLE_OFF_END","level":"warn","msg":"Spindle (M5) not seen; ensure spindle stops before end."})
    if seen["M8"] and not seen["M9"]:
        lints.append({"code":"COOLANT_OFF_END","level":"info","msg":"Coolant (M9) not seen; ensure coolant off at end."})

    return {
        "units":units,"abs":abs_mode,"bbox":bbox,
        "segments":segs,
        "meta":{"lints":lints},
        "est_time_s":t_cut + t_rapid,
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