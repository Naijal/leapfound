# main.py — Project Z (secure API-first, with analytics & export)
from __future__ import annotations

import os, re, csv, time, requests
from hashlib import sha256
from typing import Optional, Deque, Dict
from collections import deque
from datetime import datetime, timedelta

import pandas as pd
from dotenv import load_dotenv
from fastapi import FastAPI, Query, UploadFile, File, Header, HTTPException
from fastapi.responses import JSONResponse, FileResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from sqlmodel import SQLModel, Field, create_engine, Session, select, func

# ---------------------- config ----------------------
load_dotenv()

LLM_PROVIDER = os.getenv("LLM_PROVIDER", "ollama")    # ollama | openai | offline
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL  = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OLLAMA_MODEL  = os.getenv("OLLAMA_MODEL", "mistral:7b-instruct")  # must exist in `ollama list`
APP_API_KEY   = os.getenv("APP_API_KEY", "projectz_dev_key")      # set a real secret in .env

DB_URL = "sqlite:///projectz.db"
engine = create_engine(DB_URL, connect_args={"check_same_thread": False})

app = FastAPI(title="Project Z — Secure API", version="0.3.0")

# minimal CORS (add your real frontend origin(s) later)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://127.0.0.1:8000", "http://localhost:8000"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

# folders for static & exports
os.makedirs("static", exist_ok=True)
os.makedirs("exports", exist_ok=True)
app.mount("/static", StaticFiles(directory="static"), name="static")

# ---------------------- DB model ----------------------
class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow, index=True)

    # request context
    route: str = Field(index=True)
    ip: Optional[str] = None
    api_key_hash: Optional[str] = None

    # generated content
    summary: str
    content: str

    # numeric analytics (parsed from summary)
    income: Optional[float] = Field(default=None, index=True)
    expenses: Optional[float] = Field(default=None, index=True)
    net: Optional[float] = Field(default=None, index=True)

@app.on_event("startup")
def on_startup():
    # create table
    SQLModel.metadata.create_all(engine)
    # lightweight migration to add numeric columns if missing
    with engine.connect() as conn:
        cols = {row[1] for row in conn.exec_driver_sql("PRAGMA table_info(Report);")}
        adds = []
        if "income"   not in cols: adds.append(("income",   "REAL"))
        if "expenses" not in cols: adds.append(("expenses", "REAL"))
        if "net"      not in cols: adds.append(("net",      "REAL"))
        for name, typ in adds:
            conn.exec_driver_sql(f'ALTER TABLE "Report" ADD COLUMN "{name}" {typ};')

# ---------------------- auth & rate limit ----------------------
RATE_BUCKETS: Dict[str, Deque[float]] = {}
RATE_WINDOW_SEC = 60
RATE_MAX_REQS   = 30  # per key per minute

def require_api_key(x_api_key: str | None, client_ip: str | None):
    if x_api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")
    # simple token bucket
    now = time.time()
    q = RATE_BUCKETS.setdefault(x_api_key, deque())
    while q and now - q[0] > RATE_WINDOW_SEC:
        q.popleft()
    if len(q) >= RATE_MAX_REQS:
        raise HTTPException(status_code=429, detail="rate limit exceeded")
    q.append(now)
    return True

# ---------------------- helpers ----------------------
def summarise_transactions(csv_path: str = "transactions.csv") -> str:
    """Create a sample CSV if missing, then return a canonical summary string."""
    if not os.path.exists(csv_path):
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            csv.writer(f).writerows([
                ["date","description","amount","type"],
                ["2025-10-01","Online sale","320","credit"],
                ["2025-10-02","Inventory purchase","120","debit"],
                ["2025-10-03","Marketing ad","60","debit"],
                ["2025-10-04","Online sale","400","credit"],
                ["2025-10-05","Utility bill","80","debit"],
            ])
    df = pd.read_csv(csv_path)
    df["amount"] = df["amount"].astype(float)
    inc = df.loc[df["type"].str.lower()=="credit","amount"].sum()
    exp = df.loc[df["type"].str.lower()=="debit","amount"].sum()
    return f"Income={inc:.2f}, Expenses={exp:.2f}, Net={inc-exp:.2f}"

