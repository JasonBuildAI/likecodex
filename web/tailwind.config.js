/** @type {import('tailwindcss').Config} */
module.exports = {
  content: [
    './src/pages/**/*.{js,ts,jsx,tsx,mdx}',
    './src/components/**/*.{js,ts,jsx,tsx,mdx}',
    './src/app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        background: '#0f1117',
        surface: '#1a1d26',
        border: '#2a2e3b',
        primary: '#3b82f6',
        muted: '#9ca3af',
      },
    },
  },
  plugins: [],
}
