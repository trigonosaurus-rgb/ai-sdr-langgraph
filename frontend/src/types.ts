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

export interface Source {
  id: number
  title: string
  path: string
  excerpt: string
}
