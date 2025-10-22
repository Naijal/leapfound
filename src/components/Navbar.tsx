import { motion } from "framer-motion";

export default function Navbar() {
  return (
    <nav className="fixed top-0 inset-x-0 z-50 px-6 py-4">
      <div className="glass rounded-2xl shadow-soft px-5 py-3 flex items-center justify-between">
        <motion.div initial={{opacity:0,y:-6}} animate={{opacity:1,y:0}} transition={{duration:.6}}>
          <span className="text-text font-semibold tracking-wide">LeapFound</span>
        </motion.div>
        <div className="flex gap-3 text-sm text-muted">
          <a href="#dashboard" className="hover:text-text transition">Dashboard</a>
          <a href="#about" className="hover:text-text transition">About</a>
          <a href="#contact" className="hover:text-text transition">Contact</a>
        </div>
      </div>
    </nav>
  );
}
