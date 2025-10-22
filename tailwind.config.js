/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#030712",
        card: "rgba(255,255,255,0.04)",
        accent: "#38bdf8",
        accent2: "#6366f1",
        text: "#e5e7eb",
        muted: "#9ca3af",
      },
      boxShadow: {
        glow: "0 0 40px rgba(56,189,248,.25)",
        soft: "0 10px 30px rgba(0,0,0,.35)",
      },
      backdropBlur: { xl: "24px" },
    },
  },
  plugins: [],
}
