import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any

import sqlite3
from sqlmodel import SQLModel, Field, Session, select, create_engine

from fastapi import FastAPI, Request, HTTPException, Depends, Query
from fastapi.responses import FileResponse, JSONResponse, PlainTextResponse, StreamingResponse, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# -----------------------------------------------------------------------------
# App meta
# -----------------------------------------------------------------------------
APP_NAME = os.getenv("APP_NAME", "Leapfound")
APP_ENV = os.getenv("APP_ENV", "prod")
APP_VERSION = "2.1.0"

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
log = logging.getLogger("leapfound")

# -----------------------------------------------------------------------------
# Security / API Keys
# -----------------------------------------------------------------------------
# Option A: single key in APP_API_KEY
APP_API_KEY = os.getenv("APP_API_KEY", "").strip()

# Option B: JSON array of {key, role, name}
# e.g. API_KEYS_JSON='[{"key":"projectz.3478r8344r45480","role":"admin","name":"Founder"}]'
API_KEYS_JSON = os.getenv("API_KEYS_JSON", "").strip()
CLIENT_KEYS: List[Dict[str, str]] = []
if API_KEYS_JSON:
    try:
        CLIENT_KEYS = json.loads(API_KEYS_JSON)
    except Exception as e:
        log.warning("Invalid API_KEYS_JSON: %s", e)

if APP_API_KEY and not any(k.get("key") == APP_API_KEY for k in CLIENT_KEYS):
    CLIENT_KEYS.append({"key": APP_API_KEY, "role": "admin", "name": "App Key"})

def find_client_by_key(key: str) -> Optional[Dict[str, str]]:
    if not key:
        return None
    for entry in CLIENT_KEYS:
        if entry.get("key") == key:
            return entry
    if APP_API_KEY and key == APP_API_KEY:
        return {"key": APP_API_KEY, "role": "admin", "name": "App Key"}
    return None

def require_api_key(x_api_key: Optional[str], xff: str) -> Dict[str, str]:
    client = find_client_by_key(x_api_key or "")
    if not client:
        log.info("Auth failed from %s", xff)
        raise HTTPException(status_code=401, detail="invalid api key")
    return client

# -----------------------------------------------------------------------------
# DB (SQLite)
# -----------------------------------------------------------------------------
DB_PATH = os.getenv("DB_PATH", "projectz.db")
engine = create_engine(f"sqlite:///{DB_PATH}", connect_args={"check_same_thread": False})

class Txn(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    kind: str = Field(default="expense", index=True)  # 'income' or 'expense'
    amount: float = Field(default=0.0)
    # columns that existed in your earlier runs:
    category_enc: Optional[str] = Field(default=None)
    memo_enc: Optional[str] = Field(default=None)

class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(default_factory=datetime.utcnow, index=True)
    route: str = Field(default="analyze", index=True)
    summary: Optional[str] = Field(default=None)
    content: Optional[str] = Field(default=None)
    ip: Optional[str] = Field(default=None)
    key_last4: Optional[str] = Field(default=None)
    income: float = Field(default=0.0)
    expenses: float = Field(default=0.0)
    net: float = Field(default=0.0)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)

init_db()

# -----------------------------------------------------------------------------
# LLM (optional Ollama)
# -----------------------------------------------------------------------------
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "").strip()  # e.g. http://127.0.0.1:11434
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "").strip()

def _llm_suggest(prompt: str) -> str:
    # If Ollama is not configured, return a deterministic fallback suggestion.
    if not (OLLAMA_BASE and OLLAMA_MODEL):
        return f"Suggestion (fallback): Focus on top 3 revenue drivers next week; cut 1 low-ROI expense; run a 48-hour promo."

    # Lazy import requests to avoid forcing dependency if unused
    try:
        import requests  # type: ignore
    except Exception:
        return "Suggestion (fallback): Streamline costs and test a mid-week promo; enable weekly KPI review."

    try:
        r = requests.post(
            f"{OLLAMA_BASE}/api/generate",
            json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
            timeout=60,
        )
        r.raise_for_status()
        data = r.json()
        text = (data.get("response") or "").strip()
        return text or "No suggestion produced."
    except Exception as e:
        log.warning("Ollama error: %s", e)
        return "Suggestion (fallback): Improve margins by renegotiating suppliers; test bundling; refine pricing."

