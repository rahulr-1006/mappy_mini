export function ModelElementsPanel({ elements, onDelete, deletingId }) {
  return (
    <div className="panel">
      <h2>Model elements ({elements.length})</h2>

      {elements.length === 0 ? (
        <p className="empty-state">
          Nothing committed to the model yet. Keep a generated requirement to
          add it here.
        </p>
      ) : (
        <ul className="element-list">
          {elements.map((el) => (
            <li key={el.id} className="element-row">
              <div className="element-info">
                <div className="requirement-header">
                  <span className="badge badge-accent">{el.stereotype}</span>
                  {el.verifyMethod && <span className="badge">{el.verifyMethod}</span>}
                </div>
                <p className="requirement-name">{el.name}</p>
                <p className="requirement-text" title={el.text}>
                  {el.text}
                </p>
              </div>
              <button
                type="button"
                className="secondary"
                onClick={() => onDelete(el.id)}
                disabled={deletingId === el.id}
              >
                {deletingId === el.id ? 'Removing…' : 'Remove'}
              </button>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