# parse numbers out of the summary
_summary_re = re.compile(
    r"Income\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*Expenses\s*=\s*([0-9]+(?:\.[0-9]+)?)\s*,\s*Net\s*=\s*([0-9]+(?:\.[0-9]+)?)",
    re.IGNORECASE
)
def parse_summary_numbers(summary: str):
    m = _summary_re.search(summary or "")
    if not m: return None, None, None
    return tuple(map(float, m.groups()))

def persist(route: str, summary: str, content: str, ip: str | None, key: str | None = None):
    inc, exp, nett = parse_summary_numbers(summary)
    key_hash = sha256((key or "").encode()).hexdigest() if key else None
    with Session(engine) as sess:
        sess.add(Report(
            route=route, summary=summary, content=content,
            income=inc, expenses=exp, net=nett,
            ip=ip, api_key_hash=key_hash
        ))
        sess.commit()

def call_llm(prompt: str) -> str:
    if LLM_PROVIDER == "offline":
        return f"(offline) would analyse: {prompt[:120]}..."

    if LLM_PROVIDER == "openai":
        try:
            from openai import OpenAI
            client = OpenAI(api_key=OPENAI_API_KEY)
            resp = client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "user", "content": prompt}],
                temperature=0.3,
            )
            return resp.choices[0].message.content.strip()
        except Exception as e:
            return f"(openai error: {str(e)[:200]})"

    if LLM_PROVIDER == "ollama":
        try:
            url = "http://127.0.0.1:11434/api/generate"
            payload = {"model": OLLAMA_MODEL, "prompt": prompt, "stream": False}
            r = requests.post(url, json=payload, timeout=(10, 180))
            try:
                r.raise_for_status()
            except requests.HTTPError:
                return f"(ollama error {r.status_code}: {r.text})"
            data = r.json()
            return (data.get("response") or "").strip() or "(empty response)"
        except Exception as e:
            return f"(ollama error: {str(e)[:200]})"

    return "(offline) provider not recognized"

# ---------------------- public routes ----------------------
@app.get("/health")
def health():
    return {"status":"ok","provider": LLM_PROVIDER, "model": OLLAMA_MODEL, "cwd": os.getcwd()}

# optional basic homepage if you made a static/index.html
@app.get("/", include_in_schema=False)
def homepage():
    index = os.path.join("static", "index.html")
    if os.path.exists(index):
        return FileResponse(index)
    return {"message": "Project Z API is running. See /health and /api/*."}

