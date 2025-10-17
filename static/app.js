async function getJSON(url) {
  const r = await fetch(url);
  if (!r.ok) throw new Error(`HTTP ${r.status}`);
  return r.json();
}

async function postFile(url, file) {
  const fd = new FormData();
  fd.append("file", file);
  const r = await fetch(url, { method: "POST", body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json();
}

function el(id){ return document.getElementById(id); }

async function refreshHealth() {
  try {
    const h = await getJSON("/health");
    el("provider").textContent = h.provider || "-";
    el("model").textContent = h.model || "-";
  } catch (e) {
    el("provider").textContent = "offline";
    el("model").textContent = "-";
  }
}

document.addEventListener("DOMContentLoaded", () => {
  refreshHealth();

  el("upload").addEventListener("click", async () => {
    const f = el("file").files[0];
    if (!f) { el("uploadStatus").textContent = "Choose a .csv file first."; return; }
    el("uploadStatus").textContent = "Uploading...";
    try {
      const res = await postFile("/upload_csv", f);
      el("uploadStatus").textContent = res.message || "Uploaded.";
    } catch (e) {
      el("uploadStatus").textContent = `Upload failed: ${e.message}`;
    }
  });

  el("analyze").addEventListener("click", async () => {
    el("analysis").textContent = "Thinking...";
    try {
      const data = await getJSON("/");
      el("analysis").textContent = `Summary: ${data.summary}\n\nAnalysis:\n${data.analysis}`;
    } catch (e) {
      el("analysis").textContent = `Error: ${e.message}`;
    }
  });

  el("ask").addEventListener("click", async () => {
    const q = el("q").value.trim();
    if (!q) { el("answer").textContent = "Type a question first."; return; }
    el("answer").textContent = "Thinking...";
    try {
      const data = await getJSON(`/suggest?q=${encodeURIComponent(q)}`);
      el("answer").textContent = data.answer || "(no answer)";
    } catch (e) {
      el("answer").textContent = `Error: ${e.message}`;
    }
  });

  el("report").addEventListener("click", async () => {
    el("reportOut").textContent = "Compiling report...";
    try {
      const data = await getJSON("/report");
      el("reportOut").textContent = data.report || "(no report)";
    } catch (e) {
      el("reportOut").textContent = `Error: ${e.message}`;
    }
  });
});
