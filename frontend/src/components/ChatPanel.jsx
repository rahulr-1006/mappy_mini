import { useEffect, useRef, useState } from 'react'

export function ChatPanel({ messages, busy, keepingKey, onSend, onKeep, onClear }) {
  const [draft, setDraft] = useState('')
  const endRef = useRef(null)

  useEffect(() => {
    endRef.current?.scrollIntoView({ behavior: 'smooth', block: 'end' })
  }, [messages.length, busy])

  function submit(event) {
    event.preventDefault()
    const text = draft.trim()
    if (!text || busy) return
    setDraft('')
    onSend(text)
  }

  return (
    <div className="panel chat-panel">
      <div className="diagram-panel-heading">
        <h2>Chat</h2>
        {messages.length > 0 && (
          <button type="button" className="link-button" onClick={onClear}>
            Clear thread
          </button>
        )}
      </div>

      <div className="chat-thread">
        {messages.length === 0 && (
          <p className="empty-state">
            Describe a system. The assistant searches the knowledge base
            first, asks about whatever is still undetermined, and writes
            requirements once it has enough to work from, rather than
            inventing them.
          </p>
        )}

        {messages.map((m) => (
          <div key={m.id} className={`chat-msg chat-${m.role}`}>
            <div className="chat-bubble">{m.content}</div>

            {m.sources?.length > 0 && (
              <details className="chat-sources">
                <summary>
                  Grounded in {m.sources.length} retrieved passage(s)
                </summary>
                <ul>
                  {m.sources.map((s, i) => (
                    <li key={i}>
                      <span className={s.kind === 'model' ? 'badge badge-accent' : 'badge'}>
                        {s.kind === 'model' ? 'model' : 'document'}
                      </span>
                      <span className="source-name">{s.name}</span>
                      <span className="source-score">{s.score}</span>
                    </li>
                  ))}
                </ul>
              </details>
            )}

            {m.requirements?.length > 0 && (
              <ul className="requirement-list chat-reqs">
                {m.requirements.map((r, i) => {
                  const key = `${m.id}-${i}`
                  return (
                    <li key={key} className="requirement-card">
                      <div className="requirement-header">
                        <span className="badge badge-accent">{r.stereotype}</span>
                        <span className="badge">{r.verifyMethod}</span>
                        {r.reprompts > 0 && r.violations?.length === 0 && (
                          <span className="badge badge-warn">
                            repaired ×{r.reprompts}
                          </span>
                        )}
                        {r.advisories?.length > 0 && (
                          <span className="badge badge-advisory">needs a human call</span>
                        )}
                        {r.violations?.length > 0 && (
                          <span className="badge badge-fail">
                            {r.reprompts > 0
                              ? `still failing after ${r.reprompts} attempt(s)`
                              : 'fails rule check'}
                          </span>
                        )}
                      </div>
                      <p className="requirement-name">{r.name}</p>
                      <p className="requirement-text">{r.text}</p>
                      {r.violations?.length > 0 && (
                        <ul className="violation-list">
                          {r.violations.map((v, j) => (
                            <li key={j}>{v}</li>
                          ))}
                        </ul>
                      )}
                      {r.advisories?.length > 0 && (
                        <ul className="advisory-list">
                          {r.advisories.map((a, j) => (
                            <li key={j}>{a}</li>
                          ))}
                        </ul>
                      )}
                      <div className="requirement-actions">
                        <button
                          type="button"
                          onClick={() => onKeep(r, key)}
                          disabled={keepingKey === key}
                        >
                          {keepingKey === key ? 'Keeping…' : 'Keep'}
                        </button>
                      </div>
                    </li>
                  )
                })}
              </ul>
            )}
          </div>
        ))}

        {busy && <div className="chat-msg chat-assistant"><div className="chat-bubble chat-thinking">Thinking…</div></div>}
        <div ref={endRef} />
      </div>

      <form className="chat-input" onSubmit={submit}>
        <textarea
          id="chat-draft"
          rows={2}
          placeholder="Describe the system, answer a question, or ask for a fix"
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter' && !e.shiftKey) submit(e)
          }}
          disabled={busy}
        />
        <button type="submit" disabled={busy || !draft.trim()}>
          Send
        </button>
      </form>

      <p className="chat-disclaimer">
        Generated requirements can be wrong. Every one is checked against the
        INCOSE rules, but review them before keeping.
      </p>
    </div>
  )
}
