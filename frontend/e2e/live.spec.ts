import { expect, test } from '@playwright/test'
import type { Page } from '@playwright/test'

// Runs against tests/fake_server.py: the company name picks the scenario.
async function fillBrief(page: Page, company: string) {
  await page.getByLabel('Company name').fill(company)
  await page.getByLabel('Company website').fill('acme.com')
  await page.getByLabel('Recipient role').fill('VP of Engineering')
  await page.getByLabel('Your offer').fill('Contract data engineers')
}
const rail = (page: Page) => page.getByRole('region', { name: 'Run' })
const generate = (page: Page) =>
  page.getByRole('button', { name: 'Generate outreach' })

test('a run streams stages and the draft, then ends ready for review', async ({
  page,
}) => {
  await page.goto('/')
  await fillBrief(page, 'Acme')
  await generate(page).click()
  await expect(rail(page).getByText('In progress')).toBeVisible()
  // The body is streamed: it is visible before the run is complete.
  await expect(page.getByLabel('Email body')).toContainText('Acme is hiring')
  await expect(rail(page).getByText('Ready for review')).toBeVisible({
    timeout: 15_000,
  })
  await expect(page.getByLabel('Subject')).toHaveValue(
    'Staffing the Warsaw analytics team',
  )
  await expect(page.getByLabel('Email body')).toHaveValue(
    /Worth a short call next week\?$/,
  )
  await page.getByRole('tab', { name: /Research/ }).click()
  await expect(page.getByText('About Acme')).toBeVisible()
  // The finished result survives a reload.
  await page.reload()
  await expect(rail(page).getByText('Ready for review')).toBeVisible()
  await expect(page.getByLabel('Company name')).toHaveValue('Acme')
})

test('run costs show the finished run by step and the visitor’s period', async ({
  page,
}) => {
  await page.goto('/')
  await fillBrief(page, 'Acme')
  await generate(page).click()
  await expect(rail(page).getByText('Ready for review')).toBeVisible({
    timeout: 15_000,
  })
  // Four fake LLM calls (100 in, 20 cached, 50 out) and three one-credit searches at fake prices.
  await expect(rail(page).getByText('$0.0251')).toBeVisible()
  await rail(page).getByRole('button', { name: 'Usage details' }).click()
  const dialog = page.getByRole('dialog', { name: 'Run costs' })
  await expect(dialog).toContainText('Usage for this run.')
  const steps = dialog.getByRole('table', { name: 'By step' })
  await expect(steps.getByRole('row')).toHaveCount(6)
  await expect(steps).toContainText('Web search, 3 requests')
  await expect(dialog.locator('.metric').first()).toContainText('$0.0251')
  await dialog.getByRole('radio', { name: '24 hours' }).click()
  await expect(dialog).toContainText('from your address over the last 24 hours')
  await expect(dialog).toContainText('Service budget today')
})

test('reloading mid-run resumes the same run', async ({ page }) => {
  await page.goto('/')
  await fillBrief(page, 'Slowco')
  await generate(page).click()
  await expect(rail(page).getByText('In progress')).toBeVisible()
  await page.reload()
  await expect(page.getByLabel('Company name')).toHaveValue('Slowco')
  await expect(page.getByLabel('Company name')).toBeDisabled()
  await expect(rail(page).getByText('Ready for review')).toBeVisible({
    timeout: 20_000,
  })
  await expect(page.getByLabel('Subject')).toHaveValue(
    'Staffing the Warsaw analytics team',
  )
})

test('cancel is confirmed by the server and nothing is finished', async ({
  page,
}) => {
  await page.goto('/')
  await fillBrief(page, 'Slowco')
  await generate(page).click()
  await page.getByRole('button', { name: 'Cancel run' }).click()
  await expect(rail(page).getByText('Cancelled')).toBeVisible({
    timeout: 15_000,
  })
  await expect(page.getByRole('alert')).toContainText('The run was cancelled')
  await expect(generate(page)).toBeEnabled()
})

test('a failed step is reported, not shown as a result', async ({ page }) => {
  await page.goto('/')
  await fillBrief(page, 'Brokenco')
  await generate(page).click()
  await expect(rail(page).getByText('Failed')).toBeVisible({ timeout: 15_000 })
  await expect(page.getByRole('alert')).toContainText(
    'The Research step failed',
  )
  await expect(page.getByRole('button', { name: 'Copy email' })).toHaveCount(0)
})

test('an invalid brief is not sent', async ({ page }) => {
  const posts: string[] = []
  page.on('request', (request) => {
    if (request.method() === 'POST') posts.push(request.url())
  })
  await page.goto('/')
  await expect(generate(page)).toBeEnabled()
  await page.getByLabel('Company name').fill('Acme')
  await page.getByLabel('Company website').fill('not a site')
  await generate(page).click()
  await expect(page.getByText('Use a domain or URL')).toBeVisible()
  await expect(page.getByText('Enter the recipient role.')).toBeVisible()
  expect(posts).toEqual([])
})

test('generation is off while the service is unreachable', async ({ page }) => {
  await page.route('**/api/health', (route) => route.abort())
  await page.goto('/')
  await expect(
    page.getByText('The service is unavailable, so generation is off.'),
  ).toBeVisible()
  await expect(generate(page)).toBeDisabled()
})
