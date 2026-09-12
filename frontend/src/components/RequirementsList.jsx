export function RequirementsList({ requirements, log, keepingKey, onKeep, onDiscard }) {
  return (
    <div className="panel">
      <h2>Generated requirements</h2>

      {requirements.length === 0 ? (
        <p className="empty-state">
          No requirements yet — describe a system and click Generate.
        </p>
      ) : (
        <ul className="requirement-list">
          {requirements.map((req, index) => {
            const key = `${req.name}-${index}`
            return (
              <li key={key} className="requirement-card">
                <div className="requirement-header">
                  <span className="badge badge-accent">{req.stereotype}</span>
                  <span className="badge">{req.verifyMethod}</span>
                  {req.reprompts > 0 && (
                    <span className="badge badge-warn">
                      repaired ×{req.reprompts}
                    </span>
                  )}
                </div>
                <p className="requirement-name">{req.name}</p>
                <p className="requirement-text">{req.text}</p>
                <div className="requirement-actions">
                  <button type="button" onClick={() => onKeep(req, index)} disabled={keepingKey === key}>
                    {keepingKey === key ? 'Keeping…' : 'Keep'}
                  </button>
                  <button type="button" className="secondary" onClick={() => onDiscard(index)}>
                    Discard
                  </button>
                </div>
              </li>
            )
          })}
        </ul>
      )}

      {log.length > 0 && (
        <details className="generation-log">
          <summary>Generation log ({log.length})</summary>
          <ul>
            {log.map((line, i) => (
              <li key={i}>{line}</li>
            ))}
          </ul>
        </details>
      )}
    </div>
  )
}
