import { useRef, useState } from 'react'

export function KnowledgePanel({
  documents,
  index,
  busy,
  onUpload,
  onSeed,
  onDelete,
  onReindex,
  onSearch,
}) {
  const fileRef = useRef(null)
  const [query, setQuery] = useState('')
  const [results, setResults] = useState(null)
  const [searching, setSearching] = useState(false)

  async function runSearch(event) {
    event.preventDefault()
    if (!query.trim() || searching) return
    setSearching(true)
    try {
      setResults(await onSearch(query.trim()))
    } finally {
      setSearching(false)
    }
  }

  const embedded = index?.embedded_chunks ?? 0
  const total = index?.total_chunks ?? 0
  const lexicalOnly = total > 0 && embedded < total

  return (
    <div className="panel">
      <div className="diagram-panel-heading">
        <div>
          <h2>Knowledge base</h2>
          <p className="panel-subtitle">
            What the assistant retrieves from before answering: the documents
            you load, and the model being built.
          </p>
        </div>
      </div>

      <div className="index-stats">
        <div className="stat">
          <span className="stat-value">{index?.documents ?? 0}</span>
          <span className="stat-label">documents</span>
        </div>
        <div className="stat">
          <span className="stat-value">{index?.document_chunks ?? 0}</span>
          <span className="stat-label">document chunks</span>
        </div>
        <div className="stat">
          <span className="stat-value">{index?.model_chunks ?? 0}</span>
          <span className="stat-label">model chunks</span>
        </div>
        <div className="stat">
          <span className="stat-value">{embedded}</span>
          <span className="stat-label">embedded</span>
        </div>
      </div>

      {lexicalOnly && (
        <p className="status-line status-warn">
          {total - embedded} chunk(s) have no embedding, so retrieval falls back
          to keyword matching for them. Start Ollama and press Rebuild index.
        </p>
      )}

      <div className="requirement-actions knowledge-actions">
        <button type="button" onClick={() => fileRef.current?.click()} disabled={busy}>
          Upload a document
        </button>
        <input
          ref={fileRef}
          type="file"
          accept=".txt,.md,.markdown,.csv,.json"
          style={{ display: 'none' }}
          onChange={(e) => {
            const file = e.target.files?.[0]
            if (file) onUpload(file)
            e.target.value = ''
          }}
        />
        <button type="button" className="secondary" onClick={onSeed} disabled={busy}>
          Load reference corpus
        </button>
        <button type="button" className="secondary" onClick={onReindex} disabled={busy}>
          Rebuild index
        </button>
      </div>

      {documents.length === 0 ? (
        <p className="empty-state">
          No documents loaded. Load the reference corpus to see grounded
          retrieval, or upload your own .txt / .md files.
        </p>
      ) : (
        <ul className="element-list">
          {documents.map((doc) => (
            <li key={doc.id} className="element-row">
              <div className="element-info">
                <div className="requirement-header">
                  <span className="badge badge-accent">{doc.origin}</span>
                  <span className="badge">{doc.chunks} chunks</span>
                  <span className="badge">{doc.word_count} words</span>
                </div>
                <p className="requirement-name">{doc.name}</p>
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() => onDelete(doc.id)}
                disabled={busy}
              >
                Remove
              </button>
            </li>
          ))}
        </ul>
      )}

      <form className="knowledge-search" onSubmit={runSearch}>
        <h3>Try a retrieval</h3>
        <p className="panel-subtitle">
          The same search the assistant runs before every answer, shown on its
          own so you can see what it found and what it scored.
        </p>
        <div className="chat-input">
          <input
            type="text"
            value={query}
            placeholder="e.g. how is backup power provided during an outage"
            onChange={(e) => setQuery(e.target.value)}
          />
          <button type="submit" disabled={searching || !query.trim()}>
            {searching ? 'Searching…' : 'Search'}
          </button>
        </div>
      </form>

      {results && (
        <div className="search-results">
          <p className="status-line">
            {results.results.length} result(s) by {results.method} search.
          </p>
          <ul className="requirement-list">
            {results.results.map((r, i) => (
              <li key={i} className="requirement-card">
                <div className="requirement-header">
                  <span
                    className={
                      r.source_kind === 'model' ? 'badge badge-accent' : 'badge'
                    }
                  >
                    {r.source_kind === 'model' ? 'from the model' : r.source_name}
                  </span>
                  <span className="badge badge-warn">{r.score.toFixed(3)}</span>
                </div>
                <p className="requirement-text">{r.text}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  )
}
