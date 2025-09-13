# main_app/views.py
import os
import math
import difflib

from django import forms
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.core.exceptions import PermissionDenied
from django.db.models import Q
from django.http import JsonResponse, FileResponse, Http404
from django.shortcuts import render, redirect, get_object_or_404
from django.urls import reverse, reverse_lazy
from django.utils.html import mark_safe
from django.utils.text import slugify
from django.views.decorators.http import require_GET
from django.views.generic import ListView, DetailView, CreateView, UpdateView, DeleteView

from .models import Program, Job, Machine, Material, RunLog, ProgramVersion


# --- Upload constraints ---
ALLOWED_EXT = {".nc", ".gcode", ".tap"}
MAX_BYTES = 5 * 1024 * 1024  # 5 MB


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
    paginate_by = 10

    def get_queryset(self):
        qs = super().get_queryset()
        q = self.request.GET.get("q")
        if q:
            qs = qs.filter(Q(part_no_icontains=q) | Q(revision_icontains=q))
        return qs


class ProgramDetail(LoginRequiredMixin, OwnerReq, DetailView):
    model = Program


@login_required
def program_new(request):
    if request.method == "POST":
        uploaded = request.FILES.get("file")
        if not uploaded:
            return render(request, "main_app/program_form.html", {"error": "Please choose a file."})

        # --- validation ---
        _, ext = os.path.splitext(uploaded.name.lower())
        if ext not in ALLOWED_EXT:
            return render(request, "main_app/program_form.html",
                          {"error": "Unsupported file type. Use .nc, .gcode, or .tap."})
        if uploaded.size > MAX_BYTES:
            return render(request, "main_app/program_form.html",
                          {"error": "File too large (>5MB)."})

        # Create program & save file
        p = Program.objects.create(
            owner=request.user,
            part_no=request.POST.get("part_no") or "UNSET",
            revision=request.POST.get("revision") or "",
            file=uploaded,
        )

        # Parse safely; if parse fails, delete the record
        try:
            with open(p.file.path, "r", encoding="utf-8", errors="ignore") as fh:
                parsed = tiny_parse_gcode(fh)
        except Exception as e:
            p.delete()
            return render(request, "main_app/program_form.html",
                          {"error": f"Failed to parse G-code: {e}"})

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
        "segments":   parsed["segments"],        # 2D (XY in original units)
        "bbox":       parsed["bbox"],            # 2D bbox (original units)
        "segments3d": parsed["segments3d_mm"],   # 3D in mm for Three.js
        "bbox_mm":    parsed["bbox_mm"],         # 3D bbox in mm
    })


