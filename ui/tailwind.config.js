/** @type {import('tailwindcss').Config} */
export default {
  content: [
    "./index.html",
    "./src/**/*.{js,ts,jsx,tsx}",
  ],
  theme: {
    extend: {
      colors: {
        pass: '#10b981',
        fail: '#ef4444',
        warn: '#f59e0b',
        skipped: '#6b7280',
      },
    },
  },
  plugins: [],
}
