# main.py — Project Z: secure, single-file backend
# Python 3.9+ compatible

import os, io, csv, json, time, math, base64, hashlib, logging, asyncio
from datetime import datetime, timedelta
from typing import Optional, List, Dict, Any, Set, Tuple

from fastapi import FastAPI, Depends, HTTPException, Request, UploadFile, File, Response, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, PlainTextResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from pydantic import BaseModel
from sqlmodel import SQLModel, Field, Session, create_engine, select
from starlette.middleware.base import BaseHTTPMiddleware
from dotenv import load_dotenv

# ---------- Optional deps ----------
try:
    import requests
except Exception:
    requests = None

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import A4
    REPORTLAB_OK = True
except Exception:
    REPORTLAB_OK = False

try:
    from cryptography.fernet import Fernet, InvalidToken  # type: ignore
    CRYPTO_OK = True
except Exception:
    Fernet = None  # type: ignore
    InvalidToken = Exception  # type: ignore
    CRYPTO_OK = False
# -----------------------------------

load_dotenv()

APP_NAME = os.getenv("APP_NAME", "Project Z")
APP_ENV = os.getenv("APP_ENV", "dev")
DATA_DIR = os.getenv("DATA_DIR", ".")
DB_PATH = os.getenv("DB_PATH", os.path.join(DATA_DIR, "projectz.db"))
EXPORT_DIR = os.path.join(DATA_DIR, "exports")
LOG_DIR = os.path.join(DATA_DIR, "logs")
os.makedirs(EXPORT_DIR, exist_ok=True)
os.makedirs(LOG_DIR, exist_ok=True)

# Ollama / AI
OLLAMA_BASE = os.getenv("OLLAMA_BASE", "http://127.0.0.1:11434")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "llama3.1:8b-instruct")
OLLAMA_TIMEOUT = int(os.getenv("OLLAMA_TIMEOUT", "30"))

# CORS
def _load_cors() -> List[str]:
    raw = os.getenv(
        "CORS_ALLOW_ORIGINS",
        "http://127.0.0.1:5173,http://localhost:5173,http://127.0.0.1:8010"
    )
    return [o.strip() for o in raw.split(",") if o.strip()]

CORS_ALLOW_ORIGINS = _load_cors()

# Rate limiting
RATE_WINDOW_SEC = int(os.getenv("RATE_WINDOW_SEC", "60"))
RATE_MAX_CALLS = int(os.getenv("RATE_MAX_CALLS", "120"))

# ---------- API keys & roles ----------
# Options:
# 1) API_KEY=abc              -> single key, user role
# 2) API_KEYS=abc,def         -> multiple keys, user role
# 3) API_KEYS_JSON=[{"key":"abc","role":"admin","name":"Founder"}, ...]
#    roles: admin/user/viewer
def _load_keys() -> Dict[str, Dict[str, str]]:
    out: Dict[str, Dict[str, str]] = {}
    try:
        j = os.getenv("API_KEYS_JSON", "").strip()
        if j:
            arr = json.loads(j)
            for item in arr:
                k = (item.get("key") or "").strip()
                if not k:
                    continue
                out[k] = {
                    "role": (item.get("role") or "user").lower(),
                    "name": item.get("name") or "client",
                }
    except Exception:
        pass
    single = os.getenv("API_KEY", "").strip()
    if single and single not in out:
        out[single] = {"role": "user", "name": "client"}
    mult = os.getenv("API_KEYS", "")
    if mult:
        for k in [x.strip() for x in mult.split(",") if x.strip()]:
            if k not in out:
                out[k] = {"role": "user", "name": "client"}
    return out

ALLOWED: Dict[str, Dict[str, str]] = _load_keys()

def client_by_key(k: Optional[str]) -> Optional[Dict[str, str]]:
    if not k: return None
    k = k.strip()
    meta = ALLOWED.get(k)
    if not meta: return None
    return {"key": k, "role": meta.get("role", "user"), "name": meta.get("name", "client"), "key_last4": k[-4:]}

def require_key(request: Request) -> Dict[str, str]:
    supplied = request.headers.get("X-API-Key", "").strip()
    client = client_by_key(supplied)
    if not client:
        raise HTTPException(401, "invalid api key")
    return client

