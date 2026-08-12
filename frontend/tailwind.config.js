/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{ts,tsx}"],
  theme: {
    extend: {
      // Palette from docs/identity/es.md -- "Noche Templada" (tempered
      // night): a warm-charcoal dark mode instead of neutral OLED black, so
      // the app reads as calm/human during an emergency rather than as an
      // alarm panel, while keeping full dark-mode contrast and battery cost.
      colors: {
        night: "#17140F", // Fondo Principal
        card: "#241F1A", // Superficie / Cards
        brand: "#CC8B3C", // Marca Principal (Ocre Templado)
        safe: "#6FB98F", // Estado "Estoy Bien" (Verde Salvia)
        danger: "#E1755F", // Estado "Necesito Ayuda" (Terracota)
        pending: "#E8C468", // Estado "Esperando" (Dorado Suave)
        ink: "#F5EFE6", // Texto Principal
        muted: "#B8A99A", // Texto Secundario
      },
      fontFamily: {
        // System font stack only -- no downloadable web fonts, per the
        // identity guide's low-bandwidth/offline-first priority.
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          '"Segoe UI"',
          "Roboto",
          "Oxygen",
          "Ubuntu",
          "Cantarell",
          "sans-serif",
        ],
      },
    },
  },
  plugins: [],
};