# ---- tiny MVP parser with Lint Pack v2 ----
def tiny_parse_gcode(fh, rapid_xy=3000.0, rapid_z=1500.0, safe_z_mm=None):
    """
    Parses a minimal G-code subset and emits:
      - 2D XY segments (original units) for canvas
      - 3D segments in mm for Three.js
      - bbox (original units) + bbox_mm
      - meta.lints: list of {code, sev, msg}
      - meta.counts: G0/G1 counts

    Lints (v2):
      - L-UNITS: no G20/G21
      - L-MODE:  no G90/G91
      - NO_WCS:  no G54..G59
      - SPINDLE_BEFORE_CUT: cutting before M3/M4 (ever)
      - FEED_BEFORE_CUT: first G1 before any F is set
      - RAPID_BELOW_SAFEZ: any G0 Z below safe_z_mm (if provided)
      - UNKNOWN_G / UNKNOWN_M: unrecognized codes encountered
    """
    units = "mm"; abs_mode = True
    x = y = z = 0.0
    feed = 1000.0  # mm/min

    bbox    = {"xmin": 0, "xmax": 0, "ymin": 0, "ymax": 0, "zmin": 0, "zmax": 0}
    bbox_mm = {"xmin": 0, "xmax": 0, "ymin": 0, "ymax": 0, "zmin": 0, "zmax": 0}

    segs2d    = []
    segs3d_mm = []

    # lint tracking
    seen_units = False
    seen_mode  = False
    seen_wcs   = False  # G54..G59
    spindle_on = False  # current state
    ever_spindle_on = False
    feed_set   = False
    cut_before_feed = False
    first_cut_seen = False

    unknown_g = set()
    unknown_m = set()
    rapid_min_z_mm = float("inf")

    g0_count = 0
    g1_count = 0

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

    allowed_g = {0,1,2,3,17,18,19,20,21,28,40,41,42,43,49,54,55,56,57,58,59,80,90,91,92,94,95}
    allowed_m = {0,1,2,3,4,5,6,7,8,9,30}

    cut_len = rxy = rz = 0.0

    for raw in fh:
        line = raw.strip()
        # strip inline comments
        if "(" in line:
            line = line.split("(")[0].strip()
        if not line:
            continue

        U = line.upper()

        # modal/unit/mode
        if "G20" in U: units = "in"; seen_units = True
        if "G21" in U: units = "mm"; seen_units = True
        if "G90" in U: abs_mode = True;  seen_mode = True
        if "G91" in U: abs_mode = False; seen_mode = True
        if any(("G5"+d) in U for d in "456789"):  # G54..G59
            seen_wcs = True
        if "M3" in U or "M03" in U or "M4" in U or "M04" in U:
            spindle_on = True
            ever_spindle_on = True
        if "M5" in U or "M05" in U:
            spindle_on = False

        # unknown code scan
        for tok in U.replace(";", " ").split():
            if tok.startswith("G") and len(tok) > 1 and any(ch.isdigit() for ch in tok[1:]):
                try:
                    gnum = int(''.join(ch for ch in tok[1:] if ch.isdigit()))
                    if gnum not in allowed_g:
                        unknown_g.add(gnum)
                except ValueError:
                    pass
            if tok.startswith("M") and len(tok) > 1 and any(ch.isdigit() for ch in tok[1:]):
                try:
                    mnum = int(''.join(ch for ch in tok[1:] if ch.isdigit()))
                    if mnum not in allowed_m:
                        unknown_m.add(mnum)
                except ValueError:
                    pass

        nx, ny, nz = x, y, z
        code = None
        for t in U.replace(";", " ").split():
            if t in ("G0","G00"):
                code = "G0"
            elif t in ("G1","G01"):
                code = "G1"
            elif t.startswith("X"):
                v = float(t[1:]); nx = (x + v) if not abs_mode else v
            elif t.startswith("Y"):
                v = float(t[1:]); ny = (y + v) if not abs_mode else v
            elif t.startswith("Z"):
                v = float(t[1:]); nz = (z + v) if not abs_mode else v
            elif t.startswith("F"):
                try:
                    feed = float(t[1:]); feed_set = True
                except ValueError:
                    pass

        if code is None or (nx, ny, nz) == (x, y, z):
            continue

        if code == "G1":
            if not feed_set:
                cut_before_feed = True
            if not first_cut_seen:
                first_cut_seen = True

        if code == "G0": g0_count += 1
        if code == "G1": g1_count += 1

        # 2D XY (original units)
        segs2d.append({"k": code, "frm": [x, y], "to": [nx, ny]})

        # 3D (mm)
        conv = 25.4 if units == "in" else 1.0
        X1,Y1,Z1 = x*conv,  y*conv,  z*conv
        X2,Y2,Z2 = nx*conv, ny*conv, nz*conv
        segs3d_mm.append({"k": code, "frm": [X1,Y1,Z1], "to": [X2,Y2,Z2]})

        if code == "G0":
            rapid_min_z_mm = min(rapid_min_z_mm, Z1, Z2)

        # timing (mm)
        dx, dy, dz = X2-X1, Y2-Y1, Z2-Z1
        if code == "G1":
            cut_len += (dx*dx + dy*dy + dz*dz) ** 0.5
        else:
            if Z2 != Z1: rz += abs(dz)
            if X2 != X1 or Y2 != Y1: rxy += (dx*dx + dy*dy) ** 0.5

        x, y, z = nx, ny, nz
        bb(x, y, z); bb_mm(x, y, z, conv)

    # lints
    lints = []
    if not seen_units:
        lints.append({"code":"L-UNITS","sev":"warn","msg":"No G20/G21 — units unspecified"})
    if not seen_mode:
        lints.append({"code":"L-MODE","sev":"warn","msg":"No G90/G91 — distance mode unspecified"})
    if not seen_wcs:
        lints.append({"code":"NO_WCS","sev":"warn","msg":"No work offset (G54..G59) seen"})
    if first_cut_seen and not ever_spindle_on:
        lints.append({"code":"SPINDLE_BEFORE_CUT","sev":"error","msg":"Cutting move (G1) appears before spindle on (M3/M4)"})
    if cut_before_feed:
        lints.append({"code":"FEED_BEFORE_CUT","sev":"warn","msg":"First cutting move (G1) before any feed (F) specified"})
    if safe_z_mm is not None and rapid_min_z_mm != float("inf") and rapid_min_z_mm < safe_z_mm - 1e-6:
        lints.append({"code":"RAPID_BELOW_SAFEZ","sev":"error","msg":f"Rapid Z below safe Z ({rapid_min_z_mm:.3f} < {safe_z_mm:.3f} mm)"})
    if unknown_g:
        lints.append({"code":"UNKNOWN_G","sev":"info","msg":f"Unknown/unsupported G-codes: {sorted(unknown_g)}"})
    if unknown_m:
        lints.append({"code":"UNKNOWN_M","sev":"info","msg":f"Unknown/unsupported M-codes: {sorted(unknown_m)}"})

    t_cut   = (cut_len / max(feed, 1e-6)) * 60.0
    t_rapid = (rxy / rapid_xy + rz / rapid_z) * 60.0

    return {
        "units": units,
        "abs": abs_mode,
        "bbox": bbox,
        "bbox_mm": bbox_mm,
        "segments": segs2d,
        "segments3d_mm": segs3d_mm,
        "meta": {"counts": {"G0": g0_count, "G1": g1_count}, "lints": lints},
        "est_time_s": t_cut + t_rapid,
    }


