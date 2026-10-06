import { expect, test } from '@playwright/test'

for (const width of [1440, 1024, 390, 360]) {
  test(`costs dialog and responsive layout at ${width}px`, async ({ page }) => {
    await page.setViewportSize({ width, height: 900 })
    await page.goto('/')
    await page.getByRole('button', { name: 'Dark theme' }).click()
    expect(
      await page.evaluate(
        () => document.documentElement.scrollWidth <= innerWidth,
      ),
    ).toBe(true)
    if (width < 700)
      await page.getByRole('button', { name: 'Open navigation' }).click()
    await page.getByRole('button', { name: 'Run costs' }).click()
    const dialog = page.getByRole('dialog', { name: 'Run costs' })
    await expect(dialog).toBeVisible()
    await expect(dialog).toContainText('No run yet')
    const panel = await page.locator('.modal-content').boundingBox()
    const close = await page
      .getByRole('button', { name: 'Close dialog' })
      .boundingBox()
    expect(
      panel &&
        close &&
        (close.x >= panel.x + panel.width || close.y + close.height <= panel.y),
    ).toBeTruthy()
    expect(
      await dialog.evaluate(
        (el) => getComputedStyle(el, '::backdrop').backdropFilter,
      ),
    ).toContain('blur')
    await page.keyboard.press('Escape')
    await expect(dialog).not.toBeVisible()
    await expect(
      page.getByRole('button', {
        name: width < 700 ? 'Open navigation' : 'Run costs',
      }),
    ).toBeFocused()
    await page.getByRole('button', { name: 'Light theme' }).click()
    await page.screenshot({
      path: `test-results/workspace-${width}.png`,
      fullPage: true,
    })
  })
}
test('examples autoplay, pause, preserve the brief and load on a direct link', async ({
  page,
}) => {
  await page.goto('/')
  await page.getByLabel('Company name').fill('My company')
  await page.getByRole('link', { name: 'Examples', exact: true }).click()
  const video = page.locator('video').first()
  await expect
    .poll(() => video.evaluate((el: HTMLVideoElement) => el.currentTime))
    .toBeGreaterThan(0.3)
  await expect(video).toHaveJSProperty('muted', true)
  await expect(video).toHaveJSProperty('loop', true)
  await page
    .getByRole('button', { name: 'Pause From context to a first draft.' })
    .click()
  await expect(video).toHaveJSProperty('paused', true)
  // Media time can advance while the recording still contains blank startup frames.
  for (const film of await page.locator('video').all()) {
    const firstPixel = await film.evaluate(async (el: HTMLVideoElement) => {
      el.pause()
      if (el.readyState < 2)
        await new Promise((resolve) =>
          el.addEventListener('loadeddata', resolve, { once: true }),
        )
      const seeked = new Promise((resolve) =>
        el.addEventListener('seeked', resolve, { once: true }),
      )
      el.currentTime = 0.1
      await seeked
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 1
      const context = canvas.getContext('2d')!
      context.drawImage(el, 0, 0, 1, 1, 0, 0, 1, 1)
      return context.getImageData(0, 0, 1, 1).data[0]
    })
    expect(firstPixel).toBeLessThan(160)
  }
  await page.getByRole('link', { name: 'Compose', exact: true }).click()
  await expect(page.getByLabel('Company name')).toHaveValue('My company')
  await page.goto('/#examples')
  await expect(page.getByRole('heading', { level: 1 })).toHaveText(
    'Small details. Better outreach.',
  )
})
test('reduced motion leaves videos paused with a manual play control', async ({
  page,
}) => {
  await page.emulateMedia({ reducedMotion: 'reduce' })
  await page.goto('/#examples')
  await expect(page.locator('video').first()).toHaveJSProperty('paused', true)
  await page
    .getByRole('button', { name: 'Play From context to a first draft.' })
    .click()
  await expect
    .poll(() =>
      page
        .locator('video')
        .first()
        .evaluate((el: HTMLVideoElement) => el.currentTime),
    )
    .toBeGreaterThan(0.3)
})
