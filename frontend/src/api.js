const BASE_URL = import.meta.env.VITE_API_BASE ?? 'http://localhost:8000'

async function request(path, options = {}) {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })

  if (!res.ok) {
    let detail = res.statusText
    try {
      const body = await res.json()
      detail = body.detail ? JSON.stringify(body.detail) : detail
    } catch {
      // response wasn't JSON, fall back to statusText
    }
    throw new Error(`${res.status} ${detail}`)
  }

  return res.status === 204 ? null : res.json()
}

export const api = {
  getModels: () => request('/models'),

  generateRequirements: (payload) =>
    request('/requirements/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  listModelElements: () => request('/model-elements'),

  createModelElements: (elements) =>
    request('/model-elements', {
      method: 'POST',
      body: JSON.stringify({ elements }),
    }),

  deleteModelElement: (id) =>
    request(`/model-elements/${id}`, { method: 'DELETE' }),

  getActivityLog: () => request('/activity-log'),

  generateDiagram: (payload) =>
    request('/diagram/generate', {
      method: 'POST',
      body: JSON.stringify(payload),
    }),

  getDiagram: () => request('/diagram'),

  saveDiagram: (blocks, connectors) =>
    request('/diagram', {
      method: 'POST',
      body: JSON.stringify({ blocks, connectors }),
    }),

  clearDiagram: () => request('/diagram', { method: 'DELETE' }),

  getTraces: () => request('/traces'),

  getCoverage: () => request('/traces/coverage'),

  suggestTraces: (model) =>
    request('/traces/suggest', {
      method: 'POST',
      body: JSON.stringify({ model }),
    }),

  createTraces: (traces) =>
    request('/traces', {
      method: 'POST',
      body: JSON.stringify({ traces }),
    }),

  deleteTrace: (id) => request(`/traces/${id}`, { method: 'DELETE' }),

  getEvaluations: () => request('/evaluations'),

  judgeRequirements: (model) =>
    request('/evaluations/judge', {
      method: 'POST',
      body: JSON.stringify({ model }),
    }),

  runEvaluationSuite: (model) =>
    request('/evaluations/run-suite', {
      method: 'POST',
      body: JSON.stringify({ model }),
    }),
}
