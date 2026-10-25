# Image-to-Calendar Application

> **Full-Stack Application converting screenshots of assignments, syllabus schedules, and event announcements into Google Calendar events using Python, FastAPI, JavaScript, OCR, and Google Calendar API.**

![Python](https://img.shields.io/badge/Python-3.14-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-green.svg)
![OCR](https://img.shields.io/badge/OCR-Tesseract_5.5%20%2F%20Vision-orange.svg)
![Google Calendar](https://img.shields.io/badge/Google%20Calendar%20API-v3-blue.svg)
![Frontend](https://img.shields.io/badge/Frontend-Vanilla%20JS%20%26%20CSS3-purple.svg)

---

## Resume Alignment & Technical Features

### 1. Manual Calendar Entry Automation
- Converts screenshots of Canvas/Blackboard assignments, academic schedules, and flyers directly into structured calendar events.
- Drag-and-drop file upload, file browsing, and **instant clipboard paste** (`Ctrl+V` / `⌘V` for immediate screenshot processing).

### 2. Unstructured Image-to-Data Transformation (FastAPI Backend)
- **OCR Engine**: Tesseract 5.5.2 extraction pipeline with token-level bounding boxes and confidence score analytics.
- **Text Normalization**: Resolves OCR misreads (e.g., `11.59 pn` → `11:59 PM`, `11|59` → `11:59`, broken line hyphens, smart dashes).
- **Intelligent Entity Parsing**: Extracts event titles, dates, time ranges, locations (physical rooms or Zoom links), and categorizes into Exam, Assignment, Class, Work, Meeting, or Social.

### 3. Validation & Confirmation Workflow
- **Ambiguous Date Detection**: Flags ambiguous formats (e.g. `04/05/2026` vs `05/04/2026`) and missing years.
- **Missing Time Detection**: Detects missing times, suggests context-aware defaults (11:59 PM for assignments), and enables inline time editing.
- **Duplicate Event Prevention**: Detects existing calendar events matching the title and date window using sequence similarity.
- **Unreliable OCR Alerts**: Highlights low-confidence lines (<60%) for user confirmation.

### 4. Google Calendar API Integration & Algorithmic Priority Advisor
- **Schedule Conflict Detection**: Identifies overlapping calendar entries for the specified time window.
- **Priority Advisory Algorithm**:
  - Compares event importance using category weights (`Exam: 9-10`, `Assignment: 8`, `Work: 7`, `Class: 6`, `Meeting: 5`, `Social: 3`).
  - Factors in grade percentages (e.g., "20% of final grade") and mandatory attendance markers.
  - Generates clear machine advice explaining why one event takes precedence and suggests concrete action.
  - Quick action: **Auto-Shift (+1 Hour)** to reschedule and resolve conflicts with a single click.
- **Dual Mode**:
  - **Live Google Calendar**: Connects via OAuth 2.0 (`googleapiclient.discovery.build('calendar', 'v3')`).
  - **Live Calendar Sandbox**: Pre-populated simulated calendar environment for instantaneous demonstrations without requiring GCP console setup.
  - **Standard .ICS Download**: Generates RFC 5545 compliant `.ics` files importable into Apple Calendar, Google Calendar, or Microsoft Outlook.

---

## Project Structure

```
calendermaker/
├── backend/
│   ├── main.py              # FastAPI server, endpoints, CORS & static mounting
│   ├── ocr_service.py        # Tesseract OCR extraction & text normalization
│   ├── parser_service.py     # Date/time extraction, entity regex & category heuristics
│   ├── conflict_advisor.py   # Overlap detection, duplicate matching & priority advisor
│   └── calendar_service.py   # Google Calendar API v3 client, Sandbox & .ICS exporter
├── frontend/
│   ├── index.html           # Modern semantic HTML5 interface
│   ├── style.css            # Dark mode glassmorphism design system
│   └── app.js               # Frontend controller, reactive validation & API integration
├── samples/                 # High-fidelity demo screenshot assets
│   ├── assignment_canvas.png # Canvas homework due date (duplicate check demo)
│   ├── event_flyer.png       # Hackathon keynote flyer (conflict & priority advisory demo)
│   └── schedule_courses.png  # University course timetable (multi-event demo)
├── tests/
│   └── test_pipeline.py     # Comprehensive automated pytest test suite
└── requirements.txt         # Python project dependencies
```

---

## Quickstart Guide

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Run Automated Tests
```bash
PYTHONPATH=. pytest tests/test_pipeline.py -v
```

### 3. Start the Server

Copy `.env.example` to `.env` and replace every placeholder before deploying. The populated `.env` and Google credential files are ignored by Git and Docker.

```bash
uvicorn backend.main:app --host 127.0.0.1 --port 8080
```
Open your browser to: **`http://127.0.0.1:8080`**

---

## Live Demo Walkthrough

1. **Test Hackathon Flyer (Schedule Conflict & Priority Advisor)**:
   - Click the **"Hackathon Flyer (Conflict & Priority)"** demo button.
   - The app extracts the event: `ANNUAL CAMPUS HACKATHON 2026` on Oct 24, 2:30 PM - 4:30 PM.
   - It flags a **Schedule Conflict** against `CS 101 Midterm Examination` (14:00 - 16:00).
   - The **Priority Advisor** clearly explains: *Exam (Priority 9/10) takes precedence over Event (Priority 7/10). We advise keeping CS 101 Midterm Examination.*
   - Click **"Auto-Shift (+1 Hour)"** — the app immediately shifts the time and re-validates!

2. **Test Canvas Assignment (Duplicate Event Detection)**:
   - Click **"Canvas Assignment (Duplicate Check)"**.
   - Extracts `CS 101 - Homework 4: Dynamic Programming & Recursion` due Oct 24 at 11:59 PM.
   - Accurately detects that an event already exists on Google Calendar.

3. **Test Course Schedule (Multi-Event Block Splitting)**:
   - Click **"Course Schedule (Multi-Event)"**.
   - Accurately parses multiple courses (`CS 210`, `MATH 251`, `CHEM 102`) into individual validated cards.

4. **Sync / Export**:
   - Click **"Confirm & Sync to Google Calendar"** or **"Download .ICS File"**.

---

## Connecting Your Real Google Calendar (Step-by-Step)

The web app includes an **In-App Onboarding Wizard** so you can connect your actual Google Calendar directly through the browser:

1. Click the **"Connect Google"** button in the header.
2. Copy the pre-filled **Authorized Redirect URI** (e.g. `http://localhost:8080/api/calendar/oauth-callback` or your production domain).
3. In [Google Cloud Console](https://console.cloud.google.com/apis/credentials):
   - Enable the **Google Calendar API**.
   - Create an **OAuth 2.0 Client ID** (Application type: *Web application*).
   - Paste the copied Redirect URI under **Authorized redirect URIs**.
4. Configure `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` in your private `.env` file, or place an ignored `credentials.json` in the project root.
5. Restart the app, click **"Sign in with Google"**, and complete the consent screen.
6. The app will immediately switch to live mode, showing `🟢 Google Calendar: yourname@gmail.com`.
7. Any events confirmed will now be created on your **real Google Calendar**, complete with a direct **"Open in Google Calendar"** link!

---

## Publishing as a Mobile Web App

### 1. Mobile PWA Installation (iOS & Android)
- The app includes a `manifest.json` and mobile meta tags.
- On iPhone (Safari): Tap the **Share** button → tap **"Add to Home Screen"**.
- On Android (Chrome): Tap the **three dots** menu → tap **"Install App"** or **"Add to Home screen"**.
- You now have a standalone, full-screen mobile app that can take photos of syllabi or upload screenshots directly!

### 2. Deploying Live to the Cloud (1-Click Options)
You can deploy this FastAPI + JavaScript project to any platform:
- Set `PRODUCTION=true`, `PUBLIC_URL`, `ADMIN_PASSWORD`, `SESSION_SECRET_KEY`, and the Google OAuth variables in the hosting provider's secret/environment settings. Never paste secret values into committed files.
- **Render.com**: Connect your GitHub repository, choose *Web Service*, Environment: *Python*, Build Command: `pip install -r requirements.txt && apt-get install -y tesseract-ocr`, Start Command: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`.
- **Railway.app**: New Project → Deploy from GitHub Repo → add Tesseract package → deploy.
- **Fly.io** or **Docker**: Use a standard `python:3.11-slim` container with `apt-get install -y tesseract-ocr-all`.

