/** @type {import('tailwindcss').Config} */
module.exports = {
    darkMode: ["class"],
    content: ["./index.html", "./src/**/*.{ts,tsx,js,jsx}"],
  theme: {
  	extend: {
  		fontFamily: {
  			// IBM Plex only (index.css --font-*); the dead Hanken/JetBrains/Sora fallbacks are gone (v3 W1-C)
  			sans: ['var(--font-sans)', 'system-ui', 'sans-serif'],
  			mono: ['var(--font-mono)', 'monospace'],
  			display: ['var(--font-display)', 'sans-serif'],
  		},
  		// v3 W1-C: one corner for controls (2 px — the old md/sm calc() fell to 0 px and plain
  		// `rounded` was Tailwind's 4 px), 4 px for floating panels. xl/2xl/full stay Tailwind's.
  		borderRadius: {
  			DEFAULT: 'var(--radius)',
  			sm: 'var(--radius)',
  			md: 'var(--radius)',
  			lg: 'var(--radius)',
  			panel: 'var(--radius-panel)'
  		},
  		// v3 W1-C type scale (design §6): 12 metadata only · 14 interface · 16 body · 18 · 24 · 30.
  		// The same six sizes as Tailwind's xs/sm/base/lg/2xl/3xl; the names say what each is for.
  		fontSize: {
  			meta: ['12px', { lineHeight: '16px' }],
  			ui: ['14px', { lineHeight: '20px' }],
  			body: ['16px', { lineHeight: '24px' }],
  			lead: ['18px', { lineHeight: '26px' }],
  			title: ['24px', { lineHeight: '32px' }],
  			display: ['30px', { lineHeight: '36px' }]
  		},
  		// v3 W1-C stacking scale — the --z-* tokens in index.css.
  		zIndex: {
  			canvas: 'var(--z-canvas)',
  			panel: 'var(--z-panel)',
  			popover: 'var(--z-popover)',
  			modal: 'var(--z-modal)',
  			coach: 'var(--z-coach)'
  		},
  		colors: {
  			background: 'hsl(var(--background))',
  			foreground: 'hsl(var(--foreground))',
  			card: {
  				DEFAULT: 'hsl(var(--card))',
  				foreground: 'hsl(var(--card-foreground))'
  			},
  			popover: {
  				DEFAULT: 'hsl(var(--popover))',
  				foreground: 'hsl(var(--popover-foreground))'
  			},
  			primary: {
  				DEFAULT: 'hsl(var(--primary))',
  				foreground: 'hsl(var(--primary-foreground))'
  			},
  			secondary: {
  				DEFAULT: 'hsl(var(--secondary))',
  				foreground: 'hsl(var(--secondary-foreground))'
  			},
  			muted: {
  				DEFAULT: 'hsl(var(--muted))',
  				foreground: 'hsl(var(--muted-foreground))'
  			},
  			accent: {
  				DEFAULT: 'hsl(var(--accent))',
  				foreground: 'hsl(var(--accent-foreground))'
  			},
  			destructive: {
  				DEFAULT: 'hsl(var(--destructive))',
  				foreground: 'hsl(var(--destructive-foreground))'
  			},
  			border: 'hsl(var(--border))',
  			input: 'hsl(var(--input))',
  			ring: 'hsl(var(--ring))',
  			'ink-2': 'hsl(var(--ink-2))',
  			'terracotta-deep': 'hsl(var(--terracotta-deep))',
  			'accent-sand': 'hsl(var(--accent-sand))',
  			'accent-2': 'hsl(var(--accent-2))',
  			'surface-2': 'hsl(var(--surface-2))',
  			'border-strong': 'hsl(var(--border-strong))',
  			chart: {
  				'1': 'hsl(var(--chart-1))',
  				'2': 'hsl(var(--chart-2))',
  				'3': 'hsl(var(--chart-3))',
  				'4': 'hsl(var(--chart-4))',
  				'5': 'hsl(var(--chart-5))'
  			},
  			sidebar: {
  				DEFAULT: 'hsl(var(--sidebar-background))',
  				foreground: 'hsl(var(--sidebar-foreground))',
  				primary: 'hsl(var(--sidebar-primary))',
  				'primary-foreground': 'hsl(var(--sidebar-primary-foreground))',
  				accent: 'hsl(var(--sidebar-accent))',
  				'accent-foreground': 'hsl(var(--sidebar-accent-foreground))',
  				border: 'hsl(var(--sidebar-border))',
  				ring: 'hsl(var(--sidebar-ring))'
  			},
  			'viewer-chrome': 'hsl(var(--viewer-chrome))',
  			'viewer-chrome-foreground': 'hsl(var(--viewer-chrome-foreground))',
  			'viewer-chrome-muted': 'hsl(var(--viewer-chrome-muted))',
  			'viewer-chrome-border': 'hsl(var(--viewer-chrome-border))',
  			'viewer-chrome-hover': 'hsl(var(--viewer-chrome-hover))',
  			'viewer-chrome-active': 'hsl(var(--viewer-chrome-active))',
  			'viewer-blueprint-bg': 'hsl(var(--viewer-blueprint-bg))'
  		},
  		keyframes: {
  			'accordion-down': {
  				from: { height: '0' },
  				to: { height: 'var(--radix-accordion-content-height)' }
  			},
  			'accordion-up': {
  				from: { height: 'var(--radix-accordion-content-height)' },
  				to: { height: '0' }
  			},
  			'pulse-glow': {
  				'0%, 100%': { opacity: '1' },
  				'50%': { opacity: '0.5' }
  			}
  		},
  		animation: {
  			'accordion-down': 'accordion-down 0.2s ease-out',
  			'accordion-up': 'accordion-up 0.2s ease-out',
  			'pulse-glow': 'pulse-glow 2s ease-in-out infinite'
  		}
  	}
  },
  plugins: [require("tailwindcss-animate")],
}