# ---- jobs ----
class JobList(LoginRequiredMixin, OwnerQS, ListView):
    model = Job
    ordering = ["-created_at"]


class JobDetail(LoginRequiredMixin, OwnerReq, DetailView):
    model = Job
    template_name = "main_app/job_detail.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # --- include RunLog timeline
        ctx["logs"] = (
            RunLog.objects.filter(job=self.object)
            .select_related("user")
            .order_by("-ts")
        )

        # --- include lint results inline
        try:
            with open(self.object.program.file.path, "r", encoding="utf-8", errors="ignore") as fh:
                parsed = tiny_parse_gcode(fh, safe_z_mm=self.object.machine.safe_z)
            lints = list(parsed["meta"].get("lints", []))

            # stock bounds check
            bb = parsed["bbox_mm"]
            L = float(self.object.stock_lwh_mm.get("L", 0) or 0)
            W = float(self.object.stock_lwh_mm.get("W", 0) or 0)
            H = float(self.object.stock_lwh_mm.get("H", 0) or 0)

            if bb["xmin"] < -1e-6 or bb["xmax"] > L + 1e-6 or \
               bb["ymin"] < -1e-6 or bb["ymax"] > W + 1e-6:
                lints.append({
                    "code": "EXIT_STOCK_XY", "sev": "warn",
                    "msg": f"Toolpath leaves XY stock bounds (X:[0,{L}] Y:[0,{W}])"
                })

            if bb["zmin"] < -H - 1e-6:
                lints.append({
                    "code": "EXIT_STOCK_Z", "sev": "warn",
                    "msg": f"Toolpath goes below stock thickness (Zmin {bb['zmin']:.3f} < -{H} mm)"
                })

            ctx["lint_results"] = {
                "bbox_mm": bb,
                "counts": parsed["meta"].get("counts", {}),
                "lints": lints,
            }
        except Exception as e:
            ctx["lint_results"] = {"error": str(e)}

        return ctx



class JobCreate(LoginRequiredMixin, CreateView):
    model = Job
    fields = ["machine", "material", "stock_lwh_mm", "qty", "wcs"]
    template_name = "main_app/job_form.html"

    def get_initial(self):
        return {"stock_lwh_mm": {"L": 100, "W": 60, "H": 12}, "qty": 1, "wcs": "G54"}

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
    fields = ["machine", "material", "stock_lwh_mm", "qty", "wcs", "status"]
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