def require_admin(client=Depends(require_key)) -> Dict[str, str]:
    if client["role"] != "admin":
        raise HTTPException(403, "admin required")
    return client

# ---------- Logging (rotating) ----------
from logging.handlers import RotatingFileHandler
LOG_PATH = os.path.join(LOG_DIR, "app.log")
handler = RotatingFileHandler(LOG_PATH, maxBytes=2_000_000, backupCount=3, encoding="utf-8")
logging.basicConfig(level=logging.INFO, handlers=[handler], format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(APP_NAME)

# ---------- Encryption ----------
FERNET: Optional[object] = None
ENC_KEY = os.getenv("ENCRYPTION_KEY", "").strip()
if CRYPTO_OK and ENC_KEY:
    try:
        # accept raw 32-byte base64 or urlsafe base64 Fernet key
        key = ENC_KEY
        if len(ENC_KEY) != 44:  # not a typical Fernet b64
            # derive from passphrase -> NOT strong KDF (for demo); replace with proper KDF in prod
            key = base64.urlsafe_b64encode(hashlib.sha256(ENC_KEY.encode()).digest())
        FERNET = Fernet(key)
    except Exception:
        FERNET = None

def enc(s: Optional[str]) -> Optional[str]:
    if not s: return s
    if FERNET is None: return s
    return FERNET.encrypt(s.encode()).decode()

def dec(s: Optional[str]) -> Optional[str]:
    if not s: return s
    if FERNET is None: return s
    try:
        return FERNET.decrypt(s.encode()).decode()
    except Exception:
        return s

# ---------- Database ----------
class Txn(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(index=True)
    kind: str = Field(index=True)  # income|expense
    amount: float
    category_enc: Optional[str] = Field(default=None)  # encrypted
    memo_enc: Optional[str] = Field(default=None)      # encrypted

    @property
    def category(self): return dec(self.category_enc)
    @property
    def memo(self): return dec(self.memo_enc)

class Report(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    ts: datetime = Field(index=True)
    route: str = Field(index=True)
    summary: Optional[str] = None
    content_enc: Optional[str] = None
    ip: Optional[str] = None
    key_last4: Optional[str] = None
    income: Optional[float] = None
    expenses: Optional[float] = None
    net: Optional[float] = None

    @property
    def content(self): return dec(self.content_enc)

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False, connect_args={"check_same_thread": False})
SQLModel.metadata.create_all(engine)

def db() -> Session: return Session(engine)

# ---------- App & Static ----------
app = FastAPI(title=APP_NAME, version="1.0.0")

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

@app.get("/", include_in_schema=False)
def root():
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.isfile(index_path): return FileResponse(index_path)
    return PlainTextResponse("Frontend not built. Visit /health.", 200)

# ---------- CORS & Security headers ----------
app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ALLOW_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        resp: Response = await call_next(request)
        resp.headers["X-Content-Type-Options"] = "nosniff"
        resp.headers["X-Frame-Options"] = "DENY"
        resp.headers["Referrer-Policy"] = "no-referrer"
        resp.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        resp.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
        return resp

app.add_middleware(SecurityHeaders)

# ---------- Rate limiting & Audit ----------
_BUCKET: Dict[str, Tuple[int,int]] = {}
def _rtoken(ip: str, k: str) -> str: return hashlib.sha1(f"{ip}:{k}".encode()).hexdigest()

class RateLimitAndAudit(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path.startswith("/static") or path in ("/health", "/"):  # skip
            return await call_next(request)

        ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or request.client.host or "?"
        key = (request.headers.get("X-API-Key") or "").strip()
        kl4 = key[-4:] if key else "none"

        # rate-limit
        now = int(time.time())
        tok = _rtoken(ip, kl4)
        start, count = _BUCKET.get(tok, (now, 0))
        if now - start >= RATE_WINDOW_SEC:
            _BUCKET[tok] = (now, 1)
        else:
            if count + 1 > RATE_MAX_CALLS:
                logger.warning("429 %s key:%s path:%s", ip, kl4, path)
                return JSONResponse({"detail":"rate limit exceeded"}, status_code=429)
            _BUCKET[tok] = (start, count+1)

        # proceed
        resp = await call_next(request)

        # audit log
        logger.info("%s %s %s %s %s", request.method, path, resp.status_code, ip, kl4)
        return resp

app.add_middleware(RateLimitAndAudit)

# ---------- Health ----------
@app.get("/health")
def health():
    return {
        "status": "ok",
        "env": APP_ENV,
        "db": os.path.abspath(DB_PATH),
        "ollama_model": OLLAMA_MODEL,
        "pdf": REPORTLAB_OK,
        "enc": bool(FERNET),
    }

# ---------- CSV Upload ----------
@app.post("/api/upload_csv")
def upload_csv(file: UploadFile = File(...), client=Depends(require_key), request: Request=None):
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or request.client.host
    raw = file.file.read().decode("utf-8", "ignore")
    reader = csv.DictReader(io.StringIO(raw))
    rows = 0
    with db() as s:
        for row in reader:
            try:
                ts_raw = (row.get("ts") or row.get("date") or "").strip()
                kind = (row.get("kind") or row.get("type") or "").strip().lower()
                amount = float(row.get("amount", "0").strip())
                cat = (row.get("category") or "").strip() or None
                memo = (row.get("memo") or row.get("description") or "").strip() or None

                try:
                    ts = datetime.fromisoformat(ts_raw.replace("Z","+00:00"))
                except Exception:
                    ts = datetime.strptime(ts_raw, "%Y-%m-%d")

                if kind not in ("income","expense"):
                    kind = "income" if amount >= 0 else "expense"
                    amount = abs(amount)

                s.add(Txn(ts=ts, kind=kind, amount=amount, category_enc=enc(cat), memo_enc=enc(memo)))
                rows += 1
            except Exception:
                continue
        s.commit()
    return {"message": f"ingested {rows} rows", "ip": ip, "key_last4": client["key_last4"]}

# ---------- Metrics / Series / History ----------
class MetricsOut(BaseModel):
    avg_income: float; avg_expenses: float; avg_net: float; count: int

class TSPoint(BaseModel):
    t: str; income: Optional[float]; expenses: Optional[float]; net: Optional[float]

class TimeSeriesOut(BaseModel):
    points: List[TSPoint]

def _sum_all(s: Session, since: Optional[datetime]=None) -> Tuple[float,float,float]:
    stmt = select(Txn)
    if since: stmt = stmt.where(Txn.ts >= since)
    txns = s.exec(stmt).all()
    inc = sum(t.amount for t in txns if t.kind=="income")
    exp = sum(t.amount for t in txns if t.kind=="expense")
    return inc, exp, inc-exp

@app.get("/api/metrics", response_model=MetricsOut)
def metrics(days: int = Query(30, ge=1, le=365), client=Depends(require_key)):
    since = datetime.utcnow() - timedelta(days=days)
    with db() as s:
        per: Dict[str, Dict[str,float]] = {}
        for t in s.exec(select(Txn).where(Txn.ts >= since)).all():
            d = t.ts.strftime("%Y-%m-%d")
            per.setdefault(d, {"inc":0.0,"exp":0.0})
            if t.kind=="income": per[d]["inc"] += t.amount
            else: per[d]["exp"] += t.amount
        if not per: return MetricsOut(avg_income=0,avg_expenses=0,avg_net=0,count=0)
        vals = list(per.values())
        ai = sum(v["inc"] for v in vals)/len(vals)
        ae = sum(v["exp"] for v in vals)/len(vals)
        return MetricsOut(avg_income=round(ai,2), avg_expenses=round(ae,2), avg_net=round(ai-ae,2), count=len(vals))

@app.get("/api/timeseries", response_model=TimeSeriesOut)
def series(days: int = Query(30, ge=1, le=730), client=Depends(require_key)):
    since = datetime.utcnow() - timedelta(days=days)
    with db() as s:
        per: Dict[str, Dict[str,float]] = {}
        for t in s.exec(select(Txn).where(Txn.ts >= since)).all():
            d = t.ts.strftime("%Y-%m-%d")
            per.setdefault(d, {"inc":0.0,"exp":0.0})
            if t.kind=="income": per[d]["inc"] += t.amount
            else: per[d]["exp"] += t.amount
        points: List[TSPoint] = []
        for k in sorted(per.keys()):
            inc = per[k]["inc"]; exp = per[k]["exp"]; net = inc-exp
            points.append(TSPoint(t=k, income=round(inc,2), expenses=round(exp,2), net=round(net,2)))
        return TimeSeriesOut(points=points)

@app.get("/api/history")
def history(limit: int = Query(10, ge=1, le=100), client=Depends(require_key)):
    with db() as s:
        rows = s.exec(select(Report).order_by(Report.ts.desc()).limit(limit)).all()
        return [{
            "ts": r.ts.isoformat(), "route": r.route, "summary": r.summary,
            "content": r.content, "income": r.income, "expenses": r.expenses, "net": r.net,
            "key_last4": r.key_last4
        } for r in rows]

# ---------- Ollama ----------
def ollama_ok() -> bool:
    if requests is None: return False
    try:
        r = requests.get(f"{OLLAMA_BASE}/api/tags", timeout=5)
        return r.status_code == 200
    except Exception:
        return False

def ask_ollama(prompt: str) -> Optional[str]:
    if requests is None: return None
    try:
        # chat
        r = requests.post(f"{OLLAMA_BASE}/api/chat",
                          json={"model": OLLAMA_MODEL, "messages":[{"role":"user","content":prompt}]},
                          timeout=OLLAMA_TIMEOUT)
        if r.status_code == 200:
            j = r.json()
            msg = (j.get("message") or {}).get("content")
            if msg: return msg
        # fallback generate
        r = requests.post(f"{OLLAMA_BASE}/api/generate",
                          json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
                          timeout=OLLAMA_TIMEOUT)
        if r.status_code == 200:
            j = r.json(); return j.get("response")
    except Exception:
        return None
    return None

# ---------- Analyze / Suggest (sync) ----------
@app.get("/api/analyze")
def analyze(request: Request, client=Depends(require_key)):
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or request.client.host
    with db() as s:
        inc, exp, net = _sum_all(s)
        prompt = (f"You are Project Z, UK SME AI ops analyst.\n"
                  f"Totals: Income={inc:.2f}, Expenses={exp:.2f}, Net={net:.2f}.\n"
                  f"Give 5 concise high-impact actions for the next 7 days to improve net profit, "
                  f"covering compliance (VAT/PAYE), cashflow timing, and low-risk experiments.")
        ans = ask_ollama(prompt) or f"(offline) Income={inc:.2f}, Expenses={exp:.2f}, Net={net:.2f}"
        r = Report(ts=datetime.utcnow(), route="/api/analyze",
                   summary=f"Income={inc:.2f}, Expenses={exp:.2f}, Net={net:.2f}",
                   content_enc=enc(ans), ip=ip, key_last4=client["key_last4"],
                   income=inc, expenses=exp, net=net)
        s.add(r); s.commit(); s.refresh(r)
        return {"summary": r.summary, "analysis": ans, "ts": r.ts.isoformat()}

@app.get("/api/suggest")
def suggest(q: str = Query(..., min_length=3, max_length=400),
            request: Request = None, client=Depends(require_key)):
    ip = (request.headers.get("x-forwarded-for") or "").split(",")[0].strip() or request.client.host
    with db() as s:
        inc, exp, net = _sum_all(s)
        prompt = f"Context: Income={inc:.2f}, Expenses={exp:.2f}, Net={net:.2f}.\nQuestion: {q}\nAnswer for a UK small business, step-by-step, concise."
        ans = ask_ollama(prompt) or "(offline) No LLM available."
        r = Report(ts=datetime.utcnow(), route="/api/suggest",
                   summary=f"Q: {q}", content_enc=enc(ans), ip=ip, key_last4=client["key_last4"],
                   income=inc, expenses=exp, net=net)
        s.add(r); s.commit()
        return {"answer": ans}

# ---------- Jobs (async) ----------
JOB_Q: "asyncio.Queue[Dict[str, Any]]" = asyncio.Queue()
JOB_RESULTS: Dict[str, Dict[str, Any]] = {}

async def worker():
    while True:
        job = await JOB_Q.get()
        jid = job["id"]; kind = job["kind"]; created = datetime.utcnow().isoformat()
        try:
            if kind == "analyze":
                with db() as s:
                    inc, exp, net = _sum_all(s)
                prompt = f"Totals: Income={inc:.2f}, Expenses={exp:.2f}, Net={net:.2f}. Give 5 actions."
                ans = ask_ollama(prompt) or "(offline) analysis"
                JOB_RESULTS[jid] = {"status":"done","created":created,"result":{"summary":f"I={inc:.2f} E={exp:.2f} N={net:.2f}","analysis":ans}}
            else:
                JOB_RESULTS[jid] = {"status":"error","error":"unknown job"}
        except Exception as e:
            JOB_RESULTS[jid] = {"status":"error","error":str(e)}
        finally:
            JOB_Q.task_done()

@app.on_event("startup")
async def startup():
    asyncio.create_task(worker())

@app.post("/api/jobs/analyze")
async def job_analyze(client=Depends(require_key)):
    jid = hashlib.sha1(f"{time.time()}:{client['key_last4']}".encode()).hexdigest()[:16]
    await JOB_Q.put({"id":jid, "kind":"analyze"})
    return {"job_id": jid, "status":"queued"}

@app.get("/api/jobs/{job_id}")
def job_status(job_id: str, client=Depends(require_key)):
    return JOB_RESULTS.get(job_id, {"status":"unknown"})

# ---------- Reports ----------
@app.get("/api/report")
def report(client=Depends(require_key)):
    with db() as s:
        inc, exp, net = _sum_all(s)
        return {"title": f"{APP_NAME} Report", "period":"all time",
                "income": round(inc,2), "expenses": round(exp,2), "net": round(net,2)}

@app.get("/api/report_file")
def report_file(client=Depends(require_key)):
    with db() as s:
        inc, exp, net = _sum_all(s)
    txt = f"""{APP_NAME} — Report
Generated: {datetime.utcnow().isoformat()}Z

Totals:
  Income:   {inc:.2f}
  Expenses: {exp:.2f}
  Net:      {net:.2f}
"""
    fn = os.path.join(EXPORT_DIR, f"report_{int(time.time())}.txt")
    with open(fn, "w", encoding="utf-8") as f:
        f.write(txt)
    return FileResponse(fn, media_type="text/plain", filename=os.path.basename(fn))

@app.get("/api/report_pdf")
def report_pdf(client=Depends(require_key)):
    if not REPORTLAB_OK:
        return JSONResponse({"detail":"PDF not available (pip install reportlab)"}, status_code=501)
    with db() as s:
        inc, exp, net = _sum_all(s)
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    w, h = A4; y = h - 72
    c.setFont("Helvetica-Bold", 18); c.drawString(72, y, f"{APP_NAME} — Report")
    y -= 28; c.setFont("Helvetica", 11); c.drawString(72, y, f"Generated: {datetime.utcnow().isoformat()}Z")
    y -= 24
    for k,v in [("Income",inc),("Expenses",exp),("Net",net)]:
        c.drawString(72, y, f"{k}: {v:.2f}"); y -= 18
    c.showPage(); c.save(); buf.seek(0)
    return StreamingResponse(buf, media_type="application/pdf",
                             headers={"Content-Disposition": 'attachment; filename="report.pdf"'} )

# ---------- Admin ----------
@app.get("/api/admin/allowed", dependencies=[Depends(require_admin)])
def admin_allowed():
    return [{"name":v.get("name"), "role":v.get("role"), "key_last4":k[-4:]} for k,v in ALLOWED.items()]

@app.get("/api/admin/usage", dependencies=[Depends(require_admin)])
def admin_usage():
    with db() as s:
        tx_count = s.exec(select(Txn)).count()
        rp_count = s.exec(select(Report)).count()
    return {"transactions": tx_count, "reports": rp_count}

@app.get("/api/admin/audit_tail", dependencies=[Depends(require_admin)])
def admin_audit_tail(lines: int = Query(100, ge=10, le=1000)):
    try:
        with open(LOG_PATH, "r", encoding="utf-8", errors="ignore") as f:
            data = f.readlines()[-lines:]
        return {"lines": data}
    except Exception as e:
        return JSONResponse({"detail": str(e)}, status_code=500)

# ---------- Global error ----------
@app.exception_handler(Exception)
async def on_error(request: Request, exc: Exception):
    logger.exception("Unhandled: %s", exc)
    return JSONResponse({"detail":"internal error"}, status_code=500)
