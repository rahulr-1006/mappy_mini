import { useState } from 'react'

const PROMPT_MAX_LENGTH = 4000

export function GenerationForm({
  title,
  placeholder,
  buttonLabel,
  models,
  defaultModel,
  busy,
  showSanityCheck = false,
  onGenerate,
}) {
  const [prompt, setPrompt] = useState('')
  const [model, setModel] = useState(defaultModel ?? '')
  const [runSanityCheck, setRunSanityCheck] = useState(true)

  const selectedModel = model || defaultModel || models[0] || ''
  const canSubmit = prompt.trim().length > 0 && selectedModel && !busy

  function handleSubmit(event) {
    event.preventDefault()
    if (!canSubmit) return
    const payload = { prompt: prompt.trim(), model: selectedModel }
    if (showSanityCheck) payload.run_sanity_check = runSanityCheck
    onGenerate(payload)
  }

  return (
    <form className="panel prompt-form" onSubmit={handleSubmit}>
      <h2>{title}</h2>
      <label htmlFor="prompt-input">Desired system</label>
      <textarea
        id="prompt-input"
        rows={8}
        maxLength={PROMPT_MAX_LENGTH}
        placeholder={placeholder}
        value={prompt}
        onChange={(e) => setPrompt(e.target.value)}
        disabled={busy}
      />
      <div className="char-count">
        {prompt.length}/{PROMPT_MAX_LENGTH}
      </div>

      <div className="form-row">
        <label htmlFor="model-select">Model</label>
        <select
          id="model-select"
          value={selectedModel}
          onChange={(e) => setModel(e.target.value)}
          disabled={busy || models.length === 0}
        >
          {models.length === 0 && <option value="">No models available</option>}
          {models.map((m) => (
            <option key={m} value={m}>
              {m}
            </option>
          ))}
        </select>

        {showSanityCheck && (
          <label className="checkbox-label">
            <input
              type="checkbox"
              checked={runSanityCheck}
              onChange={(e) => setRunSanityCheck(e.target.checked)}
              disabled={busy}
            />
            Run rule checks &amp; auto-repair
          </label>
        )}
      </div>

      <button type="submit" disabled={!canSubmit}>
        {busy ? 'Generating…' : buttonLabel}
      </button>
    </form>
  )
}
