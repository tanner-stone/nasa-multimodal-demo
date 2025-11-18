/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        dark: {
          bg: '#000000',
          surface: '#0a0a0a',
          card: '#111111',
          border: '#00ff41',
          text: '#00ff41',
          muted: '#00cc33'
        },
        neon: {
          green: '#00ff41',
          'green-dark': '#00cc33',
          'green-glow': '#00ff41'
        }
      },
      boxShadow: {
        'neon': '0 0 5px #00ff41, 0 0 10px #00ff41',
        'neon-lg': '0 0 10px #00ff41, 0 0 20px #00ff41, 0 0 30px #00ff41',
      }
    },
  },
  plugins: [],
}
