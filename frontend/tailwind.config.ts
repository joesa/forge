import type { Config } from 'tailwindcss'
import forms from '@tailwindcss/forms'

const config: Config = {
  content: ['./src/**/*.{ts,tsx}'],
  theme: {
    extend: {
      colors: {
        void: '#04040a',
        surface: '#080812',
        panel: '#0d0d1f',
        card: '#111125',
        forge: {
          DEFAULT: '#63d9ff',
          dim: 'rgba(99,217,255,0.10)',
        },
        ember: {
          DEFAULT: '#ff6b35',
          dim: 'rgba(255,107,53,0.10)',
        },
        gold: {
          DEFAULT: '#f5c842',
          dim: 'rgba(245,200,66,0.08)',
        },
        jade: {
          DEFAULT: '#3dffa0',
          dim: 'rgba(61,255,160,0.08)',
        },
        violet: {
          DEFAULT: '#b06bff',
          dim: 'rgba(176,107,255,0.10)',
        },
        text: '#e8e8f0',
        muted: 'rgba(232,232,240,0.42)',
        faint: 'rgba(232,232,240,0.15)',
        border: {
          DEFAULT: 'rgba(255,255,255,0.06)',
          bright: 'rgba(99,217,255,0.22)',
        },
      },
      fontFamily: {
        sans: ['Syne', 'sans-serif'],
        syne: ['Syne', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
        'serif-i': ['Instrument Serif', 'serif'],
      },
      keyframes: {
        'pulse-f': {
          '0%, 100%': { opacity: '1' },
          '50%': { opacity: '0.4' },
        },
        spin: {
          to: { transform: 'rotate(360deg)' },
        },
        'fade-in': {
          from: { opacity: '0', transform: 'translateY(8px)' },
          to: { opacity: '1', transform: 'translateY(0)' },
        },
        'jade-pulse': {
          '0%, 100%': { boxShadow: '0 0 0 0 rgba(61,255,160,0.4)' },
          '50%': { boxShadow: '0 0 0 5px rgba(61,255,160,0)' },
        },
      },
      animation: {
        'pulse-f': 'pulse-f 1.8s ease-in-out infinite',
        spin: 'spin 1s linear infinite',
        'fade-in': 'fade-in 280ms ease',
        'jade-pulse': 'jade-pulse 2s ease-in-out infinite',
      },
    },
  },
  plugins: [forms],
}

export default config