# --- Job-aware lint JSON (machine safe Z + stock bounds) ---
@login_required
def job_lint_json(request, pk):
    job = get_object_or_404(Job, pk=pk, owner=request.user)

    # Parse program with machine safe Z for rapid checks
    with open(job.program.file.path, "r", encoding="utf-8", errors="ignore") as fh:
        parsed = tiny_parse_gcode(fh, safe_z_mm=job.machine.safe_z)

    lints = list(parsed["meta"].get("lints", []))  # copy

    # Stock bounds (assume origin at top-left corner of top face):
    # X:[0, L], Y:[0, W], Z:0 at top, cutting downward negative to -H
    bb = parsed["bbox_mm"]
    L = float(job.stock_lwh_mm.get("L", 0) or 0)
    W = float(job.stock_lwh_mm.get("W", 0) or 0)
    H = float(job.stock_lwh_mm.get("H", 0) or 0)

    if bb["xmin"] < -1e-6 or bb["xmax"] > L + 1e-6 or bb["ymin"] < -1e-6 or bb["ymax"] > W + 1e-6:
        lints.append({"code":"EXIT_STOCK_XY","sev":"warn",
                      "msg":f"Toolpath leaves XY stock bounds (X:[0,{L}] Y:[0,{W}])"})

    if bb["zmin"] < -H - 1e-6:
        lints.append({"code":"EXIT_STOCK_Z","sev":"warn",
                      "msg":f"Toolpath goes below stock thickness (Zmin {bb['zmin']:.3f} < -{H} mm)"})

    return JsonResponse({
        "job_id": job.pk,
        "program_id": job.program_id,
        "machine": job.machine.name,
        "stock_mm": job.stock_lwh_mm,
        "bbox_mm": bb,
        "counts": parsed["meta"].get("counts", {}),
        "lints": lints,
    })


# --- Program Update / Delete / Download ---
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
        uploaded = form.cleaned_data.get("file")

        # If there is a new file, validate first (before saving)
        if uploaded:
            _, ext = os.path.splitext(uploaded.name.lower())
            if ext not in ALLOWED_EXT:
                form.add_error("file", "Unsupported file type. Use .nc, .gcode, or .tap.")
                return self.form_invalid(form)
            if uploaded.size > MAX_BYTES:
                form.add_error("file", "File too large (>5MB).")
                return self.form_invalid(form)

            # Save text fields and file
            self.object = form.save(commit=False)
            self.object.file = uploaded
            self.object.save()

            # Re-parse after replacing file
            try:
                with open(self.object.file.path, "r", encoding="utf-8", errors="ignore") as fh:
                    parsed = tiny_parse_gcode(fh)
            except Exception as e:
                form.add_error("file", f"Failed to parse G-code: {e}")
                return self.form_invalid(form)

            self.object.units = parsed["units"]
            self.object.abs_mode = parsed["abs"]
            self.object.bbox_json = parsed["bbox"]
            self.object.meta_json = parsed["meta"]
            self.object.est_time_s = parsed["est_time_s"]
            self.object.save(update_fields=["units", "abs_mode", "bbox_json", "meta_json", "est_time_s"])

            return redirect(reverse("program_detail", args=[self.object.pk]))

        # No new file — just save metadata edits
        return super().form_valid(form)

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


# --- Program History / Diff / Version download ---
@login_required
def program_history(request, pk):
    prog = get_object_or_404(Program, pk=pk)
    if prog.owner_id != request.user.id:
        raise PermissionDenied
    versions = prog.versions.all()
    return render(request, "main_app/program_history.html", {"program": prog, "versions": versions})

@require_GET
@login_required
def program_version_download(request, pk, ver_id):
    prog = get_object_or_404(Program, pk=pk)
    if prog.owner_id != request.user.id:
        raise PermissionDenied
    ver = get_object_or_404(ProgramVersion, pk=ver_id, program=prog)
    try:
        fname = f"{slugify(prog.part_no)}-{slugify(prog.revision or 'rev')}-v{ver.id}.nc"
        return FileResponse(open(ver.file.path, "rb"), as_attachment=True, filename=fname)
    except FileNotFoundError:
        raise Http404("Version file missing.")

@login_required
def program_diff(request, pk, ver_id):
    prog = get_object_or_404(Program, pk=pk)
    if prog.owner_id != request.user.id:
        raise PermissionDenied
    ver = get_object_or_404(ProgramVersion, pk=ver_id, program=prog)

    def read_lines(path):
        with open(path, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read().splitlines()

    old_lines = read_lines(ver.file.path)
    cur_lines = read_lines(prog.file.path)

    diff_html = difflib.HtmlDiff(wrapcolumn=100).make_table(
        old_lines, cur_lines, fromdesc=f"Version v{ver.id}", todesc="Current"
    )
    return render(
        request,
        "main_app/program_diff.html",
        {"program": prog, "version": ver, "diff_html": mark_safe(diff_html)},
    )