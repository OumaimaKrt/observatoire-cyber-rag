/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        // Palette Zellige Marocain
        background: "#0F1B2D",
        surface: "#16243B",
        surfaceLight: "#1E3050",
        gold: "#C9932E",
        goldLight: "#D4A843",
        goldDark: "#B8860B",
        text: "#E8E4DA",
        textMuted: "#8A8A8A",
        alert: "#C4453D",
        alertLight: "#D95B52",
        severity: {
          critical: "#C4453D",
          high: "#E67A4A",
          medium: "#C9932E",
          low: "#4A7C8E",
          unknown: "#5A5A5A",
        },
        border: "#16243B",
        zellige: {
          blue: "#1A3A5C",
          gold: "#C9932E",
          white: "#E8E4DA",
          red: "#C4453D",
          green: "#2D6A4F",
        }
      },
      fontFamily: {
        display: ['Space Grotesk', 'Fraunces', 'serif'],
        sans: ['Inter', 'IBM Plex Sans', 'sans-serif'],
      },
      borderRadius: {
        DEFAULT: "0.5rem",
        lg: "0.75rem",
        xl: "1rem",
      },
      borderColor: {
        DEFAULT: "#16243B",
      },
      backgroundColor: {
        DEFAULT: "#0F1B2D",
      },
    },
  },
  plugins: [],
}