# -----------------------------------------------------------------------------
# FastAPI app
# -----------------------------------------------------------------------------
app = FastAPI(title=APP_NAME, version=APP_VERSION)

# CORS (open for now; you can restrict later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ALLOW_ORIGINS", "*").split(","),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Security headers
@app.middleware("http")
async def security_headers(request: Request, call_next):
    resp = await call_next(request)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "no-referrer"
    resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
    resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return resp

# Require API key for /api/*
@app.middleware("http")
async def api_key_guard(request: Request, call_next):
    path = request.url.path or ""
    if path.startswith("/api/"):
        x_api_key = request.headers.get("X-API-Key", "")
        xff = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
        try:
            request.state.client = require_api_key(x_api_key, xff)
        except HTTPException as e:
            return JSONResponse(status_code=e.status_code, content={"detail": e.detail})
    return await call_next(request)

# -----------------------------------------------------------------------------
# Utility: totals
# -----------------------------------------------------------------------------
def _sum_all(s: Session) -> (float, float, float):
    txns: List[Txn] = s.exec(select(Txn)).all()
    inc = sum(t.amount for t in txns if t.kind.lower() == "income")
    exp = sum(t.amount for t in txns if t.kind.lower() == "expense")
    net = inc - exp
    return inc, exp, net

# -----------------------------------------------------------------------------
# Health
# -----------------------------------------------------------------------------
@app.get("/health")
def health():
    pdf_available = False
    try:
        import reportlab  # type: ignore
        pdf_available = True
    except Exception:
        pdf_available = False

    return {
        "status": "ok",
        "env": APP_ENV,
        "db": f"/app/{os.path.basename(DB_PATH)}" if os.getenv("FLY_APP_NAME") else os.path.abspath(DB_PATH),
        "ollama_model": OLLAMA_MODEL,
        "pdf": pdf_available,
        "enc": False,
    }

# -----------------------------------------------------------------------------
# API: analyze / suggest / report
# -----------------------------------------------------------------------------
@app.get("/api/analyze")
def api_analyze(request: Request):
    client = getattr(request.state, "client", {})
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    key_last4 = (client.get("key") or "____")[-4:]

    with Session(engine) as s:
        inc, exp, net = _sum_all(s)
        summary = f"Income={inc:.2f}, Expenses={exp:.2f}, Net={net:.2f}"
        content = f"{summary}\nGenerated: {datetime.utcnow().isoformat()}Z"

        rpt = Report(
            route="analyze",
            summary=summary,
            content=content,
            ip=ip,
            key_last4=key_last4,
            income=inc,
            expenses=exp,
            net=net,
        )
        s.add(rpt)
        s.commit()
        s.refresh(rpt)

        return {"ok": True, "report_id": rpt.id, "summary": summary}

@app.get("/api/suggest")
def api_suggest(request: Request, q: str = Query("", alias="q")):
    client = getattr(request.state, "client", {})
    ip = request.headers.get("X-Forwarded-For", request.client.host if request.client else "unknown")
    key_last4 = (client.get("key") or "____")[-4:]

    prompt = q.strip() or "How to improve profit next week for a small business?"
    suggestion = _llm_suggest(prompt)

    with Session(engine) as s:
        inc, exp, net = _sum_all(s)
        summary = f"Suggestion created. Net={net:.2f}"
        content = f"Q: {prompt}\nA: {suggestion}"

        rpt = Report(
            route="suggest",
            summary=summary,
            content=content,
            ip=ip,
            key_last4=key_last4,
            income=inc,
            expenses=exp,
            net=net,
        )
        s.add(rpt)
        s.commit()
        s.refresh(rpt)

        return {"ok": True, "report_id": rpt.id, "suggestion": suggestion}

