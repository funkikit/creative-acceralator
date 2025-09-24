import type { Config } from "tailwindcss";

const config: Config = {
  content: ["./app/**/*.{ts,tsx}", "./components/**/*.{ts,tsx}"],
  theme: {
    extend: {
      colors: {
        primary: {
          50: "#f2f6ff",
          100: "#e6eeff",
          200: "#c7d5ff",
          300: "#a8bbff",
          400: "#6b8bff",
          500: "#2e5bff",
          600: "#284fde",
          700: "#1d39b1",
          800: "#142784",
          900: "#0d1a5f"
        }
      }
    }
  },
  plugins: []
};

export default config;
