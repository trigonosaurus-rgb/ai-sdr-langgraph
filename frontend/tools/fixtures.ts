import type { Brief, Draft, Source } from '../src/types'
import type { RunUsage } from '../src/run'
export const sampleUsage: RunUsage = {
  input: null,
  cachedInput: null,
  output: null,
  reasoning: null,
  modelUsd: null,
  searchUsd: null,
  durationSeconds: 12.4,
  model: 'Illustrative recording',
}
// Fictional material used ONLY by the development-only video recorder.
export const sampleBrief: Brief = {
  company: 'Northstar',
  website: 'https://northstar.example',
  recipient: 'Head of Customer Success',
  offer:
    'We build workflow automations that move customer context from sales to onboarding.',
  language: 'English',
  tone: 'Direct',
}
export const draft: Draft = {
  subject: 'A smoother handoff at Northstar',
  body: 'Northstar offers guided onboarding for new customers. We build automations that carry customer context from sales into onboarding, without re-entering it.\n\nAre there any manual steps in that handoff for your team today?',
}
export const sources: Source[] = [
  {
    id: 1,
    title: 'Built for growing teams',
    path: 'northstar.example / product',
    excerpt:
      'Northstar is a fictional project management platform for growing creative teams. Its shared workspace brings project planning, feedback and delivery together.',
  },
  {
    id: 2,
    title: 'A more personal start',
    path: 'northstar.example / customers',
    excerpt:
      'In this sample, Northstar offers guided onboarding for its business customers. Its customer success team helps new accounts set up their first workspace and workflows.',
  },
  {
    id: 3,
    title: 'Connecting the customer journey',
    path: 'northstar.example / integrations',
    excerpt:
      'The sample product connects with CRM and communication tools. These materials do not establish whether Northstar has manual handoff problems or how much time a proposed solution could save.',
  },
]
