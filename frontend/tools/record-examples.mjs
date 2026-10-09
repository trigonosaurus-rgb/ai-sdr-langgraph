import { chromium } from '@playwright/test'
import { spawn } from 'node:child_process'
import { createWriteStream } from 'node:fs'
import { mkdir, readdir, rm } from 'node:fs/promises'
import path from 'node:path'

// Records the Examples videos from real runs exported with tools/export-run.mjs.
//   node tools/record-examples.mjs workflow=<run> evidence=<run>
// Run with Vite listening locally. This opens only our local capture page.
//
// Frames come straight from Chromium's screencast as JPEG at quality 100 and are encoded once, by quality,
// with a single keyframe. Playwright's own recorder encodes in real time at 1 Mbit/s with periodic
// keyframes, which blurred the text on scrolls and flashed a soft frame every few seconds.
const FPS = 25
const SIZE = { width: 880, height: 720 }

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

// Playwright's bundled ffmpeg decodes only MJPEG, encodes VP8 and reads frames from a file, not a pipe.
// Use FFMPEG_PATH elsewhere.
async function findFfmpeg() {
  if (process.env.FFMPEG_PATH) return process.env.FFMPEG_PATH
  const cache = path.join(process.env.LOCALAPPDATA ?? '', 'ms-playwright')
  const folder = (await readdir(cache).catch(() => []))
    .filter((name) => name.startsWith('ffmpeg-'))
    .sort()
    .at(-1)
  if (!folder) throw new Error('Run: npx playwright install ffmpeg')
  return path.join(cache, folder, 'ffmpeg-win64.exe')
}

// Screencast frames arrive only when the page changes; collect them with their timestamps.
async function startCapture(page) {
  const cdp = await page.context().newCDPSession(page)
  const frames = []
  cdp.on('Page.screencastFrame', ({ data, metadata, sessionId }) => {
    frames.push({ at: metadata.timestamp, jpeg: Buffer.from(data, 'base64') })
    cdp.send('Page.screencastFrameAck', { sessionId }).catch(() => {})
  })
  // The page may be idle when capture starts: begin with a screenshot so frame zero exists.
  frames.push({
    at: Date.now() / 1000,
    jpeg: await page.screenshot({ type: 'jpeg', quality: 100 }),
  })
  await cdp.send('Page.startScreencast', {
    format: 'jpeg',
    quality: 100,
    maxWidth: SIZE.width,
    maxHeight: SIZE.height,
    everyNthFrame: 1,
  })
  return async () => {
    await cdp.send('Page.stopScreencast')
    return { frames, end: Date.now() / 1000 }
  }
}

// Resample to a constant frame rate (each tick shows the latest frame) and encode VP8 by quality.
async function encode(ffmpeg, { frames, end }, output) {
  frames.sort((a, b) => a.at - b.at)
  const start = frames[0].at
  const ticks = Math.ceil((end - start) * FPS)
  const stream = path.resolve('.recordings', `${path.basename(output)}.mjpeg`)
  await mkdir(path.dirname(stream), { recursive: true })
  const file = createWriteStream(stream)
  let next = 0
  for (let tick = 0; tick < ticks; tick++) {
    const time = start + tick / FPS
    while (next + 1 < frames.length && frames[next + 1].at <= time) next++
    if (!file.write(frames[next].jpeg))
      await new Promise((resolve) => file.once('drain', resolve))
  }
  await new Promise((resolve, reject) =>
    file.end((error) => (error ? reject(error) : resolve())),
  )
  const encoder = spawn(
    ffmpeg,
    [
      // Input: the JPEG frames, one per tick
      ...['-y', '-loglevel', 'error', '-f', 'image2pipe', '-c:v', 'mjpeg'],
      ...['-framerate', `${FPS}`, '-i', stream, '-an'],
      // Output: VP8 by quality, a single keyframe, no frame allowed to go soft
      ...['-c:v', 'libvpx', '-pix_fmt', 'yuv420p', '-crf', '6', '-b:v', '4M'],
      ...['-qmin', '0', '-qmax', '24', '-deadline', 'good', '-cpu-used', '0'],
      ...['-g', '100000', '-auto-alt-ref', '1', '-lag-in-frames', '16', output],
    ],
    { stdio: 'inherit', windowsHide: true },
  )
  await new Promise((resolve, reject) => {
    encoder.on('error', reject)
    encoder.on('close', (code) =>
      code === 0 ? resolve() : reject(new Error(`ffmpeg exited ${code}`)),
    )
  })
  await rm(stream)
  return { ticks, captured: frames.length }
}

const pause = (page, ms) => page.waitForTimeout(ms)
// Scroll the visible tab's column to its end at a steady speed, so the whole content is seen.
async function scrollThrough(page, pixelsPerSecond = 110) {
  await page.evaluate(async (speed) => {
    const column = document.querySelector('.draft-column')
    const end = column.scrollHeight - column.clientHeight
    if (end <= 0) return
    const start = performance.now()
    await new Promise((resolve) => {
      const step = (now) => {
        column.scrollTop = Math.min(end, ((now - start) / 1000) * speed)
        if (column.scrollTop >= end) resolve()
        else requestAnimationFrame(step)
      }
      requestAnimationFrame(step)
    })
  }, pixelsPerSecond)
}

const directory = path.resolve('public/examples')
await mkdir(directory, { recursive: true })
const ffmpeg = await findFfmpeg()
const browser = await chromium.launch({
  channel: process.env.BROWSER_CHANNEL || 'msedge',
  headless: true,
})
try {
  for (const [scene, run] of scenes) {
    const page = await browser.newPage({ viewport: SIZE })
    await page.goto(
      `http://127.0.0.1:5173/tools/capture.html?run=${run}&scene=${scene}`,
    )
    await page.waitForSelector('body[data-capture-ready="true"]')
    await page.evaluate(() => document.fonts.ready)
    const stop = await startCapture(page)
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
      await pause(page, 600) // opens on the Research tab
      await page.screenshot({ path: path.join(directory, `${scene}.png`) })
      await pause(page, 2500)
      await scrollThrough(page)
      await pause(page, 2000)
      await page.getByRole('tab', { name: 'Approach' }).click()
      await pause(page, 5000)
    }
    const capture = await stop()
    await page.close()
    const { ticks, captured } = await encode(
      ffmpeg,
      capture,
      path.join(directory, `${scene}.webm`),
    )
    console.log(
      `Recorded ${scene} from ${run}: ${(ticks / FPS).toFixed(1)} s, ${captured} captured frames`,
    )
  }
} finally {
  await browser.close()
}