# ---------------------- secured API routes ----------------------
@app.post("/api/upload_csv")
def upload_csv(
    file: UploadFile = File(...),
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    try:
        contents = file.file.read()
        with open("transactions.csv", "wb") as f:
            f.write(contents)
        _ = summarise_transactions("transactions.csv")
        return {"ok": True, "message": "CSV uploaded and ready."}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        try: file.file.close()
        except: pass

@app.get("/api/analyze")
def api_analyze(
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    try:
        summary = summarise_transactions()
        prompt = (
            "You are Project Z, an expert AI business analyst for small businesses.\n"
            "Given the numeric summary below, produce:\n"
            "• 3 concise insights\n"
            "• 2 practical actions to improve profit/cashflow this week\n\n"
            f"SUMMARY: {summary}"
        )
        analysis = call_llm(prompt)
        persist("/api/analyze", summary, analysis, x_forwarded_for, x_api_key)
        return {"summary": summary, "analysis": analysis}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/suggest")
def api_suggest(
    q: str = Query(..., description="Your question"),
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    try:
        summary = summarise_transactions()
        prompt = (
            "You are Project Z, an AI strategist for a small business.\n"
            f"Context: {summary}\n\n"
            f"Question: {q}\n\n"
            "Provide 3 short, concrete, data-aware suggestions. Be specific."
        )
        answer = call_llm(prompt)
        persist("/api/suggest", summary, answer, x_forwarded_for, x_api_key)
        return {"summary": summary, "question": q, "answer": answer}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/report")
def api_report(
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    try:
        summary = summarise_transactions()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        prompt = (
            "Create a concise daily business report from this summary. "
            "Include: (1) one-line outlook, (2) 3 bullet insights, (3) 2 actions for cashflow.\n\n"
            f"SUMMARY: {summary}\nDATE: {today}"
        )
        report = call_llm(prompt)
        persist("/api/report", summary, report, x_forwarded_for, x_api_key)
        return {"date": today, "summary": summary, "report": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/history")
def api_history(
    limit: int = 20,
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    try:
        with Session(engine) as sess:
            rows = sess.exec(select(Report).order_by(Report.created_at.desc()).limit(limit)).all()
            return [
                {"created_at": r.created_at.isoformat(), "route": r.route,
                 "summary": r.summary, "content": r.content,
                 "income": r.income, "expenses": r.expenses, "net": r.net}
                for r in rows
            ]
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------- analytics: metrics & timeseries --------
@app.get("/api/metrics")
def api_metrics(
    days: int = 30,
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    since = datetime.utcnow() - timedelta(days=days)
    with Session(engine) as sess:
        count, avg_inc, avg_exp, avg_net, min_net, max_net = sess.exec(
            select(
                func.count(Report.id),
                func.avg(Report.income),
                func.avg(Report.expenses),
                func.avg(Report.net),
                func.min(Report.net),
                func.max(Report.net),
            ).where(Report.created_at >= since)
        ).one()
    return {
        "window_days": days,
        "entries": int(count or 0),
        "avg_income": round(avg_inc or 0.0, 2),
        "avg_expenses": round(avg_exp or 0.0, 2),
        "avg_net": round(avg_net or 0.0, 2),
        "best_net": round(max_net or 0.0, 2),
        "worst_net": round(min_net or 0.0, 2),
    }

@app.get("/api/timeseries")
def api_timeseries(
    days: int = 30,
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    since = datetime.utcnow() - timedelta(days=days)
    with Session(engine) as sess:
        rows = sess.exec(
            select(Report.created_at, Report.income, Report.expenses, Report.net)
            .where(Report.created_at >= since)
            .order_by(Report.created_at)
        ).all()
    points = [{
        "t": r[0].isoformat(timespec="seconds"),
        "income": round((r[1] or 0.0), 2),
        "expenses": round((r[2] or 0.0), 2),
        "net": round((r[3] or 0.0), 2),
    } for r in rows]
    return {"window_days": days, "points": points}

# -------- export: downloadable text report --------
@app.get("/api/report_file")
def api_report_file(
    x_api_key: str | None = Header(None),
    x_forwarded_for: str | None = Header(None)
):
    require_api_key(x_api_key, x_forwarded_for)
    try:
        summary = summarise_transactions()
        today = datetime.utcnow().strftime("%Y-%m-%d")
        prompt = (
            "Create a concise daily business report from this summary. "
            "Include: (1) one-line outlook, (2) 3 bullet insights, (3) 2 actions for cashflow.\n\n"
            f"SUMMARY: {summary}\nDATE: {today}"
        )
        report = call_llm(prompt)
        persist("/api/report_file", summary, report, x_forwarded_for, x_api_key)

        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        path = os.path.join("exports", f"report_{ts}.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"Project Z — Daily Report ({today})\n\n")
            f.write(f"Summary: {summary}\n\n")
            f.write(report.strip() + "\n")

        return FileResponse(path, media_type="text/plain", filename=os.path.basename(path))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# -------- temporary backfill (run once, then remove) --------
@app.post("/admin/backfill", include_in_schema=False)
def admin_backfill(x_api_key: str | None = Header(None)):
    if x_api_key != APP_API_KEY:
        raise HTTPException(status_code=401, detail="invalid api key")
    updated = 0
    with Session(engine) as sess:
        rows = sess.exec(select(Report)).all()
        for r in rows:
            if r.income is None or r.expenses is None or r.net is None:
                inc, exp, nett = parse_summary_numbers(r.summary)
                if inc is not None:
                    r.income, r.expenses, r.net = inc, exp, nett
                    updated += 1
        sess.commit()
    return {"ok": True, "updated": updated}
