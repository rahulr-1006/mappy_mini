const PERCENT = (v) => `${Math.round((v ?? 0) * 100)}%`

export function TraceabilityPanel({
  coverage,
  traces,
  blocks,
  suggestions,
  suggesting,
  saving,
  onSuggest,
  onAcceptAll,
  onAcceptOne,
  onDismissOne,
  onDeleteTrace,
}) {
  const rows = coverage?.rows ?? []
  const orphans = coverage?.orphan_blocks ?? []
  const hasModel = rows.length > 0 && blocks.length > 0

  // requirement id -> block id -> kind, for the matrix cells
  const cellKind = {}
  for (const t of traces) {
    cellKind[`${t.requirement_id}|${t.block_id}`] = t.kind
  }
  const traceId = {}
  for (const t of traces) {
    traceId[`${t.requirement_id}|${t.block_id}`] = t.id
  }

  return (
    <>
      <div className="panel">
        <h2>Coverage</h2>
        {!hasModel ? (
          <p className="empty-state">
            Traceability needs both kept requirements and a saved diagram. Keep
            a few requirements, then generate and save a diagram for the same
            system.
          </p>
        ) : (
          <>
            <div className="stat-grid">
              <div className="stat-card">
                <div className="stat-value">{PERCENT(coverage?.coverage_rate)}</div>
                <div className="stat-label">Requirements satisfied</div>
                <div className="stat-hint">
                  {coverage?.requirements_covered} of {coverage?.requirements_total}
                </div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{coverage?.requirements_uncovered ?? 0}</div>
                <div className="stat-label">Unsatisfied</div>
                <div className="stat-hint">no design element fulfils these</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{orphans.length}</div>
                <div className="stat-label">Orphan blocks</div>
                <div className="stat-hint">satisfy no stated requirement</div>
              </div>
              <div className="stat-card">
                <div className="stat-value">{traces.length}</div>
                <div className="stat-label">Trace links</div>
              </div>
            </div>

            <div className="diagram-actions">
              <button type="button" onClick={onSuggest} disabled={suggesting}>
                {suggesting ? 'Analyzing…' : 'Suggest links'}
              </button>
            </div>
          </>
        )}
      </div>

      {suggestions.length > 0 && (
        <div className="panel">
          <div className="diagram-panel-heading">
            <h2>Proposed links ({suggestions.length})</h2>
            <button type="button" className="link-button" onClick={onAcceptAll} disabled={saving}>
              {saving ? 'Saving…' : 'Accept all'}
            </button>
          </div>
          <p className="empty-state">
            The model proposes; you decide. Nothing is written to the model
            until you accept it.
          </p>
          <ul className="requirement-list">
            {suggestions.map((s, i) => (
              <li key={i} className="requirement-card">
                <div className="requirement-header">
                  <span className="badge badge-accent">{s.kind}</span>
                  <span className="badge">{s.requirement_name}</span>
                  <span className="badge">{s.block_name}</span>
                </div>
                <p className="requirement-text">{s.rationale}</p>
                <div className="requirement-actions">
                  <button type="button" onClick={() => onAcceptOne(i)} disabled={saving}>
                    Accept
                  </button>
                  <button type="button" className="secondary" onClick={() => onDismissOne(i)}>
                    Dismiss
                  </button>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}

      {hasModel && (
        <div className="panel">
          <h2>Traceability matrix</h2>
          <p className="empty-state">
            Requirements down, design blocks across. Click a link to remove it.
          </p>
          <div className="table-scroll">
            <table className="eval-table matrix">
              <thead>
                <tr>
                  <th className="sticky-col">Requirement</th>
                  {blocks.map((b) => (
                    <th key={b.id} className="rot" title={b.name}>
                      {b.name}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rows.map((r) => (
                  <tr key={r.requirement_id}>
                    <td className="sticky-col" title={r.name}>
                      <span className={`dot ${r.covered ? 'dot-ok' : 'dot-gap'}`} />
                      {r.name}
                    </td>
                    {blocks.map((b) => {
                      const key = `${r.requirement_id}|${b.id}`
                      const kind = cellKind[key]
                      return (
                        <td key={b.id} className="cell">
                          {kind ? (
                            <button
                              type="button"
                              className="cell-link"
                              title={`${kind} — click to remove`}
                              onClick={() => onDeleteTrace(traceId[key])}
                            >
                              {kind === 'satisfy' ? '●' : '○'}
                            </button>
                          ) : (
                            <span className="cell-empty">·</span>
                          )}
                        </td>
                      )
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {orphans.length > 0 && (
        <div className="panel">
          <h2>Orphan blocks ({orphans.length})</h2>
          <p className="empty-state">
            Design elements that satisfy no stated requirement. Either a
            requirement is missing, or the element is unjustified scope.
          </p>
          <ul className="element-list">
            {orphans.map((b) => (
              <li key={b.id} className="element-row">
                <div className="element-info">
                  <p className="requirement-name">{b.name}</p>
                </div>
              </li>
            ))}
          </ul>
        </div>
      )}
    </>
  )
}
