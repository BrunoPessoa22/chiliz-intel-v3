import type { Config } from 'tailwindcss'

const config: Config = {
  darkMode: ['class'],
  content: [
    './pages/**/*.{js,ts,jsx,tsx,mdx}',
    './components/**/*.{js,ts,jsx,tsx,mdx}',
    './app/**/*.{js,ts,jsx,tsx,mdx}',
  ],
  theme: {
    extend: {
      colors: {
        chiliz: {
          red: '#CD0124',
          dark: '#1a1a2e',
          darker: '#0f0f1a',
        },
        grade: {
          a: '#22c55e',
          b: '#84cc16',
          c: '#eab308',
          d: '#f97316',
          f: '#ef4444',
        }
      },
    },
  },
  plugins: [require('tailwindcss-animate')],
}
export default config
