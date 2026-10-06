import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { trimRecording } from './trim-recording.mjs'

// Run with Vite listening locally. This opens only our local capture page.
const directory = path.resolve('public/examples')
await mkdir(directory, { recursive: true })
const browser = await chromium.launch({
  channel: process.env.BROWSER_CHANNEL || 'msedge',
  headless: true,
})
try {
  for (const scene of process.argv[2]
    ? [process.argv[2]]
    : ['workflow', 'evidence']) {
    const context = await browser.newContext({
      viewport: { width: 880, height: 720 },
      recordVideo: {
        dir: path.resolve('.recordings'),
        size: { width: 880, height: 720 },
      },
    })
    const page = await context.newPage()
    await page.goto(`http://127.0.0.1:5173/tools/capture.html?scene=${scene}`)
    await page.waitForSelector('body[data-capture-ready="true"]')
    await page.evaluate(() => document.fonts.ready)
    if (scene === 'workflow') {
      await page.evaluate(() =>
        window.dispatchEvent(new Event('recording:start')),
      )
      await page
        .getByText('Ready for your review', { exact: true })
        .waitFor({ timeout: 20000 })
      await page.screenshot({ path: path.join(directory, `${scene}.png`) })
      await page.waitForTimeout(2500)
    } else {
      await page.getByRole('tab', { name: /Research/ }).click()
      await page
        .locator('summary')
        .filter({ hasText: 'A more personal start' })
        .click()
      await page.screenshot({ path: path.join(directory, `${scene}.png`) })
      await page.waitForTimeout(4500)
      await page.getByRole('tab', { name: 'Approach' }).click()
      await page.waitForTimeout(4500)
    }
    const video = page.video()
    await context.close()
    const raw = path.resolve('.recordings', `${scene}-raw.webm`)
    await video.saveAs(raw)
    await video.delete()
    await trimRecording(
      browser,
      raw,
      `/.recordings/${scene}-raw.webm`,
      path.join(directory, `${scene}.webm`),
    )
    console.log(`Recorded ${scene}`)
  }
} finally {
  await browser.close()
}
