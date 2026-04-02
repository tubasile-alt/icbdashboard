# ICB Performance Dashboard

## Overview
A business intelligence performance dashboard that syncs Excel data from Dropbox and visualizes KPIs, revenue trends, and surgical production metrics through a React web interface.

## Architecture
- **Frontend:** React 19 + Vite + Tailwind CSS + Recharts (port 5000)
- **Backend:** FastAPI + Uvicorn (port 8000)
- **Database:** PostgreSQL (via system `DATABASE_URL` env var) with SQLAlchemy ORM
- **Data Pipeline:** Dropbox API → Excel (Pandas/Openpyxl) → PostgreSQL

## Project Structure
```
backend/
  app/
    main.py          - FastAPI app entry point
    config.py        - Pydantic settings (reads .env)
    models.py        - SQLAlchemy models
    schemas.py       - Pydantic response schemas
    database.py      - DB engine and session setup
    data_service.py  - Dashboard data queries
    sync_job.py      - Background Dropbox sync loop
    dropbox_client.py - Dropbox API client
  requirements.txt
  .env               - Local env vars (DATABASE_URL, DROPBOX_ACCESS_TOKEN, etc.)

frontend/
  src/
    App.jsx          - Main dashboard component
    components/      - KpiCard, UpdateBadge
    lib/api.js       - Axios API client
  vite.config.js     - Vite config (port 5000, host 0.0.0.0, allowedHosts: true)
  .env               - VITE_API_URL=http://localhost:8000
```

## Workflows
- **Start application** - Frontend: `cd frontend && npm run dev` (port 5000, webview)
- **Backend API** - Backend: `cd backend && python -m uvicorn app.main:app --host localhost --port 8000` (port 8000, console)

## Environment Variables
- `DATABASE_URL` - PostgreSQL connection string (set by Replit system)
- `DROPBOX_ACCESS_TOKEN` - Dropbox API token (user must configure)
- `DROPBOX_FOLDER_PATH` - Path to folder in Dropbox with Excel files
- `DROPBOX_FILE_EXTENSION` - File extension to look for (default: .xlsx)
- `UPDATE_INTERVAL_MINUTES` - Sync interval (default: 5)
- `STALE_THRESHOLD_HOURS` - Hours before data is considered stale (default: 6)
- `VITE_API_URL` - Backend API URL for frontend (default: http://localhost:8000)

## Setup Notes
- psycopg2-binary is required for PostgreSQL support (added to requirements.txt)
- The Dropbox sync loop waits 30s after startup before first run to allow server to stabilize
- The backend reads .env from the `backend/` directory
- Frontend proxies `/api` requests to the backend (via Vite proxy config)
- The system `DATABASE_URL` env var takes precedence over the one in backend/.env