@app.get("/api/report")
def api_report():
    with Session(engine) as s:
        rpt = s.exec(select(Report).order_by(Report.ts.desc())).first()
        if not rpt:
            return {"ok": True, "report": None}
        return {
            "ok": True,
            "report": {
                "id": rpt.id,
                "ts": rpt.ts.isoformat() + "Z",
                "route": rpt.route,
                "summary": rpt.summary,
                "content": rpt.content,
                "income": rpt.income,
                "expenses": rpt.expenses,
                "net": rpt.net,
            },
        }

@app.get("/api/report_file")
def api_report_file():
    with Session(engine) as s:
        rpt = s.exec(select(Report).order_by(Report.ts.desc())).first()
        if not rpt:
            raise HTTPException(status_code=404, detail="no report available")
        text = f"[{APP_NAME}] Report {rpt.id} @ {rpt.ts.isoformat()}Z\n{rpt.summary}\n\n{rpt.content or ''}\n"
        filename = f"report_{rpt.id}.txt"
        return StreamingResponse(
            iter([text]),
            media_type="text/plain",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

@app.get("/api/history")
def api_history(limit: int = 10):
    limit = max(1, min(100, limit))
    with Session(engine) as s:
        rows: List[Report] = s.exec(select(Report).order_by(Report.ts.desc()).limit(limit)).all()
        return {
            "ok": True,
            "items": [
                {
                    "id": r.id,
                    "ts": r.ts.isoformat() + "Z",
                    "route": r.route,
                    "summary": r.summary,
                    "income": r.income,
                    "expenses": r.expenses,
                    "net": r.net,
                }
                for r in rows
            ],
        }

@app.get("/api/metrics")
def api_metrics(days: int = 30):
    days = max(1, min(365, days))
    since = datetime.utcnow() - timedelta(days=days)
    with Session(engine) as s:
        rows: List[Report] = s.exec(select(Report).where(Report.ts >= since)).all()
        # If no reports, compute from Txn
        if not rows:
            inc, exp, net = _sum_all(s)
            return {"ok": True, "since_days": days, "income": inc, "expenses": exp, "net": net}
        inc = sum(r.income for r in rows)
        exp = sum(r.expenses for r in rows)
        net = sum(r.net for r in rows)
        return {"ok": True, "since_days": days, "income": inc, "expenses": exp, "net": net}

@app.get("/api/timeseries")
def api_timeseries(days: int = 30):
    days = max(1, min(365, days))
    since = datetime.utcnow() - timedelta(days=days)
    with Session(engine) as s:
        rows: List[Report] = s.exec(
            select(Report).where(Report.ts >= since).order_by(Report.ts)
        ).all()
        return {
            "ok": True,
            "since_days": days,
            "points": [
                {
                    "ts": r.ts.isoformat() + "Z",
                    "income": r.income,
                    "expenses": r.expenses,
                    "net": r.net,
                    "route": r.route,
                }
                for r in rows
            ],
        }

# -----------------------------------------------------------------------------
# Static Frontend
# -----------------------------------------------------------------------------
# Serve built Vite assets (ensure your frontend build was copied to ./static)
if os.path.isdir("static/assets"):
    app.mount("/assets", StaticFiles(directory="static/assets"), name="assets")
if os.path.isdir("static"):
    app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/", include_in_schema=False)
def root_get():
    if os.path.isfile("static/index.html"):
        return FileResponse("static/index.html")
    return PlainTextResponse("Frontend is not built yet. Build and copy to ./static", status_code=200)

@app.head("/", include_in_schema=False)
def root_head():
    return Response(status_code=200)

# -----------------------------------------------------------------------------
# Uvicorn entry (local dev)
# -----------------------------------------------------------------------------
if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
