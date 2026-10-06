import { act, fireEvent, render, screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { ThemeControl } from './ThemeControl'

function systemTheme(dark: boolean) {
  const listeners = new Set<() => void>()
  const media = {
    matches: dark,
    addEventListener: (_event: string, listener: () => void) =>
      listeners.add(listener),
    removeEventListener: (_event: string, listener: () => void) =>
      listeners.delete(listener),
  }
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => media),
  )
  return (next: boolean) =>
    act(() => {
      media.matches = next
      listeners.forEach((listener) => listener())
    })
}

describe('theme preference', () => {
  it('follows system changes by default, with an accessible selected state', () => {
    const changeSystem = systemTheme(true)
    render(<ThemeControl />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(
      screen.getByRole('button', { name: 'System theme' }),
    ).toHaveAttribute('aria-pressed', 'true')
    changeSystem(false)
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
  })

  it('persists explicit selection and restores it after remounting', () => {
    systemTheme(false)
    const view = render(<ThemeControl />)
    fireEvent.click(screen.getByRole('button', { name: 'Dark theme' }))
    expect(localStorage.getItem('ai-sdr.theme')).toBe('dark')
    view.unmount()
    render(<ThemeControl />)
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(document.documentElement.style.colorScheme).toBe('dark')
    expect(screen.getByRole('button', { name: 'Dark theme' })).toHaveAttribute(
      'aria-pressed',
      'true',
    )
  })

  it('keeps a manual choice across OS changes and can return to system mode', () => {
    const changeSystem = systemTheme(false)
    render(<ThemeControl />)
    fireEvent.click(screen.getByRole('button', { name: 'Light theme' }))
    changeSystem(true)
    expect(document.documentElement).toHaveAttribute('data-theme', 'light')
    fireEvent.click(screen.getByRole('button', { name: 'System theme' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
    expect(localStorage.getItem('ai-sdr.theme')).toBe('system')
  })

  it('still switches when browser storage is blocked', () => {
    systemTheme(false)
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('Blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('Blocked')
    })
    render(<ThemeControl />)
    fireEvent.click(screen.getByRole('button', { name: 'Dark theme' }))
    expect(document.documentElement).toHaveAttribute('data-theme', 'dark')
  })
})
