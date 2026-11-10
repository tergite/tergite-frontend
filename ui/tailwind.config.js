/** @type {import('tailwindcss').Config} */
module.exports = {
  darkMode: ["class"],
  content: [
    './pages/**/*.{ts,tsx}',
    './components/**/*.{ts,tsx}',
    './app/**/*.{ts,tsx}',
    './src/**/*.{ts,tsx}',
  ],
  prefix: "",
  theme: {
    container: {
      center: true,
      padding: "2rem",
      screens: {
        "2xl": "1400px",
      },
    },
    extend: {
      fontFamily: {
        sans: ['"DM Sans"', "sans-serif"],
        display: ['"Space Grotesk"'],
      },
      colors: {
        border: "hsl(var(--border))",
        input: "hsl(var(--input))",
        ring: "hsl(var(--ring))",
        background: "hsl(var(--background))",
        foreground: "hsl(var(--foreground))",
        primary: {
          DEFAULT: "hsl(var(--primary))",
          foreground: "hsl(var(--primary-foreground))",
        },
        secondary: {
          DEFAULT: "hsl(var(--secondary))",
          foreground: "hsl(var(--secondary-foreground))",
        },
        destructive: {
          DEFAULT: "hsl(var(--destructive))",
          foreground: "hsl(var(--destructive-foreground))",
        },
        muted: {
          DEFAULT: "hsl(var(--muted))",
          foreground: "hsl(var(--muted-foreground))",
        },
        accent: {
          DEFAULT: "hsl(var(--accent))",
          foreground: "hsl(var(--accent-foreground))",
        },
        popover: {
          DEFAULT: "hsl(var(--popover))",
          foreground: "hsl(var(--popover-foreground))",
        },
        card: {
          DEFAULT: "hsl(var(--card))",
          foreground: "hsl(var(--card-foreground))",
        },
        signal: "hsl(var(--signal))",
        success: {
          DEFAULT: "hsl(var(--success))",
          tint: "hsl(var(--success-tint))",
        },
        sidebar: {
          DEFAULT: "hsl(var(--sidebar))",
          foreground: "hsl(var(--sidebar-foreground))",
          highlight: "hsl(var(--sidebar-highlight))",
          strong: "hsl(var(--sidebar-strong))",
          soft: "hsl(var(--sidebar-soft))",
          muted: "hsl(var(--sidebar-muted))",
          subtle: "hsl(var(--sidebar-subtle))",
          primary: "hsl(var(--sidebar-primary))",
          "primary-soft": "hsl(var(--sidebar-primary-soft))",
          ring: "hsl(var(--sidebar-ring))",
          veil: "hsl(var(--sidebar-veil))",
        },
      },
      // Tailwind drops the alpha of an hsl(var()) colour in a shadow, so these live in index.css
      boxShadow: {
        card: "var(--shadow-card)",
        "metric-hover": "var(--shadow-metric-hover)",
        "device-hover": "var(--shadow-device-hover)",
        sidebar: "var(--shadow-sidebar)",
        "nav-active": "var(--shadow-nav-active)",
      },
      borderRadius: {
        lg: "var(--radius)",
        md: "calc(var(--radius) - 2px)",
        sm: "calc(var(--radius) - 4px)",
      },
      keyframes: {
        "accordion-down": {
          from: { height: "0" },
          to: { height: "var(--radix-accordion-content-height)" },
        },
        "accordion-up": {
          from: { height: "var(--radix-accordion-content-height)" },
          to: { height: "0" },
        },
      },
      animation: {
        "accordion-down": "accordion-down 0.2s ease-out",
        "accordion-up": "accordion-up 0.2s ease-out",
      },
    },
  },
  plugins: [require("tailwindcss-animate")],
}