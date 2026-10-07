export type Language = 'English' | 'Russian'
export type Tone = 'Direct' | 'Warm'
export type ResultTab = 'email' | 'research' | 'strategy'

export interface Brief {
  company: string
  website: string
  offer: string
  recipient: string
  language: Language
  tone: Tone
}

export interface Draft {
  subject: string
  body: string
}

// One verified fact: the claim, and a verbatim excerpt from the page it came from.
export interface Source {
  id: number
  claim: string
  title: string
  url: string
  path: string // short display form of url
  excerpt: string
}

export interface Strategy {
  observation: string
  factIds: number[] // Source ids the observation rests on
  offerLink: string
  hypotheses: string[] // unconfirmed assumptions, never shown as facts
  angle: string
  offerFit: 'good' | 'weak' | 'poor'
  fitReason: string
}

export interface Review {
  attempt: number
  passed: boolean
  issues: string[]
}
