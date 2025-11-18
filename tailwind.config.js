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
          card: '#0A6E0A',
          border: '#00ff41',
          text: '#00ff41',
          muted: '#00cc33'
        },
        neon: {
          green: '#00ff41',
          'green-dark': '#00cc33',
          'green-glow': '#00ff41'
        },
        'neo-mint': '#00ff41',
        'muted-green': '#00cc33',
        'neon-cyan': '#00d9ff',
        'lime-green': '#A0FF00',
        'electric-cyan': '#00FFFF',
        'dark-lime': '#66CC00',
        'dark-gray-green': '#334D33',
        'dark-emerald': '#0A6E0A'
      },
      boxShadow: {
        'neon': '0 0 5px #00ff41, 0 0 10px #00ff41',
        'neon-lg': '0 0 10px #00ff41, 0 0 20px #00ff41, 0 0 30px #00ff41',
      }
    },
  },
  plugins: [],
}
