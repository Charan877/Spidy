/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        spidy: {
          bg: '#03060d',
          surface: 'rgba(7, 12, 24, 0.75)',
          border: 'rgba(255, 255, 255, 0.08)',
          hover: 'rgba(255, 255, 255, 0.12)',
          electric: '#38bdf8',
          cyan: '#06b6d4',
          emerald: '#10b981',
          amber: '#f59e0b',
          rose: '#ef4444',
          slate: {
            950: '#03060d',
            900: '#070c18',
            800: '#0e172a',
            700: '#1e293b',
          }
        }
      },
      fontFamily: {
        display: ['"Plus Jakarta Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        body: ['"Plus Jakarta Sans"', 'system-ui', '-apple-system', 'sans-serif'],
        mono: ['"JetBrains Mono"', 'monospace'],
      },
      boxShadow: {
        'subtle': '0 8px 30px rgba(0, 0, 0, 0.5)',
        'glow-electric': '0 0 25px rgba(56, 189, 248, 0.25)',
        'glow-emerald': '0 0 25px rgba(16, 185, 129, 0.25)',
      }
    },
  },
  plugins: [],
}
