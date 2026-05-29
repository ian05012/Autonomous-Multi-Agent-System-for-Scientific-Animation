/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        studio: {
          black: "#030303",
          panel: "rgba(24, 22, 31, 0.72)",
          border: "rgba(255, 255, 255, 0.12)",
          purple: "#9346ff",
          violet: "#c59cff",
          ink: "#f7f3ff",
          muted: "#b8b2c3",
        },
      },
      boxShadow: {
        glow: "0 0 90px rgba(147, 70, 255, 0.28)",
      },
    },
  },
  plugins: [],
};
