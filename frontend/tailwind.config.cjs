/** @type {import('tailwindcss').Config} */
module.exports = {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        bg: "#0b0f14",
        card: "#0f1520",
        line: "#1f2a37",
        brand: "#4f46e5",
        brand2: "#22d3ee",
        text: "#e5e7eb",
        muted: "#9aa7b2",
      },
      boxShadow: {
        soft: "0 10px 30px rgba(0,0,0,.35)",
        glow: "0 0 40px rgba(34,211,238,.25)",
      },
      borderRadius: { xl2: "1.25rem" },
    },
  },
  plugins: [require("@tailwindcss/forms"), require("@tailwindcss/typography")],
};
