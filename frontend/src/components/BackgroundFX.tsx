export default function BackgroundFX() {
  return (
    <>
      <style>{`
        .blob { position:absolute; width:60vmax; height:60vmax; border-radius:50%; opacity:.35; mix-blend-mode:screen; will-change:transform; filter:blur(40px) }
        .blob-a { left:-10vmax; top:-10vmax; background:radial-gradient(circle at 30% 30%, rgba(99,102,241,.9), rgba(99,102,241,0) 60%); animation:floatA 14s ease-in-out infinite; }
        .blob-b { right:-15vmax; top:-5vmax; background:radial-gradient(circle at 60% 40%, rgba(56,189,248,.9), rgba(56,189,248,0) 60%); animation:floatB 18s ease-in-out infinite; }
        .blob-c { left:10vmax; bottom:-15vmax; background:radial-gradient(circle at 40% 60%, rgba(34,197,94,.9), rgba(34,197,94,0) 60%); animation:floatC 20s ease-in-out infinite; }
        @keyframes floatA { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(6vmax,3vmax) scale(1.06)} }
        @keyframes floatB { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(-5vmax,4vmax) scale(1.05)} }
        @keyframes floatC { 0%,100%{transform:translate(0,0) scale(1)} 50%{transform:translate(4vmax,-6vmax) scale(1.08)} }
      `}</style>

      {/* Put blobs ABOVE the body background but BELOW content */}
      <div
        aria-hidden
        style={{
          position: 'fixed',
          inset: 0,
          zIndex: 0,            // <-- was -1; now visible
          overflow: 'hidden',
          pointerEvents: 'none'
        }}
      >
        <div className="blob blob-a" />
        <div className="blob blob-b" />
        <div className="blob blob-c" />
      </div>
    </>
  );
}
