import { motion } from "framer-motion";
export default function Hero() {
  return (
    <section className="pt-28 pb-16 px-6 relative">
      <div className="max-w-6xl mx-auto text-center relative z-10">
        <motion.h1 initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{duration:.7}}
          className="text-6xl md:text-7xl font-semibold text-white tracking-tight drop-shadow">
          LeapFound — LIVE TEST ✅
        </motion.h1>
        <motion.p initial={{opacity:0,y:12}} animate={{opacity:1,y:0}} transition={{delay:.15,duration:.7}}
          className="mt-4 text-lg text-[#cbd5e1]">
          If you can read this, the UI is updating correctly.
        </motion.p>
      </div>
    </section>
  );
}
