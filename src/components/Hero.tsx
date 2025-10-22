import { motion } from "framer-motion";

export default function Hero() {
  return (
    <section className="pt-28 pb-16 px-6">
      <div className="max-w-6xl mx-auto text-center">
        <motion.h1
          initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{duration:.8}}
          className="text-5xl md:text-6xl font-semibold text-text tracking-tight"
        >
          Your AI Business Partner
        </motion.h1>
        <motion.p
          initial={{opacity:0,y:8}} animate={{opacity:1,y:0}} transition={{delay:.15,duration:.8}}
          className="mt-4 text-lg text-muted"
        >
          Fluid, glassy, and calm—LeapFound analyzes, advises, and automates.
        </motion.p>
      </div>
    </section>
  );
}
