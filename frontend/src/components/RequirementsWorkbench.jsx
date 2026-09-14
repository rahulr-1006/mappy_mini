import { useState } from 'react'

const STEREOTYPES = [
  'functionalRequirement',
  'performanceRequirement',
  'interfaceRequirement',
  'physicalRequirement',
  'designConstraint',
  'extendedRequirement',
]

const VERIFY_METHODS = ['Analysis', 'Demonstration', 'Inspection', 'Test']

const BLANK = {
  stereotype: 'functionalRequirement',
  name: '',
  text: '',
  verifyMethod: 'Test',
}

function RequirementEditor({ value, busy, onChange, onSave, onCancel, saveLabel }) {
  return (
    <div className="requirement-editor">
      <div className="editor-row">
        <label>
          Stereotype
          <select
            value={value.stereotype}
            onChange={(e) => onChange({ ...value, stereotype: e.target.value })}
          >
            {STEREOTYPES.map((s) => (
              <option key={s} value={s}>
                {s}
              </option>
            ))}
          </select>
        </label>
        <label>
          Verified by
          <select
            value={value.verifyMethod}
            onChange={(e) => onChange({ ...value, verifyMethod: e.target.value })}
          >
            {VERIFY_METHODS.map((v) => (
              <option key={v} value={v}>
                {v}
              </option>
            ))}
          </select>
        </label>
      </div>

      <label>
        Name
        <input
          type="text"
          value={value.name}
          placeholder="Short summary, with spaces"
          onChange={(e) => onChange({ ...value, name: e.target.value })}
        />
      </label>

      <label>
        Requirement text
        <textarea
          rows={5}
          value={value.text}
          placeholder="The system shall…"
          onChange={(e) => onChange({ ...value, text: e.target.value })}
        />
        <span className="field-hint">
          {value.text.trim() ? value.text.trim().split(/\s+/).length : 0} words —
          the checker needs 40 or more
        </span>
      </label>

      <div className="requirement-actions">
        <button type="button" onClick={onSave} disabled={busy || !value.text.trim()}>
          {busy ? 'Saving…' : saveLabel}
        </button>
        <button type="button" className="secondary" onClick={onCancel} disabled={busy}>
          Cancel
        </button>
      </div>
    </div>
  )
}

export function RequirementsWorkbench({
  elements,
  busyId,
  adding,
  onUpdate,
  onCreate,
  onDelete,
}) {
  const [editingId, setEditingId] = useState(null)
  const [draft, setDraft] = useState(BLANK)
  const [newDraft, setNewDraft] = useState(null)

  const failing = elements.filter((e) => e.violations?.length > 0).length

  function startEdit(el) {
    setNewDraft(null)
    setEditingId(el.id)
    setDraft({
      stereotype: el.stereotype,
      name: el.name,
      text: el.text,
      verifyMethod: el.verifyMethod,
    })
  }

  async function saveEdit() {
    await onUpdate(editingId, draft)
    setEditingId(null)
  }

  async function saveNew() {
    await onCreate(newDraft)
    setNewDraft(null)
  }

  return (
    <div className="panel">
      <div className="diagram-panel-heading">
        <div>
          <h2>Requirements ({elements.length})</h2>
          <p className="panel-subtitle">
            Everything kept from the conversation. Edit any of them by hand —
            the rule check runs again on save.
          </p>
        </div>
        <button
          type="button"
          onClick={() => {
            setEditingId(null)
            setNewDraft(BLANK)
          }}
          disabled={Boolean(newDraft)}
        >
          Add by hand
        </button>
      </div>

      {elements.length > 0 && (
        <p className={failing ? 'status-line status-warn' : 'status-line'}>
          {failing === 0
            ? `${elements.length} requirement(s), all passing the rule check.`
            : `${failing} of ${elements.length} requirement(s) break a rule.`}
        </p>
      )}

      {newDraft && (
        <div className="requirement-card">
          <p className="requirement-name">New requirement</p>
          <RequirementEditor
            value={newDraft}
            busy={adding}
            onChange={setNewDraft}
            onSave={saveNew}
            onCancel={() => setNewDraft(null)}
            saveLabel="Add to model"
          />
        </div>
      )}

      {elements.length === 0 && !newDraft ? (
        <p className="empty-state">
          No requirements yet. Describe your system in Chat and keep the ones
          worth having, or add one by hand.
        </p>
      ) : (
        <ul className="requirement-list">
          {elements.map((el) => (
            <li key={el.id} className="requirement-card">
              {editingId === el.id ? (
                <RequirementEditor
                  value={draft}
                  busy={busyId === el.id}
                  onChange={setDraft}
                  onSave={saveEdit}
                  onCancel={() => setEditingId(null)}
                  saveLabel="Save changes"
                />
              ) : (
                <>
                  <div className="requirement-header">
                    <span className="badge badge-accent">{el.stereotype}</span>
                    <span className="badge">{el.verifyMethod}</span>
                    {el.violations?.length > 0 && (
                      <span className="badge badge-fail">breaks the rule check</span>
                    )}
                    {el.advisories?.length > 0 && (
                      <span className="badge badge-advisory">needs a human call</span>
                    )}
                  </div>
                  <p className="requirement-name">{el.name}</p>
                  <p className="requirement-text">{el.text}</p>
                  {el.violations?.length > 0 && (
                    <ul className="violation-list">
                      {el.violations.map((v, i) => (
                        <li key={i}>{v}</li>
                      ))}
                    </ul>
                  )}
                  {el.advisories?.length > 0 && (
                    <ul className="advisory-list">
                      {el.advisories.map((a, i) => (
                        <li key={i}>{a}</li>
                      ))}
                    </ul>
                  )}
                  <div className="requirement-actions">
                    <button type="button" onClick={() => startEdit(el)}>
                      Edit
                    </button>
                    <button
                      type="button"
                      className="secondary"
                      onClick={() => onDelete(el.id)}
                      disabled={busyId === el.id}
                    >
                      {busyId === el.id ? 'Removing…' : 'Delete'}
                    </button>
                  </div>
                </>
              )}
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
