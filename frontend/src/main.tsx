import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import { captureDeveloperKey } from './api'
import './styles.css'

captureDeveloperKey()

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
