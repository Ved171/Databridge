/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      colors: {
        brand: {
          50:  '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d6fe',
          500: '#4f6ef7',
          600: '#3b56e8',
          700: '#2d44cc',
          900: '#1a2880',
        },
      },
    },
  },
  plugins: [],
}
