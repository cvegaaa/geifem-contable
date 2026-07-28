/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,jsx}"],
  theme: {
    extend: {
      colors: {
        geifem: {
          // Paleta oficial GEIFEM
          navy: "#14315E",       // Azul seiroleo (principal)
          "navy-dark": "#0E2547",
          blue: "#1E5A7C",       // Azul corporativo (secundario)
          "blue-light": "#2C7BA8",
          gold: "#C9A961",       // Dorado degame
          "gold-light": "#E0C68A",
          "gold-dark": "#A7893F",
        },
      },
      fontFamily: {
        sans: ["Montserrat", "system-ui", "sans-serif"],
      },
    },
  },
  plugins: [],
};
