import { readdir } from 'node:fs/promises'
import { spawnSync } from 'node:child_process'
import path from 'node:path'

export async function trimRecording(browser, input, url, output) {
  const page = await browser.newPage()
  let start
  try {
    await page.goto('http://127.0.0.1:5173/')
    start = await page.evaluate(async (src) => {
      const video = document.createElement('video')
      video.muted = true
      video.src = src
      await new Promise((resolve, reject) => {
        video.onloadeddata = resolve
        video.onerror = reject
      })
      const canvas = document.createElement('canvas')
      canvas.width = canvas.height = 1
      const ctx = canvas.getContext('2d')
      const contentAt = async (time) => {
        video.currentTime = Math.max(0.001, time)
        await new Promise((resolve) => {
          video.onseeked = resolve
        })
        ctx.drawImage(video, 0, 0, 1, 1, 0, 0, 1, 1)
        return ctx.getImageData(0, 0, 1, 1).data[0] < 160
      }
      let low = 0,
        high = video.duration - 0.1
      if (!(await contentAt(high)))
        throw new Error('Recording did not render the dark capture scene')
      if (await contentAt(0)) return 0
      while (high - low > 0.025) {
        const middle = (low + high) / 2
        if (await contentAt(middle)) high = middle
        else low = middle
      }
      return high + 0.04
    }, url)
  } finally {
    await page.close()
  }
  // Playwright's bundled ffmpeg supports VP8. Use FFMPEG_PATH on other platforms.
  let ffmpeg = process.env.FFMPEG_PATH
  if (!ffmpeg) {
    const cache = path.join(process.env.LOCALAPPDATA, 'ms-playwright')
    const folder = (await readdir(cache))
      .filter((name) => name.startsWith('ffmpeg-'))
      .sort()
      .at(-1)
    if (!folder) throw new Error('Run: npx playwright install ffmpeg')
    ffmpeg = path.join(cache, folder, 'ffmpeg-win64.exe')
  }
  const result = spawnSync(
    ffmpeg,
    [
      '-y',
      '-ss',
      start.toFixed(3),
      '-i',
      input,
      '-an',
      '-c:v',
      'libvpx',
      '-b:v',
      '1000k',
      output,
    ],
    { encoding: 'utf8', windowsHide: true },
  )
  if (result.status !== 0)
    throw new Error(result.stderr || String(result.error))
  console.log(
    `Trimmed ${start.toFixed(2)}s of browser startup from ${path.basename(output)}`,
  )
}
