/** @type {import('tailwindcss').Config} */
import defaultTheme from "tailwindcss/defaultTheme";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      fontFamily: {
        sans: ["Inter", ...defaultTheme.fontFamily.sans],
      },
      colors: {
        brand: {
          50: "#f2f6fa",
          100: "#e2ebf4",
          200: "#c4d7e8",
          300: "#9bbad6",
          400: "#6694bd",
          500: "#4476a4",
          600: "#335e89",
          700: "#2a4c70",
          800: "#24405e",
          900: "#1e3a5f",
          950: "#142841",
        },
      },
      boxShadow: {
        card: "0 1px 2px 0 rgb(15 23 42 / 0.04), 0 1px 3px 0 rgb(15 23 42 / 0.06)",
      },
    },
  },
  plugins: [],
};
