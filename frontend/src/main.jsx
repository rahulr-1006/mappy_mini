import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import './index.css'
import App from './App.jsx'
import { DiagramPage } from './DiagramPage.jsx'

const isDiagramPage = window.location.pathname === '/diagram-view'
if (isDiagramPage) document.body.classList.add('diagram-page-body')

createRoot(document.getElementById('root')).render(
  <StrictMode>
    {isDiagramPage ? <DiagramPage /> : <App />}
  </StrictMode>,
)
