# CNC-3 — Three-Axis CNC Manager

Upload and manage **3-axis G-code programs**, preview toolpaths, generate printable **setup packets**, and track jobs from **Draft → Submitted → Approved**. CNC-3 also integrates **DeepSeek** so you can **chat**, **review**, and (optionally) **generate** G-code that’s auto-validated and saved as a Program.

---

## 📸 Screenshot / Logo

> Replace this placeholder with your screenshot/logo. Keep descriptive alt text.

![CNC-3 app](mian_app/static/images/image.png)

---

## 🔗 Live App & Planning

- **Deployed URL:** https://cnc3.onrender.com
- **Planning materials:**
  - Wireframes: `docs/wireframes.pdf`
  - ERD: `docs/erd.png`

> Replace the URL and files above with your own.

---

## 🧰 What this app does (and why)

CNC-3 is a focused manufacturing helper for small shops and hobbyists:

- **Programs**
  - Upload `.nc` / `.gcode` / `.tap` (≤ 5 MB).
  - Files stored in Postgres as **bytea blobs** (`file_blob`) with `file_name` + `file_mime`. (A `FileField` exists as an optional FS fallback.)
  - Built-in parser extracts **units** (G20/G21), **mode** (G90/G91), **bbox**, **move counts**, **estimated time**, and **lint warnings** (e.g., no WCS, unsafe rapids, feed before cut).
  - 2D backplot (XY): dashed rapids (G0) vs solid cuts (G1).

- **Jobs**
  - Binds a **Program** to a **Machine** and **Material**.
  - Track **stock** (L/W/H in mm), **qty**, **WCS** (e.g., G54) and status: **draft → submitted → approved**.
  - **RunLog** records actions (create/update/submit/approve).

- **Setup Packets**
  - Printable HTML & **PDF** (ReportLab) with program metadata, bbox, time, lints, stock, and machine/material info.

- **DeepSeek**
  - **/ai/chat/**: machining Q&A via LLM.
  - **/ai/chat/program/<id>/**: program-aware review (sends truncated G-code and metadata for targeted feedback).
  - *(Optional UI)* **/ai/generate/**: prompt → LLM returns fenced `gcode` → parsed, linted, and saved as a new Program.

**Why built:** to demo owner-scoped CRUD, binary file storage in Postgres, a practical G-code parser, and a realistic way AI can assist CNC workflows.

---

## 🗃️ Data Model (High-Level)

- **Program** → `owner`, `part_no`, `revision`, `file_blob`, `file_name`, `file_mime`, `units`, `abs_mode`, `bbox_json`, `meta_json`, `est_time_s`, `created_at`
- **ProgramVersion** → `program`, `file_blob`, `file_name`, `file_mime`, `comment`, `created_at`
- **Job** → `owner`, `program`, `machine`, `material`, `stock_lwh_mm` (`{L,W,H}`), `qty`, `wcs`, `status`, `created_at`
- **Machine** → `name`, `max_rpm`, `max_feed`, `rapid_xy`, `rapid_z`, `safe_z`
- **Material** → `name`, `hardness`, `feedspeeds_json`
- **RunLog** → `job`, `user`, `action`, `notes`, `ts`
- **Attachment** → `job`, `file_blob` (+ optional `file`), `file_name`, `file_mime`, `uploaded_by`, `uploaded_at`

> DB-first storage (bytea) with optional filesystem fallback keeps deployments simple and portable.

---

## 🧭 Routes (High Level)

- **Auth** (Django built-ins):  
  `/auth/login`, `/auth/logout`  
  **Signup (custom):** `/signup`

- **Programs:**  
  `/` (list), `/programs/new`, `/programs/<id>`, `/programs/<id>/preview.json`, `/programs/<id>/edit`, `/programs/<id>/delete`  
  `/programs/<id>/history`, `/programs/<id>/versions/<ver_id>/download`, `/programs/<id>/diff/<ver_id>`

- **Jobs:**  
  `/jobs/` (list), `/jobs/new/<program_id>`, `/jobs/<id>`, `/jobs/<id>/edit`, `/jobs/<id>/delete`,  
  `/jobs/<id>/submit`, `/jobs/<id>/approve`, `/jobs/<id>/packet`, `/jobs/<id>/packet.pdf`, `/jobs/<id>/lint.json`

- **Attachments:**  
  `/jobs/<job_id>/attachments/new`, `/attachments/<id>/download`, `/attachments/<id>/delete`

- **AI (DeepSeek):**  
  `POST /ai/chat/`  
  `POST /ai/chat/program/<id>/`

- *(Optional UI)* **AI Generate Program:**  
  `/ai/generate/` (form + “Generating…” overlay) → POST to `/ai/chat/` → saves Program on success

---

## 🛠️ Technology

- **Backend:** Django 5 (templates/SSR, forms, auth, CSRF)
- **DB:** PostgreSQL (prod) / SQLite (dev)
- **Static/Media:** WhiteNoise + Django staticfiles
- **PDF:** ReportLab
- **AI:** DeepSeek via OpenAI Python SDK (custom `base_url`)
- **Frontend:** Server-rendered HTML + lightweight JS (canvas backplot)
- **Runtime:** Python 3.11+

---

## 🔒 Auth & Authorization

- **Auth:** Django sessions.
- **Authorization:** all lists are **owner-scoped**; only the **owner** sees Edit/Delete and can modify a record.
- **CSRF:** enabled site-wide; JSON endpoints expect `application/json`.
- **Admin:** use `/admin/` (superuser).

---

## 🧪 Lints (examples)

- No G20/G21 units
- No G90/G91 mode
- No work offset (G54..G59)
- Cut before feedrate set
- Cut before spindle on (M3/M4)
- Rapid Z below machine **safe Z**
- Job stock bounds exceeded (XY or Z)

*Lints appear in Program metadata and in Job packet views.*

---

## 🧯 Troubleshooting

- **PowerShell JSON error:** Use `ConvertTo-Json` as shown in README examples.
- **“DEEPSEEK_API_KEY is not set”:** Confirm `.env` and restart the server.
- **Program upload shows but preview fails:** Ensure the file is text G-code (UTF-8 or ASCII). Max **5 MB**.
- **Admin login didn’t work:** Rerun `python manage.py createsuperuser`.

---

## 📚 Attributions

- Django
- ReportLab (PDF)
- OpenAI Python SDK *(used with a custom `base_url` for DeepSeek)*
- DeepSeek API  
- Any icons, images, or fonts used in `/static` or `/docs` should retain their original licenses.

---

## 🧱 Technologies Used

- Python 3.11+, Django 5
- PostgreSQL (prod), SQLite (dev)
- WhiteNoise, ReportLab
- OpenAI Python SDK + DeepSeek
- Vanilla JS (canvas backplot), HTML/CSS (SSR)

---

## 🗺️ Next Steps (Stretch Goals)

- Arc support in parser/backplot (G2/G3 preview with approximated segments).
- Tool table + multi-tool lints (spindle RPM/feed checks vs material & tool geometry).
- Collision/safe-Z simulator: highlight potential workholding collisions and red-zone rapids.
- Versioning UX: “Save as new version” on edit, visual diff overlay in the backplot.
- **AI Generate UI:** prompt → fenced `gcode` → validate → save Program (with a live **Generating…** overlay).
- Shop floor mode: QR code job packets and kiosk-style “Run / Pause / Log issue” flow.
- Export: zipped job packet (PDF + G-code + setup JSON).
- S3 / GCS storage option for large files.


