export default function Navbar() {
  return (
    <nav style={{position:'fixed',insetInline:0,top:0,zIndex:50,padding:'16px 24px'}}>
      <div style={{
        background:'rgba(255,255,255,.06)', border:'1px solid rgba(255,255,255,.08)',
        backdropFilter:'blur(18px)', borderRadius:'16px', padding:'12px 16px',
        display:'flex',justifyContent:'space-between',alignItems:'center'
      }}>
        <span style={{color:'#e5e7eb',fontWeight:700,letterSpacing:'.3px'}}>LeapFound</span>
        <div style={{color:'#9ca3af',display:'flex',gap:'12px',fontSize:'14px'}}>
          <a href="#dashboard" style={{color:'inherit'}}>Dashboard</a>
          <a href="#about" style={{color:'inherit'}}>About</a>
          <a href="#contact" style={{color:'inherit'}}>Contact</a>
        </div>
      </div>
    </nav>
  );
}
