/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Immich-inspired palette
        immich: {
          primary: "#4250af",
          bg: "#1e1e2e",
          surface: "#27273a",
          border: "#3d3d57",
        },
      },
    },
  },
  plugins: [],
};
