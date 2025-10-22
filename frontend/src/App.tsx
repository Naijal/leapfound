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
