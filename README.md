# CNC-3 — Three-Axis CNC Manager

Upload and manage **3-axis G-code programs**, preview their toolpaths, and generate printable **setup sheets**. Create **Jobs** by binding a Program to a Machine and Material, then track status from **Draft → Submitted → Approved**. Built with **Django templates** (session auth, SSR), deployable on Render/Railway/Fly.

---

## Screenshot / Logo

> Replace the image below with your own screenshot or logo (keep alt text).

![CNC-3 app screenshot showing a 2D toolpath backplot, program metadata, and navigation sidebar](docs/screenshot.png)

---

## Live App

- **Deployed URL:** https://YOUR-APP-URL.example.com  
- **Planning materials:**  
  - Wireframes: `docs/wireframes.pdf`  
  - ERD: `docs/erd.png`

---

## Why this app

A focused CRUD app that demonstrates:
- File uploads + server-side parsing (G-code).
- Owner-scoped data (per-user) with session-based auth/authorization.
- Accessible, consistent UI using CSS Grid/Flex.
- Deployable, production-ready Django setup with static/media handling.

---

## Features (MVP)

- **Auth (session-based):** login/logout using Django auth.
- **Authorization:** guests cannot create/update/delete; **only the owner** of a record sees Edit/Delete controls or can modify it.
- **Entities (plus User):**
  - **Program** (belongs to User): upload G-code; stored metadata (units/mm-in, abs/inc, bbox, time estimate, lints); 2D backplot viewer.
  - **Job** (belongs to User): binds Program + Machine + Material; stock size, WCS, qty; status flow; printable setup sheet.
  - **Machine:** caps like max RPM/feed, rapid rates, safe Z.
  - **Material:** name, hardness, optional feeds/speeds table.
- **Full CRUD:** Programs, Jobs, Machines, Materials (Machines/Materials can be admin-only).
- **2D Backplot:** XY canvas view with dashed rapids (G0) and solid cuts (G1; optional arcs G2/G3).
- **Lint checks (starter set):** safe-Z before XY rapid, coolant/spindle off at end, max feed/RPM vs machine, WCS set early.
- **Setup Sheet:** print-styled HTML (PDF optional) with bbox/time/tooling summary.

---

## Meets GA Unit 4 Requirements

- **Frontend:** Django **templates** render UI (SSR).  
- **DB:** SQLite (dev) / PostgreSQL (prod).  
- **Auth:** Django session-based authentication.  
- **Authorization:** guests blocked from create/update/delete; UI for edit/delete shown only to record owner.  
- **Data entities:** Program, Job, Machine, Material (Program & Job relate to User).  
- **Full CRUD:** implemented for at least two entities (Program, Job) plus Machine/Material.  
- **Deployed:** hosted online (link above).  

### Code conventions & quality
- Conventional Django layout, pluralized list names, no dead code/prints.
- App runs without terminal or browser console errors.
- Proper indentation and consistent style.

### UI/UX & Accessibility
- Consistent theme (dark slate + blue accent), Grid/Flex layout.
- Intuitive navigation via sidebar links; no manual URL typing needed.
- WCAG 2.0 AA color contrast verified for text/background.
- Edit forms are **pre-filled** with existing data.
- Owner-only edit/delete UI.
- All images have descriptive **alt** text.
- No text over busy images that harms readability.
- Styled buttons with visible focus states.

### Git & GitHub
- Single visible contributor on a **public** repo (e.g., `cnc-3`).
- Commits from day 1 → presentation; descriptive messages.
- If pivoting, keep old repo; don’t delete history.

---

## Data Model (ERD)


**Program**: part_no, revision, file, units, abs_mode, bbox_json, meta_json, est_time_s, owner → User  
**Job**: program → Program, machine → Machine, material → Material, stock_lwh_mm{L,W,H}, qty, wcs, status, owner → User  
**Machine**: name, max_rpm, max_feed, rapid_xy, rapid_z, safe_z  
**Material**: name, hardness, feedspeeds_json

---

## Routes (high level)

- **Auth:** `/auth/login`, `/auth/logout` (Django builtin)
- **Programs:** `/` (list), `/programs/new`, `/programs/:id`, `/programs/:id/preview.json`
- **Jobs:** `/jobs/` (list), `/jobs/new/:program_id`, `/jobs/:id`, `/jobs/:id/edit`, `/jobs/:id/delete`, `/jobs/:id/packet`
- **Machines/Materials:** `/machines/…`, `/materials/…` (admin-only or owner-scoped)

---

## Technology

- **Backend:** Django 5 (templates, auth, CSRF, forms)
- **Server:** Uvicorn (ASGI)
- **DB:** SQLite (dev), PostgreSQL (prod)
- **Static/Media:** WhiteNoise + Django staticfiles
- **Frontend:** Server-rendered HTML + vanilla JS canvas backplot
- **Dev tools:** Python 3.11+, venv

---

## Getting Started

### Prerequisites
- Python **3.11+**
- (Prod) A PostgreSQL database URL
