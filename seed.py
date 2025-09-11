# seed.py  —  run with:  python seed.py
import os

# --- Django setup ---
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "cnc3.settings")
import django  # noqa: E402
django.setup()

from django.conf import settings  # noqa: E402
from django.contrib.auth import get_user_model  # noqa: E402
from django.core.files.base import ContentFile  # noqa: E402

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
                "10": {"flutes": 3, "rpm": 8000, "chipload_mm_per_tooth": 0.040, "doc_axial_mm": 5.0, "doc_radial_mm": 2.5},
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
        dict(name="6061-T6 Aluminum (example)", hardness="HB ~95", feedspeeds_json=al6061),
        dict(name="1018 Mild Steel (example)", hardness="BHN ~120", feedspeeds_json=steel1018),
        dict(name="Acrylic PMMA (example)", hardness="-", feedspeeds_json=pmma),
    ]
    out = []
    for d in data:
        obj, created = Material.objects.get_or_create(name=d["name"], defaults=d)
        print(("✓ Created" if created else "• Exists"), "Material:", obj.name)
        out.append(obj)
    return out


def create_or_update_program(owner, part_no: str, revision: str, filename: str, gcode_text: str) -> Program:
    """
    Idempotent: if Program(owner, part_no, revision) exists, its file is replaced and metadata re-parsed.
    """
    p = Program.objects.filter(owner=owner, part_no=part_no, revision=revision).first()
    created = False
    if not p:
        p = Program(owner=owner, part_no=part_no, revision=revision)
        created = True

    # Save/replace file contents
    p.file.save(filename, ContentFile(gcode_text.encode("utf-8")), save=False)

    # Parse using your tiny_parse_gcode (which also produces 3D mm segments/bbox for the viewer endpoint)
    with open(p.file.path, "r", encoding="utf-8", errors="ignore") as fh:
        parsed = tiny_parse_gcode(fh)

    p.units = parsed["units"]
    p.abs_mode = parsed["abs"]
    p.bbox_json = parsed["bbox"]
    p.meta_json = parsed["meta"]
    p.est_time_s = parsed["est_time_s"]
    p.save()

    print(("✓ Created" if created else "• Updated"), f"Program: {p.part_no} {p.revision} (id={p.id})")
    return p


def seed_programs(owner):
    # AB-123: simple metric square pocket
    gcode_metric = """%
(AB-123 C — Square pocket, metric)
G21 G90 G17
G54
T1 M6
S12000 M3
G0 Z10
G0 X0 Y0
F600
G1 Z-2 F200
G1 X40 Y0
G1 X40 Y30
G1 X0  Y30
G1 X0  Y0
G0 Z10
M5
G0 X0 Y0
M30
%"""

    # JIG-45: 3D demo (metric) — 3 depths and a ramp for real 3D lines
    gcode_jig45_3d = """%
(JIG-45 A — 3D demo, G0/G1 only)
G21 G90 G17
G54
G0  Z15
G0  X0 Y0
S12000 M3
F800

(Go to start, surface touch)
G0  X10 Y10
G1  Z0    F300

(Depth 1 @ Z=0: rectangle 60x30 from (10,10) to (70,40))
G1  X70 Y10  F800
G1  X70 Y40
G1  X10 Y40
G1  X10 Y10

(Depth 2 @ Z=-1.5)
G1  Z-1.5  F300
G1  X70 Y10  F800
G1  X70 Y40
G1  X10 Y40
G1  X10 Y10

(Depth 3 @ Z=-3.0)
G1  Z-3.0  F300
G1  X70 Y10  F800
G1  X70 Y40
G1  X10 Y40
G1  X10 Y10

(Ramp up and out in 3D so you see sloped lines)
G1  X70 Y25 Z-2.0
G1  X70 Y45 Z-1.0
G1  X50 Y45 Z0.0

(Exit)
G0  Z15
M5
G0  X0 Y0
M30
%"""

    p1 = create_or_update_program(owner, "AB-123", "C", "AB-123-C.nc", gcode_metric)
    p2 = create_or_update_program(owner, "JIG-45", "A", "JIG-45-A-3D.nc", gcode_jig45_3d)
    return [p1, p2]


def seed_job(owner, program: Program, machine: Machine, material: Material) -> Job:
    job, created = Job.objects.get_or_create(
        owner=owner,
        program=program,
        machine=machine,
        material=material,
        defaults={"stock_lwh_mm": {"L": 100, "W": 60, "H": 12}, "qty": 4, "wcs": "G54", "status": "draft"},
    )
    if created:
        RunLog.objects.create(job=job, user=owner, action="create", notes="seed")
        print(f"✓ Created Job #{job.id} for Program {program.part_no} on {machine.name}")
    else:
        print(f"• Exists Job #{job.id} for Program {program.part_no} on {machine.name}")
    return job


def main():
    # Ensure media directory exists
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)

    user = get_or_create_demo_user()
    machines = seed_machines()
    materials = seed_materials()
    programs = seed_programs(user)

    if machines and materials and programs:
        seed_job(user, programs[0], machines[0], materials[0])

    print("\nDone. Try login as the demo user, then:")
    print("  Programs:  /")
    print("  Jobs:      /jobs/")
    print("Open JIG-45 → you should see a proper 3D path with multiple depths + a ramp.")


if __name__ == "__main__":
    main()
