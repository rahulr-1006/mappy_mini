export function ActivityLog({ entries }) {
  const ordered = [...entries].reverse()

  return (
    <div className="panel">
      <h2>Activity log</h2>

      {ordered.length === 0 ? (
        <p className="empty-state">Nothing has happened yet.</p>
      ) : (
        <ul className="log-list">
          {ordered.map((entry, i) => (
            <li key={i} className="log-entry">
              <span className="log-time">
                {new Date(entry.timestamp).toLocaleTimeString()}
              </span>
              <span className="log-message">{entry.message}</span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
