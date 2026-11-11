/** iOS 设计系统 token —— Fab Bot Desktop */
/** @type {import('tailwindcss').Config} */
export default {
  darkMode: "class",
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        ios: {
          bg: "#F2F2F7",
          card: "#FFFFFF",
          darkBg: "#000000",
          darkCard: "#1C1C1E",
          darkCard2: "#2C2C2E",
          blue: "#0A84FF",
          green: "#30D158",
          red: "#FF453A",
          orange: "#FF9500",
          yellow: "#FFD60A",
          separator: "rgba(60,60,67,0.29)",
          label: "#1C1B1F",
          label2: "rgba(60,60,67,0.60)",
        },
      },
      fontFamily: {
        sans: ['"MiSans"', '"HarmonyOS Sans SC"', '"Segoe UI"', 'system-ui', 'sans-serif'],
      },
      borderRadius: { card: "16px", win: "10px" },
      boxShadow: {
        card: "0 1px 3px rgba(20,30,50,.06), 0 4px 16px rgba(20,30,50,.05)",
        float: "0 12px 48px rgba(10,20,40,.22)",
      },
      transitionTimingFunction: { ios: "cubic-bezier(0.32,0.72,0,1)" },
    },
  },
  plugins: [],
};
