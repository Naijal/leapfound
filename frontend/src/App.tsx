<<<<<<< HEAD
export default function App() {
  return (
    <div className="min-h-screen bg-[#0b1220] text-white">
      <header className="sticky top-0 z-10 backdrop-blur border-b border-white/10 bg-black/20">
        <div className="mx-auto max-w-6xl px-6 py-4 flex items-center justify-between">
          <div className="text-xl font-semibold tracking-wide">Leapfound</div>
          <nav className="flex gap-6 text-sm text-white/80">
            <a className="hover:text-white" href="#dash">Dashboard</a>
            <a className="hover:text-white" href="#analyze">Analyze</a>
            <a className="hover:text-white" href="#about">About</a>
          </nav>
        </div>
      </header>

      <main className="mx-auto max-w-6xl px-6 py-12">
        <section className="mb-12">
          <h1 className="text-4xl md:text-5xl font-bold tracking-tight">
            Founders’ Copilot, built for the UK.
          </h1>
          <p className="mt-4 text-white/70 max-w-2xl">
            Secure, fast, and beautiful by default. This is the live app shell.
            If you can read this, the frontend is mounted correctly.
          </p>
        </section>

        <section id="dash" className="grid md:grid-cols-3 gap-6">
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
            <div className="text-sm text-white/60">Status</div>
            <div className="mt-2 text-2xl font-semibold">Online</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
            <div className="text-sm text-white/60">API</div>
            <div className="mt-2 text-2xl font-semibold">/health ✓</div>
          </div>
          <div className="rounded-2xl border border-white/10 bg-white/5 p-6">
            <div className="text-sm text-white/60">Region</div>
            <div className="mt-2 text-2xl font-semibold">LHR</div>
          </div>
        </section>
      </main>

      <footer className="mt-16 border-t border-white/10 py-10 text-center text-white/50">
        © Leapfound
      </footer>
    </div>
  );
}
=======
import { useEffect, useMemo, useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";
import { Line } from "react-chartjs-2";
import {
  Chart as ChartJS, LineElement, PointElement, LinearScale, TimeSeriesScale, CategoryScale, Tooltip, Legend,
} from "chart.js";

ChartJS.register(LineElement, PointElement, LinearScale, TimeSeriesScale, CategoryScale, Tooltip, Legend);

type TSResp = { points: { t: string; income?: number; expenses?: number; net?: number }[] };
type MetricsResp = { avg_income: number; avg_expenses: number; avg_net: number; count: number };

const BASE = "http://127.0.0.1:8010";

export default function App() {
  const [apiKey, setApiKey] = useState(localStorage.getItem("apiKey") || "");
  const [busy, setBusy] = useState(false);
  const [analysis, setAnalysis] = useState<string>("");
  const [metrics, setMetrics] = useState<MetricsResp | null>(null);
  const [series, setSeries] = useState<TSResp["points"]>([]);
  const [q, setQ] = useState("how can we grow profit next week?");
  const [answer, setAnswer] = useState("");

  // lead capture modal
  const [showPilot, setShowPilot] = useState(false);
  const [pilotEmail, setPilotEmail] = useState("");

  const headers = useMemo(() => (apiKey ? { "X-API-Key": apiKey } : {}), [apiKey]);

  useEffect(() => {
    // load metrics + timeseries on mount (if key saved)
    if (!apiKey) return;
    fetchMetrics();
    fetchSeries();
  }, [apiKey]);

  async function fetchMetrics() {
    try {
      const r = await axios.get<MetricsResp>(`${BASE}/api/metrics?days=30`, { headers });
      setMetrics(r.data);
    } catch (e: any) {
      console.error(e);
    }
  }
  async function fetchSeries() {
    try {
      const r = await axios.get<TSResp>(`${BASE}/api/timeseries?days=30`, { headers });
      setSeries(r.data.points || []);
    } catch (e: any) {
      console.error(e);
    }
  }

  async function runAnalyze() {
    if (!apiKey) return alert("Add API key first.");
    setBusy(true);
    setAnalysis("");
    try {
      const r = await axios.get(`${BASE}/api/analyze`, { headers });
      setAnalysis(JSON.stringify(r.data, null, 2));
      fetchMetrics();
      fetchSeries();
    } catch (e: any) {
      setAnalysis("❌ " + (e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  }

  async function runSuggest() {
    if (!apiKey) return alert("Add API key first.");
    setBusy(true);
    setAnswer("");
    try {
      const r = await axios.get(`${BASE}/api/suggest`, { headers, params: { q } });
      setAnswer(r.data.answer || "");
    } catch (e: any) {
      setAnswer("❌ " + (e.response?.data?.detail || e.message));
    } finally {
      setBusy(false);
    }
  }

  async function uploadCSV(e: React.ChangeEvent<HTMLInputElement>) {
    if (!e.target.files?.length) return;
    if (!apiKey) return alert("Add API key first.");
    const f = e.target.files[0];
    const form = new FormData();
    form.append("file", f);
    setBusy(true);
    try {
      await axios.post(`${BASE}/api/upload_csv`, form, { headers });
      await fetchMetrics();
      await fetchSeries();
      await runAnalyze();
    } catch (err: any) {
      alert("Upload failed: " + (err.response?.data?.detail || err.message));
    } finally {
      setBusy(false);
      e.target.value = "";
    }
  }

  const chartData = useMemo(() => {
    const labels = series.map(p => p.t);
    return {
      labels,
      datasets: [
        { label: "Income", data: series.map(p => p.income ?? 0), borderWidth: 2, tension: 0.35 },
        { label: "Expenses", data: series.map(p => p.expenses ?? 0), borderWidth: 2, tension: 0.35 },
        { label: "Net", data: series.map(p => p.net ?? 0), borderWidth: 2, tension: 0.35 },
      ],
    };
  }, [series]);

  function saveKey() {
    localStorage.setItem("apiKey", apiKey.trim());
    alert("✅ API key saved");
  }

  function clearKey() {
    localStorage.removeItem("apiKey");
    setApiKey("");
  }

  return (
    <div className="min-h-screen text-text bg-bg">
      {/* header */}
      <div className="max-w-6xl mx-auto px-4 pt-8 pb-4">
        <div className="flex items-center justify-between">
          <motion.h1 initial={{opacity:0,y:10}} animate={{opacity:1,y:0}} transition={{duration:.6}} className="text-2xl font-semibold">
            <span className="opacity-90">Project</span>{" "}
            <span className="text-white">Z</span>
          </motion.h1>
          <div className="flex gap-2">
            <input
              value={apiKey}
              onChange={(e)=>setApiKey(e.target.value)}
              placeholder="X-API-Key"
              className="input w-64"
            />
            <button onClick={saveKey} className="btn-ghost">Save</button>
            <button onClick={clearKey} className="btn-ghost">Clear</button>
            <button onClick={()=>setShowPilot(true)} className="btn-primary">Join Pilot</button>
          </div>
        </div>
      </div>

      {/* hero card */}
      <motion.div
        className="max-w-6xl mx-auto px-4 grid md:grid-cols-3 gap-4"
        initial={{opacity:0, y:20}} animate={{opacity:1, y:0}} transition={{duration:.5}}
      >
        <div className="card p-6 md:col-span-2">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-medium">Weekly Performance</h2>
            <div className="flex gap-2">
              <label className="btn-ghost cursor-pointer">
                <input type="file" className="hidden" accept=".csv" onChange={uploadCSV} />
                Upload CSV
              </label>
              <button disabled={busy} onClick={runAnalyze} className="btn-primary">{busy ? "Working…" : "Analyze Now"}</button>
            </div>
          </div>

          <div className="relative">
            <Line
              data={chartData}
              options={{
                responsive: true,
                plugins: { legend: { display: true } },
                scales: { x: { grid: { display: false } }, y: { grid: { color: "rgba(255,255,255,.07)" } } },
              }}
            />
            {/* ambient glow */}
            <motion.div
              className="absolute -inset-6 rounded-2xl pointer-events-none"
              initial={{ opacity: 0 }} animate={{ opacity: 1 }}
              style={{ boxShadow: "0 0 120px rgba(79,70,229,.25)" }}
            />
          </div>
        </div>

        <div className="card p-6 space-y-4">
          <h2 className="text-lg font-medium">KPIs (rolling 30 days)</h2>
          <div className="grid grid-cols-3 gap-3">
            <Kpi title="Avg Income" value={money(metrics?.avg_income)} />
            <Kpi title="Avg Expenses" value={money(metrics?.avg_expenses)} />
            <Kpi title="Avg Net" value={money(metrics?.avg_net)} />
          </div>

          <div className="h-px bg-line/70 my-2" />

          <div className="space-y-2">
            <label className="text-sm text-muted">Ask Project Z</label>
            <input className="input" value={q} onChange={(e)=>setQ(e.target.value)} />
            <button disabled={busy} onClick={runSuggest} className="btn-primary w-full">
              {busy ? "Thinking…" : "Get Suggestion"}
            </button>
          </div>

          <motion.div initial={{opacity:0}} animate={{opacity:1}} className="text-sm border border-line rounded-xl p-3 bg-card/70 max-h-48 overflow-auto">
            {answer ? answer : <span className="text-muted">AI suggestions appear here…</span>}
          </motion.div>
        </div>
      </motion.div>

      {/* analysis panel */}
      <motion.div
        className="max-w-6xl mx-auto px-4 mt-4"
        initial={{opacity:0, y:10}} animate={{opacity:1, y:0}} transition={{duration:.5, delay:.1}}
      >
        <div className="card p-6">
          <div className="flex items-center justify-between mb-2">
            <h2 className="text-lg font-medium">Latest Analysis</h2>
            <a
              href={`${BASE}/api/report_pdf`}
              onClick={(e)=>{ if(!apiKey){ e.preventDefault(); alert("Add API key first."); } }}
              className="btn-ghost"
            >
              Download PDF
            </a>
          </div>
          <pre className="text-sm max-h-64 overflow-auto">{analysis || "Run Analyze to generate insights…"}</pre>
        </div>
      </motion.div>

      {/* pilot modal */}
      {showPilot && (
        <motion.div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50"
          initial={{opacity:0}} animate={{opacity:1}}>
          <motion.div className="card p-6 w-[90%] max-w-md"
            initial={{scale:.9, opacity:0}} animate={{scale:1, opacity:1}}>
            <h3 className="text-xl font-semibold mb-2">Join the Private Pilot</h3>
            <p className="text-sm text-muted mb-4">
              Get early access, concierge onboarding, and priority features for UK businesses.
            </p>
            <input
              placeholder="work email"
              className="input mb-3"
              value={pilotEmail}
              onChange={(e)=>setPilotEmail(e.target.value)}
            />
            <div className="flex gap-2">
              <button
                className="btn-primary flex-1"
                onClick={()=>{
                  if(!pilotEmail.includes("@")) return alert("Enter a valid email");
                  localStorage.setItem("pilotEmail", pilotEmail.trim());
                  setShowPilot(false);
                  alert("✅ Registered. We’ll be in touch.");
                }}
              >
                Request Invite
              </button>
              <button className="btn-ghost" onClick={()=>setShowPilot(false)}>Close</button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </div>
  );
}

function Kpi({ title, value }: { title: string; value: string }) {
  return (
    <motion.div className="rounded-xl border border-line p-3 bg-card/70"
      initial={{opacity:0, y:8}} animate={{opacity:1, y:0}}>
      <div className="text-xs text-muted">{title}</div>
      <div className="text-lg font-semibold mt-1">{value}</div>
    </motion.div>
  );
}

function money(n?: number) {
  if (typeof n !== "number" || isNaN(n)) return "–";
  return "£" + n.toFixed(2);
}
>>>>>>> b24514b (Initial Leapfound (backend FastAPI + frontend Vite))
