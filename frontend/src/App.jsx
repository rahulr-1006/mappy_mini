import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ActivityLog } from './components/ActivityLog'
import { BlockDiagram } from './components/BlockDiagram'
import { ChatPanel } from './components/ChatPanel'
import { EvaluationsPanel } from './components/EvaluationsPanel'
import { GenerationForm } from './components/GenerationForm'
import { ModelElementsPanel } from './components/ModelElementsPanel'
import { RequirementsList } from './components/RequirementsList'
import { TraceabilityPanel } from './components/TraceabilityPanel'
import './App.css'

function App() {
  const [tab, setTab] = useState('requirements')

  const [models, setModels] = useState([])
  const [defaultModel, setDefaultModel] = useState('')
  const [modelElements, setModelElements] = useState([])
  const [activityLog, setActivityLog] = useState([])

  const [draftRequirements, setDraftRequirements] = useState([])
  const [generationLog, setGenerationLog] = useState([])
  const [generating, setGenerating] = useState(false)
  const [keepingKey, setKeepingKey] = useState(null)
  const [deletingId, setDeletingId] = useState(null)

  const [draftDiagram, setDraftDiagram] = useState({ blocks: [], connectors: [] })
  const [diagramLog, setDiagramLog] = useState([])
  const [savedDiagram, setSavedDiagram] = useState({ blocks: [], connectors: [] })
  const [diagramPrompt, setDiagramPrompt] = useState('')
  const [generatingDiagram, setGeneratingDiagram] = useState(false)
  const [savingDiagram, setSavingDiagram] = useState(false)

  const [evaluations, setEvaluations] = useState({ records: [], summary: null })
  const [runningSuite, setRunningSuite] = useState(false)
  const [judgeResult, setJudgeResult] = useState(null)
  const [judging, setJudging] = useState(false)

  const [chatMessages, setChatMessages] = useState([])
  const [chatBusy, setChatBusy] = useState(false)
  const [chatKeepingKey, setChatKeepingKey] = useState(null)

  const [coverage, setCoverage] = useState(null)
  const [traces, setTraces] = useState([])
  const [suggestions, setSuggestions] = useState([])
  const [suggesting, setSuggesting] = useState(false)
  const [savingTraces, setSavingTraces] = useState(false)

  const [error, setError] = useState(null)

  const refreshElements = useCallback(async () => {
    setModelElements(await api.listModelElements())
  }, [])

  const refreshLog = useCallback(async () => {
    setActivityLog(await api.getActivityLog())
  }, [])

  const refreshDiagram = useCallback(async () => {
    setSavedDiagram(await api.getDiagram())
  }, [])

  const refreshEvaluations = useCallback(async () => {
    setEvaluations(await api.getEvaluations())
  }, [])

  const refreshChat = useCallback(async () => {
    setChatMessages(await api.getChat())
  }, [])

  const refreshTraces = useCallback(async () => {
    const [cov, links] = await Promise.all([api.getCoverage(), api.getTraces()])
    setCoverage(cov)
    setTraces(links)
  }, [])

  useEffect(() => {
    async function loadInitial() {
      try {
        const [modelsRes] = await Promise.all([
          api.getModels(),
          refreshElements(),
          refreshLog(),
          refreshDiagram(),
          refreshEvaluations(),
          refreshTraces(),
          refreshChat(),
        ])
        setModels(modelsRes.models)
        setDefaultModel(modelsRes.default)
      } catch (err) {
        setError(err.message)
      }
    }
    loadInitial()
  }, [refreshElements, refreshLog, refreshDiagram, refreshEvaluations, refreshTraces, refreshChat])

  async function handleGenerate(payload) {
    setGenerating(true)
    setError(null)
    try {
      const res = await api.generateRequirements(payload)
      setDraftRequirements(res.requirements)
      setGenerationLog(res.log)
      await Promise.all([refreshLog(), refreshEvaluations()])
    } catch (err) {
      setError(err.message)
    } finally {
      setGenerating(false)
    }
  }

  async function handleKeep(requirement, index) {
    const key = `${requirement.name}-${index}`
    setKeepingKey(key)
    setError(null)
    try {
      await api.createModelElements([
        {
          stereotype: requirement.stereotype,
          name: requirement.name,
          text: requirement.text,
          verifyMethod: requirement.verifyMethod,
        },
      ])
      setDraftRequirements((prev) => prev.filter((_, i) => i !== index))
      await Promise.all([refreshElements(), refreshLog(), refreshTraces()])
    } catch (err) {
      setError(err.message)
    } finally {
      setKeepingKey(null)
    }
  }

  function handleDiscard(index) {
    setDraftRequirements((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleDelete(id) {
    setDeletingId(id)
    setError(null)
    try {
      await api.deleteModelElement(id)
      await Promise.all([refreshElements(), refreshLog(), refreshTraces()])
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  async function handleGenerateDiagram(payload) {
    setGeneratingDiagram(true)
    setError(null)
    try {
      const res = await api.generateDiagram(payload)
      setDraftDiagram({ blocks: res.blocks, connectors: res.connectors })
      setDiagramPrompt(payload.prompt)
      setDiagramLog(res.log)
      await Promise.all([refreshLog(), refreshEvaluations()])
    } catch (err) {
      setError(err.message)
    } finally {
      setGeneratingDiagram(false)
    }
  }

  async function handleSaveDiagram() {
    setSavingDiagram(true)
    setError(null)
    try {
      await api.saveDiagram(draftDiagram.blocks, draftDiagram.connectors, diagramPrompt)
      await Promise.all([refreshDiagram(), refreshLog(), refreshTraces()])
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingDiagram(false)
    }
  }

  async function handleRunSuite() {
    setRunningSuite(true)
    setError(null)
    try {
      await api.runEvaluationSuite(defaultModel || models[0])
      await Promise.all([refreshEvaluations(), refreshLog()])
    } catch (err) {
      setError(err.message)
    } finally {
      setRunningSuite(false)
    }
  }

  async function handleJudge() {
    setJudging(true)
    setError(null)
    try {
      setJudgeResult(await api.judgeRequirements(defaultModel || models[0]))
      await Promise.all([refreshLog(), refreshEvaluations()])
    } catch (err) {
      setError(err.message)
    } finally {
      setJudging(false)
    }
  }

  async function handleSendChat(message) {
    setChatBusy(true)
    setError(null)
    try {
      const res = await api.sendChat(message, defaultModel || models[0])
      setChatMessages(res.messages)
      await Promise.all([refreshLog(), refreshEvaluations()])
    } catch (err) {
      setError(err.message)
    } finally {
      setChatBusy(false)
    }
  }

  async function handleKeepFromChat(requirement, key) {
    setChatKeepingKey(key)
    setError(null)
    try {
      await api.createModelElements([
        {
          stereotype: requirement.stereotype,
          name: requirement.name,
          text: requirement.text,
          verifyMethod: requirement.verifyMethod,
        },
      ])
      await Promise.all([refreshElements(), refreshLog(), refreshTraces()])
    } catch (err) {
      setError(err.message)
    } finally {
      setChatKeepingKey(null)
    }
  }

  async function handleClearChat() {
    setError(null)
    try {
      await api.clearChat()
      await Promise.all([refreshChat(), refreshLog()])
    } catch (err) {
      setError(err.message)
    }
  }

  function withNames(links) {
    const reqName = Object.fromEntries(modelElements.map((r) => [r.id, r.name]))
    const blockName = Object.fromEntries(savedDiagram.blocks.map((b) => [b.id, b.name]))
    return links.map((l) => ({
      ...l,
      requirement_name: reqName[l.requirement_id] ?? l.requirement_id,
      block_name: blockName[l.block_id] ?? l.block_id,
    }))
  }

  async function handleSuggestTraces() {
    setSuggesting(true)
    setError(null)
    try {
      const res = await api.suggestTraces(defaultModel || models[0])
      setSuggestions(withNames(res.suggestions))
      await Promise.all([refreshLog(), refreshEvaluations()])
    } catch (err) {
      setError(err.message)
    } finally {
      setSuggesting(false)
    }
  }

  async function saveTraces(links) {
    setSavingTraces(true)
    setError(null)
    try {
      await api.createTraces(
        links.map(({ requirement_id, block_id, kind, rationale }) => ({
          requirement_id,
          block_id,
          kind,
          rationale,
        })),
      )
      await Promise.all([refreshTraces(), refreshLog()])
    } catch (err) {
      setError(err.message)
    } finally {
      setSavingTraces(false)
    }
  }

  async function handleAcceptAllTraces() {
    await saveTraces(suggestions)
    setSuggestions([])
  }

  async function handleAcceptTrace(index) {
    await saveTraces([suggestions[index]])
    setSuggestions((prev) => prev.filter((_, i) => i !== index))
  }

  function handleDismissTrace(index) {
    setSuggestions((prev) => prev.filter((_, i) => i !== index))
  }

  async function handleDeleteTrace(id) {
    setError(null)
    try {
      await api.deleteTrace(id)
      await Promise.all([refreshTraces(), refreshLog()])
    } catch (err) {
      setError(err.message)
    }
  }

  async function handleRegenerateDiagram() {
    const prompt = savedDiagram.prompt || diagramPrompt
    if (!prompt) return
    await handleGenerateDiagram({
      prompt,
      model: defaultModel || models[0],
    })
  }

  function openFullDiagramView() {
    window.open('/diagram-view', '_blank', 'noopener')
  }

  async function handleClearDiagram() {
    setError(null)
    try {
      await api.clearDiagram()
      await Promise.all([refreshDiagram(), refreshLog(), refreshTraces()])
    } catch (err) {
      setError(err.message)
    }
  }

  return (
    <div className="app-shell">
      <header className="app-header">
        <h1>Mini-MAPPy</h1>
        <p>AI-assisted MBSE requirements and block diagrams, checked against INCOSE and SysML rules.</p>
      </header>

      {error && (
        <div className="error-banner" role="alert">
          {error}
          <button type="button" onClick={() => setError(null)}>
            ×
          </button>
        </div>
      )}

      <div className="layout">
        <div className="column">
          <div className="tab-bar">
            <button
              type="button"
              className={tab === 'requirements' ? 'active' : ''}
              onClick={() => setTab('requirements')}
            >
              Requirements
            </button>
            <button
              type="button"
              className={tab === 'chat' ? 'active' : ''}
              onClick={() => setTab('chat')}
            >
              Chat
            </button>
            <button
              type="button"
              className={tab === 'diagram' ? 'active' : ''}
              onClick={() => setTab('diagram')}
            >
              System Diagram
            </button>
            <button
              type="button"
              className={tab === 'traceability' ? 'active' : ''}
              onClick={() => setTab('traceability')}
            >
              Traceability
            </button>
            <button
              type="button"
              className={tab === 'evaluations' ? 'active' : ''}
              onClick={() => setTab('evaluations')}
            >
              Evaluations
            </button>
          </div>

          {tab === 'requirements' && (
            <>
              <GenerationForm
                title="Describe the system"
                placeholder="e.g. an autonomous coffee maker that grinds beans on demand and shuts off if the pot is removed"
                buttonLabel="Generate requirements"
                models={models}
                defaultModel={defaultModel}
                busy={generating}
                showSanityCheck
                onGenerate={handleGenerate}
              />
              <RequirementsList
                requirements={draftRequirements}
                log={generationLog}
                keepingKey={keepingKey}
                onKeep={handleKeep}
                onDiscard={handleDiscard}
              />
            </>
          )}

          {tab === 'chat' && (
            <ChatPanel
              messages={chatMessages}
              busy={chatBusy}
              keepingKey={chatKeepingKey}
              onSend={handleSendChat}
              onKeep={handleKeepFromChat}
              onClear={handleClearChat}
            />
          )}

          {tab === 'traceability' && (
            <TraceabilityPanel
              coverage={coverage}
              traces={traces}
              blocks={savedDiagram.blocks}
              suggestions={suggestions}
              suggesting={suggesting}
              saving={savingTraces}
              onSuggest={handleSuggestTraces}
              onAcceptAll={handleAcceptAllTraces}
              onAcceptOne={handleAcceptTrace}
              onDismissOne={handleDismissTrace}
              onDeleteTrace={handleDeleteTrace}
            />
          )}

          {tab === 'evaluations' && (
            <EvaluationsPanel
              records={evaluations.records}
              summary={evaluations.summary}
              model={defaultModel || models[0] || 'the default model'}
              running={runningSuite}
              onRunSuite={handleRunSuite}
              judgeResult={judgeResult}
              judging={judging}
              onJudge={handleJudge}
            />
          )}

          {tab === 'diagram' && (
            <>
              <GenerationForm
                title="Describe the system"
                placeholder="e.g. an autonomous coffee maker that grinds beans on demand and shuts off if the pot is removed"
                buttonLabel="Generate diagram"
                models={models}
                defaultModel={defaultModel}
                busy={generatingDiagram}
                onGenerate={handleGenerateDiagram}
              />
              <div className="panel">
                <h2>Generated block diagram</h2>
                <BlockDiagram blocks={draftDiagram.blocks} connectors={draftDiagram.connectors} />
                {draftDiagram.blocks.length > 0 && (
                  <div className="diagram-actions">
                    <button type="button" onClick={handleSaveDiagram} disabled={savingDiagram}>
                      {savingDiagram ? 'Saving…' : 'Save to model'}
                    </button>
                  </div>
                )}
                {diagramLog.length > 0 && (
                  <details className="generation-log">
                    <summary>Generation log ({diagramLog.length})</summary>
                    <ul>
                      {diagramLog.map((line, i) => (
                        <li key={i}>{line}</li>
                      ))}
                    </ul>
                  </details>
                )}
              </div>
              <div className="panel">
                <div className="diagram-panel-heading">
                  <h2>Saved diagram ({savedDiagram.blocks.length} block(s))</h2>
                  <button type="button" className="link-button" onClick={openFullDiagramView}>
                    Open full-size ↗
                  </button>
                </div>
                <BlockDiagram blocks={savedDiagram.blocks} connectors={savedDiagram.connectors} />
                {savedDiagram.blocks.length > 0 && (
                  <>
                    {savedDiagram.prompt && (
                      <p className="empty-state">
                        Change which requirements you have kept, then regenerate
                        to redesign against the new set.
                      </p>
                    )}
                    <div className="diagram-actions">
                      {savedDiagram.prompt && (
                        <button
                          type="button"
                          onClick={handleRegenerateDiagram}
                          disabled={generatingDiagram}
                        >
                          {generatingDiagram
                            ? 'Regenerating…'
                            : `Regenerate from ${modelElements.length} requirement(s)`}
                        </button>
                      )}
                      <button type="button" className="secondary" onClick={handleClearDiagram}>
                        Clear saved diagram
                      </button>
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>

        <div className="column">
          <ModelElementsPanel
            elements={modelElements}
            onDelete={handleDelete}
            deletingId={deletingId}
          />
          <ActivityLog entries={activityLog} />
        </div>
      </div>
    </div>
  )
}

export default App
