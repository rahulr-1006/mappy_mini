import { useCallback, useEffect, useState } from 'react'
import { api } from './api'
import { ActivityLog } from './components/ActivityLog'
import { BlockDiagram } from './components/BlockDiagram'
import { ChatPanel } from './components/ChatPanel'
import { EvaluationsPanel } from './components/EvaluationsPanel'
import { KnowledgePanel } from './components/KnowledgePanel'
import { ModelElementsPanel } from './components/ModelElementsPanel'
import { RequirementsWorkbench } from './components/RequirementsWorkbench'
import { TraceabilityPanel } from './components/TraceabilityPanel'
import './App.css'

function App() {
  const [tab, setTab] = useState('chat')

  const [models, setModels] = useState([])
  const [defaultModel, setDefaultModel] = useState('')
  const [modelElements, setModelElements] = useState([])
  const [activityLog, setActivityLog] = useState([])

  const [editingBusyId, setEditingBusyId] = useState(null)
  const [addingRequirement, setAddingRequirement] = useState(false)
  const [deletingId, setDeletingId] = useState(null)

  const [documents, setDocuments] = useState([])
  const [index, setIndex] = useState(null)
  const [knowledgeBusy, setKnowledgeBusy] = useState(false)

  const [draftDiagram, setDraftDiagram] = useState({ blocks: [], connectors: [] })
  const [diagramLog, setDiagramLog] = useState([])
  const [savedDiagram, setSavedDiagram] = useState({ blocks: [], connectors: [] })
  const [generatingDiagram, setGeneratingDiagram] = useState(false)
  const [savingDiagram, setSavingDiagram] = useState(false)

  const [evaluations, setEvaluations] = useState({ records: [], summary: null })
  const [runningSuite, setRunningSuite] = useState(false)
  const [judgeResult, setJudgeResult] = useState(null)
  const [judging, setJudging] = useState(false)
  const [headToHead, setHeadToHead] = useState(null)
  const [headToHeadRunning, setHeadToHeadRunning] = useState(false)

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

  const refreshKnowledge = useCallback(async () => {
    const res = await api.listDocuments()
    setDocuments(res.documents)
    setIndex(res.index)
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
          refreshKnowledge(),
        ])
        setModels(modelsRes.models)
        setDefaultModel(modelsRes.default)
      } catch (err) {
        setError(err.message)
      }
    }
    loadInitial()
  }, [refreshElements, refreshLog, refreshDiagram, refreshEvaluations, refreshTraces, refreshChat, refreshKnowledge])

  async function handleUpdateRequirement(id, fields) {
    setEditingBusyId(id)
    setError(null)
    try {
      await api.updateModelElement(id, fields)
      await Promise.all([refreshElements(), refreshLog(), refreshKnowledge()])
    } catch (err) {
      setError(err.message)
    } finally {
      setEditingBusyId(null)
    }
  }

  async function handleCreateRequirement(draft) {
    setAddingRequirement(true)
    setError(null)
    try {
      await api.createModelElements([draft])
      await Promise.all([
        refreshElements(),
        refreshLog(),
        refreshTraces(),
        refreshKnowledge(),
      ])
    } catch (err) {
      setError(err.message)
    } finally {
      setAddingRequirement(false)
    }
  }

  async function handleDelete(id) {
    setDeletingId(id)
    setError(null)
    try {
      await api.deleteModelElement(id)
      await Promise.all([
        refreshElements(),
        refreshLog(),
        refreshTraces(),
        refreshKnowledge(),
      ])
    } catch (err) {
      setError(err.message)
    } finally {
      setDeletingId(null)
    }
  }

  async function handleGenerateDiagram() {
    setGeneratingDiagram(true)
    setError(null)
    try {
      const res = await api.generateDiagram({ model: defaultModel || models[0] })
      setDraftDiagram({ blocks: res.blocks, connectors: res.connectors })
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
      await api.saveDiagram(draftDiagram.blocks, draftDiagram.connectors, '')
      await Promise.all([
        refreshDiagram(),
        refreshLog(),
        refreshTraces(),
        refreshKnowledge(),
      ])
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

  async function handleRunHeadToHead() {
    setHeadToHeadRunning(true)
    setError(null)
    try {
      setHeadToHead(await api.runHeadToHead(models))
      await Promise.all([refreshEvaluations(), refreshLog()])
    } catch (err) {
      setError(err.message)
    } finally {
      setHeadToHeadRunning(false)
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
      await Promise.all([
        refreshElements(),
        refreshLog(),
        refreshTraces(),
        refreshKnowledge(),
      ])
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
    await handleGenerateDiagram()
  }

  async function withKnowledgeBusy(work) {
    setKnowledgeBusy(true)
    setError(null)
    try {
      await work()
      await Promise.all([refreshKnowledge(), refreshLog()])
    } catch (err) {
      setError(err.message)
    } finally {
      setKnowledgeBusy(false)
    }
  }

  const handleUploadDocument = (file) => withKnowledgeBusy(() => api.uploadDocument(file))
  const handleSeedDocuments = () => withKnowledgeBusy(() => api.seedDocuments())
  const handleDeleteDocument = (id) => withKnowledgeBusy(() => api.deleteDocument(id))
  const handleReindex = () => withKnowledgeBusy(() => api.reindex())

  async function handleSearchKnowledge(query) {
    return api.searchKnowledge(query)
  }

  function openFullDiagramView() {
    window.open('/diagram-view', '_blank', 'noopener')
  }

  async function handleClearDiagram() {
    setError(null)
    try {
      await api.clearDiagram()
      await Promise.all([
        refreshDiagram(),
        refreshLog(),
        refreshTraces(),
        refreshKnowledge(),
      ])
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
              className={tab === 'chat' ? 'active' : ''}
              onClick={() => setTab('chat')}
            >
              Chat
            </button>
            <button
              type="button"
              className={tab === 'requirements' ? 'active' : ''}
              onClick={() => setTab('requirements')}
            >
              Requirements{modelElements.length > 0 ? ` (${modelElements.length})` : ''}
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
              className={tab === 'knowledge' ? 'active' : ''}
              onClick={() => setTab('knowledge')}
            >
              Knowledge{index?.documents ? ` (${index.documents})` : ''}
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
            <RequirementsWorkbench
              elements={modelElements}
              busyId={editingBusyId || deletingId}
              adding={addingRequirement}
              onUpdate={handleUpdateRequirement}
              onCreate={handleCreateRequirement}
              onDelete={handleDelete}
            />
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
              headToHead={headToHead}
              headToHeadRunning={headToHeadRunning}
              onRunHeadToHead={handleRunHeadToHead}
            />
          )}

          {tab === 'diagram' && (
            <>
              <div className="panel">
                <div className="diagram-panel-heading">
                  <div>
                    <h2>System diagram</h2>
                    <p className="panel-subtitle">
                      Generated from the requirements and the conversation.
                      There is no separate prompt. Describing the system twice
                      is how the requirements and the design end up describing
                      two different systems.
                    </p>
                  </div>
                  <button
                    type="button"
                    onClick={handleGenerateDiagram}
                    disabled={generatingDiagram || modelElements.length === 0}
                  >
                    {generatingDiagram
                      ? 'Generating…'
                      : `Generate from ${modelElements.length} requirement(s)`}
                  </button>
                </div>

                {modelElements.length === 0 && (
                  <p className="empty-state">
                    Nothing to design against yet. Keep some requirements from
                    Chat first, and the diagram will be scoped to them.
                  </p>
                )}

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
                    <p className="empty-state">
                      Change which requirements you have kept, then regenerate
                      to redesign against the new set.
                    </p>
                    <div className="diagram-actions">
                      <button
                        type="button"
                        onClick={handleRegenerateDiagram}
                        disabled={generatingDiagram || modelElements.length === 0}
                      >
                        {generatingDiagram
                          ? 'Regenerating…'
                          : `Regenerate from ${modelElements.length} requirement(s)`}
                      </button>
                      <button type="button" className="secondary" onClick={handleClearDiagram}>
                        Clear saved diagram
                      </button>
                    </div>
                  </>
                )}
              </div>
            </>
          )}

          {tab === 'knowledge' && (
            <KnowledgePanel
              documents={documents}
              index={index}
              busy={knowledgeBusy}
              onUpload={handleUploadDocument}
              onSeed={handleSeedDocuments}
              onDelete={handleDeleteDocument}
              onReindex={handleReindex}
              onSearch={handleSearchKnowledge}
            />
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
