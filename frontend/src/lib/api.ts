const base = import.meta.env.VITE_API_BASE?.replace(/\/$/, "") || window.location.origin;

export async function get<T>(path: string, key?: string): Promise<T> {
  const r = await fetch(`${base}${path}`, { headers: key ? { "X-API-Key": key } : {} });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}

export async function postFile<T>(path: string, file: File, key?: string): Promise<T> {
  const fd = new FormData(); fd.append("file", file);
  const r = await fetch(`${base}${path}`, { method: "POST", headers: key ? { "X-API-Key": key } : {}, body: fd });
  if (!r.ok) throw new Error(await r.text());
  return r.json() as Promise<T>;
}
