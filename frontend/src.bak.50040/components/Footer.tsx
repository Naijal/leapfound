export default function Footer() {
  return (
    <footer id="about" className="px-6 pb-10">
      <div className="max-w-6xl mx-auto glass rounded-2xl p-6 text-sm text-muted text-center">
        © {new Date().getFullYear()} LeapFound — AI for founders. Built with love.
      </div>
    </footer>
  );
}
