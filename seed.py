# seed.py  —  run with:  python seed.py
import os
import math

# --- Django setup ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cnc3.settings")
import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402

from main_app.models import Program, Machine, Material, Job, RunLog  # noqa: E402
# Re-use your parser so Program meta/bbox/time match your app
from main_app.views import tiny_parse_gcode  # noqa: E402


def get_or_create_demo_user():
    """
    Creates or returns a demo user. Override via env:
      SEED_USERNAME=alice SEED_PASSWORD=secret python seed.py
    """
    User = get_user_model()
    username = os.getenv("SEED_USERNAME", "demo")
    password = os.getenv("SEED_PASSWORD", "demo12345")
    user, created = User.objects.get_or_create(
        username=username, defaults={"email": f"{username}@example.com"}
    )
    if created:
        user.set_password(password)
        user.save()
        print(f"✓ Created user: {username} / {password}")
    else:
        print(f"• Using existing user: {username}")
    return user


def seed_machines():
    data = [
        dict(name="Haas VF-2 (example)", max_rpm=10000, max_feed=12000, rapid_xy=24000, rapid_z=15240, safe_z=5.0),
        dict(name="Tormach 1100MX (example)", max_rpm=10000, max_feed=5000, rapid_xy=7620, rapid_z=5080, safe_z=6.0),
        dict(name="Desktop Router (example)", max_rpm=18000, max_feed=3000, rapid_xy=4000, rapid_z=2000, safe_z=10.0),
    ]
    out = []
    for d in data:
        obj, created = Machine.objects.get_or_create(name=d["name"], defaults=d)
        print(("✓ Created" if created else "• Exists"), "Machine:", obj.name)
        out.append(obj)
    return out


def seed_materials():
    al6061 = {
        "units": "mm",
        "notes": "Generic starters for carbide; adjust per rigidity/coolant.",
        "tools": {
            "flat_endmill": {
                "3": {"flutes": 2, "rpm": 12000, "chipload_mm_per_tooth": 0.015, "doc_axial_mm": 1.5, "doc_radial_mm": 1.0},
                "6": {"flutes": 3, "rpm": 10000, "chipload_mm_per_tooth": 0.030, "doc_axial_mm": 3.0, "doc_radial_mm": 2.0},
                "10": {"flutes": 3, "rpm": 8000,  "chipload_mm_per_tooth": 0.040, "doc_axial_mm": 5.0, "doc_radial_mm": 2.5},
            }
        },
    }
    steel1018 = {
        "units": "mm",
        "notes": "Conservative starters for carbide; flood/air.",
        "tools": {
            "flat_endmill": {
                "3": {"flutes": 3, "rpm": 6000, "chipload_mm_per_tooth": 0.010, "doc_axial_mm": 1.0, "doc_radial_mm": 0.6},
                "6": {"flutes": 4, "rpm": 4500, "chipload_mm_per_tooth": 0.020, "doc_axial_mm": 2.0, "doc_radial_mm": 1.0},
                "10": {"flutes": 4, "rpm": 3500, "chipload_mm_per_tooth": 0.025, "doc_axial_mm": 3.0, "doc_radial_mm": 1.5},
            }
        },
    }
    pmma = {
        "units": "mm",
        "notes": "High rpm to avoid chip welding; single/2-flute.",
        "tools": {
            "flat_endmill": {
                "2": {"flutes": 1, "rpm": 16000, "chipload_mm_per_tooth": 0.020, "doc_axial_mm": 1.0, "doc_radial_mm": 0.8},
                "3": {"flutes": 2, "rpm": 18000, "chipload_mm_per_tooth": 0.015, "doc_axial_mm": 1.0, "doc_radial_mm": 0.6},
                "6": {"flutes": 2, "rpm": 16000, "chipload_mm_per_tooth": 0.025, "doc_axial_mm": 2.0, "doc_radial_mm": 1.0},
            }
        },
    }
    data = [
        dict(name="6061-T6 Aluminum (example)", hardness="HB ~95",  feedspeeds_json=al6061),
        dict(name="1018 Mild Steel (example)",   hardness="BHN ~120", feedspeeds_json=steel1018),
        dict(name="Acrylic PMMA (example)",      hardness="-",         feedspeeds_json=pmma),
    ]
    out = []
    for d in data:
        obj, created = Material.objects.get_or_create(name=d["name"], defaults=d)
        print(("✓ Created" if created else "• Exists"), "Material:", obj.name)
        out.append(obj)
    return out


