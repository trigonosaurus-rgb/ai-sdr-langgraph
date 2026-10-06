import { useEffect, useState } from 'react'
import { Monitor, Moon, Sun } from 'lucide-react'

type Theme = 'light' | 'dark' | 'system'
const storageKey = 'ai-sdr.theme'
const options = [
  { value: 'light', label: 'Light theme', icon: Sun },
  { value: 'dark', label: 'Dark theme', icon: Moon },
  { value: 'system', label: 'System theme', icon: Monitor },
] as const

function readTheme(): Theme {
  try {
    const saved = localStorage.getItem(storageKey)
    if (saved === 'light' || saved === 'dark') return saved
  } catch {
    /* The switch still works when storage is unavailable. */
  }
  return 'system'
}

export function ThemeControl() {
  const [theme, setTheme] = useState<Theme>(readTheme)

  useEffect(() => {
    const media = window.matchMedia?.('(prefers-color-scheme: dark)')
    function applyTheme() {
      const resolved =
        theme === 'system' ? (media?.matches ? 'dark' : 'light') : theme
      document.documentElement.dataset.theme = resolved
      document.documentElement.style.colorScheme = resolved
      document
        .querySelector('meta[name="theme-color"]')
        ?.setAttribute('content', resolved === 'dark' ? '#191919' : '#f6f6f3')
    }
    applyTheme()
    media?.addEventListener('change', applyTheme)
    return () => media?.removeEventListener('change', applyTheme)
  }, [theme])

  function selectTheme(next: Theme) {
    setTheme(next)
    try {
      localStorage.setItem(storageKey, next)
    } catch {
      /* Session-only fallback. */
    }
  }

  return (
    <div className="theme-control" role="group" aria-label="Color theme">
      {options.map(({ value, label, icon: Icon }) => (
        <button
          type="button"
          key={value}
          aria-label={label}
          title={label}
          aria-pressed={theme === value}
          onClick={() => selectTheme(value)}
        >
          <Icon size={15} />
        </button>
      ))}
    </div>
  )
}
