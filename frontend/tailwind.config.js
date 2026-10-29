/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  darkMode: 'class',
  theme: {
    extend: {
      colors: {
        evidence: {
          grey: '#64748b',
          yellow: '#eab308',
          blue: '#2563eb',
          green: '#16a34a',
          red: '#dc2626',
        }
      }
    },
  },
  plugins: [],
}