# ---------- GCODE BUILDERS (G0/G1 only; absolute; metric) ----------

def _hdr(title="DEMO", safez=10.0):
    return [
        "%",
        f"({title}; metric; absolute; G0/G1 only)",
        "G21 G90 G17",
        "G54",
        "T1 M6",
        "S12000 M3",
        f"G0 Z{safez:.3f}",
        "G0 X0.000 Y0.000",
    ]


def _end():
    return [
        "G0 Z15.000",
        "M5",
        "G0 X0.000 Y0.000",
        "M30",
        "%",
    ]


def build_long_complex_gcode():
    lines = []
    A = lines.append
    for s in _hdr("DEMO-3D-LONG — Helix + Pocket + 3D Wave"):
        A(s)

    # Helical ramp down
    cx, cy = 60.0, 60.0
    r = 25.0
    z_top, z_bot = 0.0, -10.0
    turns = 5
    steps_per_turn = 180
    total_steps = turns * steps_per_turn

    A("(Helical ramp down)")
    A("F800")
    A(f"G0 X{cx + r:.3f} Y{cy:.3f}")
    A("G1 Z0.000 F300")
    for i in range(total_steps + 1):
        t = 2.0 * math.pi * (i / steps_per_turn)
        x = cx + r * math.cos(t)
        y = cy + r * math.sin(t)
        z = z_top + (z_bot - z_top) * (i / total_steps)
        A(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F800")
    A(f"G1 X{cx + r:.3f} Y{cy:.3f} Z{z_bot:.3f} F800")

    # Serpentine pocket
    A("(Serpentine pocket area: 10,20 to 110,80)")
    x0, y0 = 10.0, 20.0
    x1, y1 = 110.0, 80.0
    row_pitch = 2.0
    depths = [-12.0, -13.5, -15.0, -16.5, -18.0]
    A("G0 Z5.000")
    A(f"G0 X{x0:.3f} Y{y0:.3f}")
    for di, depth in enumerate(depths):
        A(f"(Depth pass {di+1} at Z={depth:.3f})")
        A(f"G1 Z{depth:.3f} F300")
        y = y0
        row = 0
        A("F1200")
        while y <= y1 + 1e-6:
            if row % 2 == 0:
                A(f"G1 X{x1:.3f} Y{y:.3f}")
            else:
                A(f"G1 X{x0:.3f} Y{y:.3f}")
            y += row_pitch
            row += 1
            if y <= y1 + 1e-6:
                A(f"G1 X{(x1 if (row % 2 == 1) else x0):.3f} Y{y:.3f}")
        # perimeter cleanup
        A(f"G1 X{x0:.3f} Y{y0:.3f} F900")
        A(f"G1 X{x1:.3f} Y{y0:.3f}")
        A(f"G1 X{x1:.3f} Y{y1:.3f}")
        A(f"G1 X{x0:.3f} Y{y1:.3f}")
        A(f"G1 X{x0:.3f} Y{y0:.3f}")

    # 3D wavy surface
    A("(3D wavy surface)")
    A("G0 Z5.000")
    wave_y0, wave_y1 = 0.0, 120.0
    wave_x0, wave_x1 = 0.0, 120.0
    y_pass_pitch = 2.0
    samples_per_pass = 700
    base_z = -4.0
    amp_z = 2.5

    A(f"G0 X{wave_x0:.3f} Y{wave_y0:.3f}")
    y = wave_y0
    pass_idx = 0
    while y <= wave_y1 + 1e-6:
        A(f"(Wave pass at Y={y:.3f})")
        A("F1400")
        if pass_idx % 2 == 0:
            xs = [wave_x0 + (wave_x1 - wave_x0) * (i / samples_per_pass) for i in range(samples_per_pass + 1)]
        else:
            xs = [wave_x1 - (wave_x1 - wave_x0) * (i / samples_per_pass) for i in range(samples_per_pass + 1)]
        for x in xs:
            z = base_z + amp_z * math.sin(0.08 * x + 0.05 * y)
            A(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}")
        y += y_pass_pitch
        pass_idx += 1
        if y <= wave_y1 + 1e-6:
            A("G0 Z5.000")
            A(f"G0 X{xs[-1]:.3f} Y{y:.3f}")
            z_plunge = base_z + amp_z * math.sin(0.08 * xs[-1] + 0.05 * y)
            A(f"G1 Z{z_plunge:.3f} F300")

    for s in _end():
        A(s)
    return "\n".join(lines)


def build_short_square():
    return """%
(SHORT-DEMO — small square, metric)
G21 G90 G17
G54
S12000 M3
G0 Z10
G0 X0 Y0
F600
G1 Z-1 F200
G1 X40 Y0
G1 X40 Y30
G1 X0  Y30
G1 X0  Y0
G0 Z10
M5
G0 X0 Y0
M30
%"""


def build_rect_pocket(w=80, h=50, step=2.0, depth=-6.0):
    lines = []
    A = lines.append
    for s in _hdr(f"RECT-POCKET {w}x{h}"):
        A(s)
    x0, y0 = 10.0, 10.0
    x1, y1 = x0 + w, y0 + h
    A("G0 Z5.000")
    A(f"G0 X{x0:.3f} Y{y0:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    y = y0
    A("F1000")
    row = 0
    while y <= y1 + 1e-6:
        if row % 2 == 0:
            A(f"G1 X{x1:.3f} Y{y:.3f}")
        else:
            A(f"G1 X{x0:.3f} Y{y:.3f}")
        y += step
        row += 1
        if y <= y1 + 1e-6:
            A(f"G1 X{(x1 if (row % 2 == 1) else x0):.3f} Y{y:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_spiral_square(size=100.0, pitch=2.0, depth=-3.0):
    lines = []
    A = lines.append
    for s in _hdr(f"SPIRAL-SQUARE {size}"):
        A(s)
    x0, y0 = 0.0, 0.0
    x, y = x0, y0
    max_x, max_y = x0 + size, y0 + size
    min_x, min_y = x0, y0
    A("G0 Z5.000")
    A(f"G0 X{x0:.3f} Y{y0:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F1200")
    while min_x < max_x and min_y < max_y:
        A(f"G1 X{max_x:.3f} Y{y:.3f}")
        A(f"G1 X{max_x:.3f} Y{max_y:.3f}")
        A(f"G1 X{min_x:.3f} Y{max_y:.3f}")
        min_x += pitch
        min_y += pitch
        max_x -= pitch
        max_y -= pitch
        if min_x < max_x and min_y < max_y:
            A(f"G1 X{min_x:.3f} Y{min_y:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_helix_bore(cx=60.0, cy=60.0, r=12.0, depth=-8.0, turns=4, steps_per_turn=90):
    lines = []
    A = lines.append
    for s in _hdr(f"HELIX-BORE r{r}"):
        A(s)
    A("F800")
    A(f"G0 X{cx + r:.3f} Y{cy:.3f}")
    A("G1 Z0.000 F300")
    total_steps = turns * steps_per_turn
    for i in range(total_steps + 1):
        t = 2.0 * math.pi * (i / steps_per_turn)
        x = cx + r * math.cos(t)
        y = cy + r * math.sin(t)
        z = 0.0 + (depth - 0.0) * (i / total_steps)
        A(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f} F800")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_grid_hatch(w=120, h=120, pitch=10.0, depth=-1.0):
    lines = []
    A = lines.append
    for s in _hdr(f"GRID-HATCH {pitch}mm"):
        A(s)
    x0, y0 = 0.0, 0.0
    x1, y1 = x0 + w, y0 + h
    A("G0 Z5.000")
    A(f"G0 X{x0:.3f} Y{y0:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F1500")
    y = y0
    while y <= y1 + 1e-6:
        A(f"G1 X{x1:.3f} Y{y:.3f}")
        y += pitch
        if y <= y1 + 1e-6:
            A(f"G1 X{x0:.3f} Y{y:.3f}")
    A("G0 Z5.000")
    A(f"G0 X{x0:.3f} Y{y0:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F1500")
    x = x0
    while x <= x1 + 1e-6:
        A(f"G1 X{x:.3f} Y{y1:.3f}")
        x += pitch
        if x <= x1 + 1e-6:
            A(f"G1 X{x:.3f} Y{y0:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_zigzag_plate(w=120, h=80, pitch=5.0, depth=-2.0):
    lines = []
    A = lines.append
    for s in _hdr("ZIGZAG-PLATE"):
        A(s)
    x0, y0 = 0.0, 0.0
    x1, y1 = x0 + w, y0 + h
    A("G0 Z5.000")
    A(f"G0 X{x0:.3f} Y{y0:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F1200")
    y = y0
    row = 0
    while y <= y1 + 1e-6:
        if row % 2 == 0:
            A(f"G1 X{x1:.3f} Y{y:.3f}")
        else:
            A(f"G1 X{x0:.3f} Y{y:.3f}")
        y += pitch
        row += 1
        if y <= y1 + 1e-6:
            A(f"G1 X{(x1 if row % 2 == 1 else x0):.3f} Y{y:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_chamfer_frame(w=120, h=80, inset=5.0, depth=-1.0):
    lines = []
    A = lines.append
    for s in _hdr("CHAMFER-FRAME"):
        A(s)
    x0, y0 = 0.0, 0.0
    x1, y1 = x0 + w, y0 + h
    A("G0 Z5.000")
    A(f"G0 X{x0+inset:.3f} Y{y0+inset:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F900")
    A(f"G1 X{x1-inset:.3f} Y{y0+inset:.3f}")
    A(f"G1 X{x1-inset:.3f} Y{y1-inset:.3f}")
    A(f"G1 X{x0+inset:.3f} Y{y1-inset:.3f}")
    A(f"G1 X{x0+inset:.3f} Y{y0+inset:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_bolt_circle(cx=60.0, cy=60.0, r=40.0, holes=8, z_top=2.0, z_drill=-6.0):
    lines = []
    A = lines.append
    for s in _hdr(f"BOLT-CIRCLE {holes}x"):
        A(s)
    A("F300")
    for i in range(holes):
        t = 2.0 * math.pi * i / holes
        x = cx + r * math.cos(t)
        y = cy + r * math.sin(t)
        A(f"G0 Z{z_top:.3f}")
        A(f"G0 X{x:.3f} Y{y:.3f}")
        A(f"G1 Z{z_drill:.3f}")
        A(f"G0 Z{z_top:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_wave_ridges(w=120, h=60, y_pitch=3.0, amp=3.0, depth_base=-2.0):
    lines = []
    A = lines.append
    for s in _hdr("WAVE-RIDGES"):
        A(s)
    A("G0 Z5.000")
    y = 0.0
    while y <= h + 1e-6:
        A(f"G0 X0.000 Y{y:.3f}")
        A("F1200")
        for i in range(241):
            x = i * (w / 240.0)
            z = depth_base + amp * math.sin(0.12 * x + 0.05 * y)
            if i == 0:
                A(f"G1 Z{z:.3f} F300")
            A(f"G1 X{x:.3f} Y{y:.3f} Z{z:.3f}")
        y += y_pitch
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_star_outline(cx=60, cy=60, r_outer=40, r_inner=18, points=5, depth=-2.0):
    lines = []
    A = lines.append
    for s in _hdr("STAR-OUTLINE"):
        A(s)
    # build vertices
    verts = []
    for i in range(points * 2):
        r = r_outer if i % 2 == 0 else r_inner
        ang = math.pi/2 + i * math.pi / points
        x = cx + r * math.cos(ang)
        y = cy + r * math.sin(ang)
        verts.append((x, y))
    A("G0 Z5.000")
    A(f"G0 X{verts[0][0]:.3f} Y{verts[0][1]:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F1000")
    for (x, y) in verts[1:] + [verts[0]]:
        A(f"G1 X{x:.3f} Y{y:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_random_polyline(seed=42, segments=200, step=2.0, bounds=(0, 120, 0, 120), depth=-1.5):
    import random
    random.seed(seed)
    x0, x1, y0, y1 = bounds
    x = (x0 + x1) / 2
    y = (y0 + y1) / 2
    lines = []
    A = lines.append
    for s in _hdr("RANDOM-POLYLINE"):
        A(s)
    A("G0 Z5.000")
    A(f"G0 X{x:.3f} Y{y:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F1200")
    for _ in range(segments):
        ang = random.random() * 2 * math.pi
        x = min(max(x + step * math.cos(ang), x0), x1)
        y = min(max(y + step * math.sin(ang), y0), y1)
        A(f"G1 X{x:.3f} Y{y:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


def build_triangle_pocket(side=100.0, rows=40, depth=-3.0):
    lines = []
    A = lines.append
    for s in _hdr("TRIANGLE-POCKET"):
        A(s)
    # Equilateral triangle vertices
    xA, yA = 10.0, 10.0
    xB, yB = 10.0 + side, 10.0
    xC, yC = 10.0 + side/2, 10.0 + (math.sqrt(3)/2)*side
    A("G0 Z5.000")
    A(f"G0 X{xA:.3f} Y{yA:.3f}")
    A(f"G1 Z{depth:.3f} F300")
    A("F1000")
    # perimeter
    A(f"G1 X{xB:.3f} Y{yB:.3f}")
    A(f"G1 X{xC:.3f} Y{yC:.3f}")
    A(f"G1 X{xA:.3f} Y{yA:.3f}")
    # simple raster inside (horizontal lines clipped to triangle bbox)
    y_min, y_max = yA, yC
    for i in range(rows):
        y = y_min + (y_max - y_min) * (i / (rows - 1))
        # compute triangle left/right at this y
        # edges AB (horizontal) and AC & BC
        # left x on AC, right x on BC
        # AC: (xA,yA)->(xC,yC)
        t_ac = (y - yA) / (yC - yA) if yC != yA else 0
        x_left = xA + t_ac * (xC - xA)
        # BC: (xB,yB)->(xC,yC)
        t_bc = (y - yB) / (yC - yB) if yC != yB else 0
        x_right = xB + t_bc * (xC - xB)
        if x_left > x_right:
            x_left, x_right = x_right, x_left
        if i % 2 == 0:
            A(f"G1 X{x_right:.3f} Y{y:.3f}")
        else:
            A(f"G1 X{x_left:.3f} Y{y:.3f}")
    for s in _end():
        A(s)
    return "\n".join(lines)


# ---------- Create/Update helper using DB bytes (file_blob) ----------
def create_or_update_program(owner, part_no: str, revision: str, filename: str, gcode_text: str) -> Program:
    """
    Idempotent: if Program(owner, part_no, revision) exists, its bytes are replaced and metadata re-parsed.
    Stores bytes in Program.file_blob (DB), plus file_name/mime; no disk writes needed.
    """
    p = Program.objects.filter(owner=owner, part_no=part_no, revision=revision).first()
    created = False
    if not p:
        p = Program(owner=owner, part_no=part_no, revision=revision)
        created = True

    raw = gcode_text.encode("utf-8")

    # Parse using your tiny_parse_gcode from a text stream
    import io as _io
    parsed = tiny_parse_gcode(_io.StringIO(gcode_text))

    # Fill fields
    p.file_blob = raw
    p.file_name = filename
    p.file_mime = "text/plain"
    p.units = parsed["units"]
    p.abs_mode = parsed["abs"]
    p.bbox_json = parsed["bbox"]
    p.meta_json = parsed["meta"]
    p.est_time_s = parsed["est_time_s"]
    p.save()

    total = parsed['meta'].get('counts', {}).get('G0', 0) + parsed['meta'].get('counts', {}).get('G1', 0)
    print(("✓ Created" if created else "• Updated"),
          f"Program: {p.part_no} {p.revision} (id={p.id})  — Segments {total}")
    return p


def seed_programs(owner):
    programs = []

    # 1: long 3D path
    programs.append(create_or_update_program(owner, "DEMO-3D-LONG", "A", "DEMO-3D-LONG-A.nc", build_long_complex_gcode()))
    # 2: short square
    programs.append(create_or_update_program(owner, "SHORT-DEMO", "A", "SHORT-DEMO-A.nc", build_short_square()))
    # 3: rectangle pocket
    programs.append(create_or_update_program(owner, "RECT-POCKET-80x50", "A", "RECT-POCKET-80x50-A.nc", build_rect_pocket(80, 50, 2.0, -6.0)))
    # 4: spiral square
    programs.append(create_or_update_program(owner, "SPIRAL-SQUARE-100", "A", "SPIRAL-SQUARE-100-A.nc", build_spiral_square(100.0, 2.0, -3.0)))
    # 5: helix bore
    programs.append(create_or_update_program(owner, "HELIX-BORE-Ø24", "A", "HELIX-BORE-24-A.nc", build_helix_bore(r=12.0, depth=-8.0)))
    # 6: grid hatch
    programs.append(create_or_update_program(owner, "GRID-HATCH-10", "A", "GRID-HATCH-10-A.nc", build_grid_hatch(120, 120, 10.0, -1.0)))
    # 7: zigzag plate
    programs.append(create_or_update_program(owner, "ZIGZAG-PLATE", "A", "ZIGZAG-PLATE-A.nc", build_zigzag_plate(120, 80, 5.0, -2.0)))
    # 8: chamfer frame
    programs.append(create_or_update_program(owner, "CHAMFER-FRAME", "A", "CHAMFER-FRAME-A.nc", build_chamfer_frame(120, 80, 5.0, -1.0)))
    # 9: bolt circle
    programs.append(create_or_update_program(owner, "BOLT-CIRCLE-8xR40", "A", "BOLT-CIRCLE-8xR40-A.nc", build_bolt_circle(holes=8, r=40.0)))
    # 10: wave ridges
    programs.append(create_or_update_program(owner, "WAVE-RIDGES", "A", "WAVE-RIDGES-A.nc", build_wave_ridges(120, 60, 3.0, 3.0, -2.0)))
    # 11: star outline
    programs.append(create_or_update_program(owner, "STAR-OUTLINE-5PT", "A", "STAR-OUTLINE-5PT-A.nc", build_star_outline()))
    # 12: random polyline
    programs.append(create_or_update_program(owner, "RANDOM-POLY-200", "A", "RANDOM-POLY-200-A.nc", build_random_polyline(seed=123, segments=200)))

    return programs


def seed_job(owner, program: Program, machine: Machine, material: Material) -> Job:
    job, created = Job.objects.get_or_create(
        owner=owner,
        program=program,
        machine=machine,
        material=material,
        defaults={"stock_lwh_mm": {"L": 140, "W": 140, "H": 25}, "qty": 2, "wcs": "G54", "status": "draft"},
    )
    if created:
        RunLog.objects.create(job=job, user=owner, action="create", notes="seed")
        print(f"✓ Created Job #{job.id} for Program {program.part_no} on {machine.name}")
    else:
        print(f"• Exists Job #{job.id} for Program {program.part_no} on {machine.name}")
    return job


def main():
    # If you still have MEDIA_ROOT set for attachments/legacy files, keep the dir around
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

    user = get_or_create_demo_user()
    machines = seed_machines()
    materials = seed_materials()
    programs = seed_programs(user)

    if machines and materials and programs:
        # seed one job for a meaty program
        seed_job(user, programs[0], machines[0], materials[0])

    print("\nDone. Try login as the demo user, then:")
    print("  Programs:  /")
    print("  Jobs:      /jobs/")
    print("Open DEMO-3D-LONG → hit 3D Simulation. Enjoy the helix + pocket + wavy pass ✨")


if __name__ == "__main__":
    main()