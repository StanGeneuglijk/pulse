import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        base: "#07070B",
        ink: "#0E0E14",
        line: "rgba(255,255,255,0.08)",
        recovery: { high: "#22E57A", mid: "#FFD60A", low: "#FF3B5C" },
        strain: "#3AA0FF",
        sleep: "#9B8CFF",
        fuel: { DEFAULT: "#FF6B3D", pink: "#FF2E93", amber: "#FFB547" },
      },
      fontFamily: {
        sans: ["var(--font-inter)", "system-ui", "sans-serif"],
        display: ["var(--font-display)", "var(--font-inter)", "sans-serif"],
      },
      backgroundImage: {
        "fuel-gradient": "linear-gradient(135deg, #FFB547 0%, #FF6B3D 45%, #FF2E93 100%)",
        "brand-gradient": "linear-gradient(135deg, #22E57A 0%, #3AA0FF 50%, #9B8CFF 100%)",
      },
      boxShadow: {
        glass: "inset 0 1px 0 0 rgba(255,255,255,0.06), 0 20px 50px -20px rgba(0,0,0,0.7)",
        fuel: "0 0 60px -12px rgba(255,107,61,0.55)",
      },
      keyframes: {
        "fade-in-up": {
          "0%": { opacity: "0", transform: "translateY(10px)" },
          "100%": { opacity: "1", transform: "translateY(0)" },
        },
        wave: {
          "0%, 100%": { transform: "scaleY(0.3)" },
          "50%": { transform: "scaleY(1)" },
        },
        float: {
          "0%, 100%": { transform: "translate(0, 0) scale(1)" },
          "50%": { transform: "translate(30px, -20px) scale(1.08)" },
        },
        shimmer: {
          "0%": { backgroundPosition: "-200% 0" },
          "100%": { backgroundPosition: "200% 0" },
        },
      },
      animation: {
        "fade-in-up": "fade-in-up 0.6s cubic-bezier(0.16, 1, 0.3, 1) both",
        wave: "wave 0.9s ease-in-out infinite",
        float: "float 14s ease-in-out infinite",
        shimmer: "shimmer 3s linear infinite",
      },
    },
  },
  plugins: [],
};

export default config;
