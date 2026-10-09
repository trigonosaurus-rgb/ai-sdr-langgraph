import { chromium } from '@playwright/test'
import { mkdir } from 'node:fs/promises'
import path from 'node:path'
import { trimRecording } from './trim-recording.mjs'

// Records the Examples videos from real runs exported with tools/export-run.mjs.
//   node tools/record-examples.mjs workflow=<run> evidence=<run>
// Run with Vite listening locally. This opens only our local capture page.
const scenes = process.argv.slice(2).map((arg) => arg.split('='))
if (
  !scenes.length ||
  scenes.some(
    ([scene, run]) => !['workflow', 'evidence'].includes(scene) || !run,
  )
) {
  console.error(
    'Usage: node tools/record-examples.mjs workflow=<run> evidence=<run>',
  )
  process.exit(1)
}
const directory = path.resolve('public/examples')
await mkdir(directory, { recursive: true })
const browser = await chromium.launch({
  channel: process.env.BROWSER_CHANNEL || 'msedge',
  headless: true,
})
const pause = (page, ms) => page.waitForTimeout(ms)
// Scroll the visible tab's column slowly to its end, so the whole list is seen.
async function scrollThrough(page) {
  await page.evaluate(async () => {
    const column = document.querySelector('.draft-column')
    const end = column.scrollHeight - column.clientHeight
    for (let top = 0; top < end; top += 2) {
      column.scrollTop = top
      await new Promise((resolve) => setTimeout(resolve, 16))
    }
  })
}
try {
  for (const [scene, run] of scenes) {
    const context = await browser.newContext({
      viewport: { width: 880, height: 720 },
      recordVideo: {
        dir: path.resolve('.recordings'),
        size: { width: 880, height: 720 },
      },
    })
    const page = await context.newPage()
    await page.goto(
      `http://127.0.0.1:5173/tools/capture.html?run=${run}&scene=${scene}`,
    )
    await page.waitForSelector('body[data-capture-ready="true"]')
    await page.evaluate(() => document.fonts.ready)
    if (scene === 'workflow') {
      await page.evaluate(() =>
        window.dispatchEvent(new Event('recording:start')),
      )
      await page.waitForSelector('body[data-played="true"]', { timeout: 60000 })
      await pause(page, 1500)
      await page.screenshot({ path: path.join(directory, `${scene}.png`) })
      await scrollThrough(page) // a longer email continues below the frame
      await pause(page, 2000)
    } else {
      await page.getByRole('tab', { name: /Research/ }).click()
      await pause(page, 600)
      await page.screenshot({ path: path.join(directory, `${scene}.png`) })
      await pause(page, 2500)
      await scrollThrough(page)
      await pause(page, 2000)
      await page.getByRole('tab', { name: 'Approach' }).click()
      await pause(page, 5000)
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
    console.log(`Recorded ${scene} from ${run}`)
  }
} finally {
  await browser.close()
}
