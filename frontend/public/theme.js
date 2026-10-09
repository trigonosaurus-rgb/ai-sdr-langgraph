// Apply the theme preference before the stylesheet to avoid a light flash.
// A plain file rather than an inline script, so the Content-Security-Policy can stay 'self'.
;(() => {
  let theme = 'system'
  try {
    theme = localStorage.getItem('ai-sdr.theme') || 'system'
  } catch {}
  const resolved =
    theme === 'light' || theme === 'dark'
      ? theme
      : matchMedia('(prefers-color-scheme: dark)').matches
        ? 'dark'
        : 'light'
  document.documentElement.dataset.theme = resolved
  document.documentElement.style.colorScheme = resolved
  document.querySelector('meta[name="theme-color"]').content =
    resolved === 'dark' ? '#191919' : '#f6f6f3'
})()
