/** @type {import('tailwindcss').Config} */
export default {
  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],
  theme: {
    extend: {
      fontFamily: {
        headline: ['Manrope', 'sans-serif'],
        body: ['Inter', 'sans-serif'],
        mono: ['JetBrains Mono', 'monospace'],
      },
      maxWidth: {
        content: '1400px',
      },
      width: {
        sidebar: '260px',
      },
      boxShadow: {
        card: '0 4px 12px -2px rgba(26, 25, 22, 0.05)',
      },
      colors: {
        surface: {
          DEFAULT: '#faf9f5',
          dim: '#dbdad6',
          bright: '#faf9f5',
          container: {
            lowest: '#ffffff',
            low: '#f4f4f0',
            DEFAULT: '#efeeea',
            high: '#e9e8e4',
            highest: '#e3e2df',
          },
        },
        'on-surface': {
          DEFAULT: '#1b1c1a',
          variant: '#494740',
        },
        outline: {
          DEFAULT: '#7a776f',
          variant: '#cbc6bd',
        },
        accent: {
          50: '#eef4f5',
          100: '#d5e5e8',
          200: '#adc9cf',
          300: '#7fa8b0',
          400: '#5c8d96',
          500: '#48757c',
          600: '#3a5f65',
          700: '#2f4d52',
          800: '#243d41',
          900: '#1a2d30',
        },
        success: {
          DEFAULT: '#15803d',
          bg: '#dcfce7',
          border: '#bbf7d0',
        },
        warning: {
          DEFAULT: '#b45309',
          bg: '#ffedd5',
          border: '#fed7aa',
        },
        error: {
          DEFAULT: '#ba1a1a',
          bg: '#ffdad6',
          border: '#fecaca',
        },
        // Legacy aliases for existing pages
        'bg-base': 'var(--color-bg-base)',
        'bg-surface': 'var(--color-bg-surface)',
        'bg-card': 'var(--color-bg-card)',
        'bg-overlay': 'var(--color-bg-overlay)',
        'border-default': 'var(--color-border-default)',
        'border-muted': 'var(--color-border-muted)',
        'border-strong': 'var(--color-border-strong)',
        'text-primary': 'var(--color-text-primary)',
        'text-secondary': 'var(--color-text-secondary)',
        'text-muted': 'var(--color-text-muted)',
        'text-subtle': 'var(--color-text-subtle)',
        'text-inverse': 'var(--color-text-inverse)',
        sidebar: {
          bg: 'var(--color-sidebar-bg)',
          hover: 'var(--color-sidebar-hover)',
          border: 'var(--color-sidebar-border)',
          text: 'var(--color-sidebar-text)',
          active: 'var(--color-sidebar-active)',
        },
        brand: {
          50: '#f0f4ff',
          100: '#e0e9ff',
          200: '#c7d6fe',
          500: '#4f6ef7',
          600: '#3b56e8',
          700: '#2d44cc',
          900: '#1a2880',
        },
      },
      borderRadius: {
        card: '0.75rem',
      },
    },
  },
  plugins: [],
}
