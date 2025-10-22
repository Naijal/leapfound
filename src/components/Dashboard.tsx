import { useEffect, useState } from "react";
import { motion } from "framer-motion";
import axios from "axios";

type Metrics = { income:number; expenses:number; net:number };
const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:8010";
const API_KEY  = localStorage.getItem("lf_api_key") || "";

export default function Dashboard() {
  const [metrics, setMetrics] = useState<Metrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [keyInput, setKeyInput] = useState(API_KEY);

  const headers = () => (keyInput ? { "X-API-Key": keyInput } : undefined);

  async function fetchMetrics() {
    setLoading(true);
    try {
      const r = await axios.get(`${API_BASE}/api/metrics?days=30`, { headers: headers() });
      setMetrics(r.data);
      localStorage.setItem("lf_api_key", keyInput);
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  async function loadSample() {
    setLoading(true);
    try {
      await axios.post(`${API_BASE}/api/load_sample`, {}, { headers: headers() });
      await fetchMetrics();
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { fetchMetrics(); }, []);

  return (
    <section id="dashboard" className="px-6 pb-24">
      <div className="max-w-6xl mx-auto">
        <div className="glass rounded-2xl p-5 shadow-soft mb-5 flex flex-col md:flex-row gap-3 md:items-center justify-between">
          <div className="text-text font-medium">Project Z — Control Panel</div>
          <div className="flex gap-3">
            <input
              value={keyInput}
              onChange={(e)=>setKeyInput(e.target.value)}
              placeholder="Enter X-API-Key"
              className="bg-white/5 border border-white/10 rounded-lg px-3 py-2 text-sm outline-none focus:border-accent"
            />
            <button onClick={fetchMetrics} className="rounded-lg px-4 py-2 text-sm bg-accent/20 hover:bg-accent/30 border border-accent/40">
              Connect
            </button>
            <button onClick={loadSample} className="rounded-lg px-4 py-2 text-sm bg-accent2/20 hover:bg-accent2/30 border border-accent2/40">
              Load sample
            </button>
          </div>
        </div>
      </div>
    </section>
  );
}
