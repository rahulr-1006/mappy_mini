import { useEffect, useState } from 'react'
import { api } from './api'
import { BlockDiagram } from './components/BlockDiagram'
import './App.css'

export function DiagramPage() {
  const [diagram, setDiagram] = useState({ blocks: [], connectors: [] })
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  useEffect(() => {
    async function loadDiagram() {
      try {
        setDiagram(await api.getDiagram())
      } catch (err) {
        setError(err.message)
      } finally {
        setLoading(false)
      }
    }
    loadDiagram()
  }, [])

  async function handleRefresh() {
    setLoading(true)
    setError(null)
    try {
      setDiagram(await api.getDiagram())
    } catch (err) {
      setError(err.message)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div className="diagram-page">
      <header className="diagram-page-header">
        <div>
          <h1>Mini-MAPPy — System Diagram</h1>
          <p>Showing the diagram currently saved to the model.</p>
        </div>
        <button type="button" onClick={handleRefresh} disabled={loading}>
          {loading ? 'Refreshing…' : 'Refresh'}
        </button>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          {error}
        </div>
      )}

      {!loading && diagram.blocks.length === 0 ? (
        <p className="empty-state">
          No diagram has been saved yet. Go back to the main app, generate a
          diagram, click "Save to model," then refresh this page.
        </p>
      ) : (
        <div className="diagram-page-canvas">
          <BlockDiagram blocks={diagram.blocks} connectors={diagram.connectors} />
        </div>
      )}
    </div>
  )
}
