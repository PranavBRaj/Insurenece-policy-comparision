import axios from 'axios'

const LLM_PROVIDER_KEY = 'pasta-llm-provider'

const api = axios.create({
  baseURL: '/api',
  timeout: 120_000, // 2 min – large PDFs can take time
})

// ---- Interceptor: normalise error messages ----
api.interceptors.response.use(
  (res) => res,
  (err) => {
    const detail =
      err.response?.data?.detail ||
      err.response?.data?.message ||
      err.message ||
      'An unexpected error occurred'
    return Promise.reject(new Error(detail))
  },
)

export function getSelectedLlmProvider() {
  const value = window.localStorage.getItem(LLM_PROVIDER_KEY)
  return value === 'ollama' ? 'ollama' : 'groq'
}

export function setSelectedLlmProvider(provider) {
  const safe = provider === 'ollama' ? 'ollama' : 'groq'
  window.localStorage.setItem(LLM_PROVIDER_KEY, safe)
  return safe
}

function llmParams(extra = {}) {
  return { ...extra, llm_provider: getSelectedLlmProvider() }
}

/**
 * Upload two PDF files and receive comparison results.
 * @param {File} file1
 * @param {File} file2
 * @param {(pct: number) => void} [onProgress]
 */
export async function uploadAndCompare(file1, file2, onProgress, provider) {
  const form = new FormData()
  form.append('policy1', file1)
  form.append('policy2', file2)
  form.append('llm_provider', provider || getSelectedLlmProvider())

  const res = await api.post('/upload-compare', form, {
    headers: { 'Content-Type': 'multipart/form-data' },
    onUploadProgress: (evt) => {
      if (onProgress && evt.total) {
        onProgress(Math.round((evt.loaded / evt.total) * 100))
      }
    },
  })
  return res.data
}

/**
 * Get a single comparison by id.
 * @param {number} id
 */
export async function getComparison(id) {
  const res = await api.get(`/comparisons/${id}`)
  return res.data
}

/**
 * List recent comparisons.
 * @param {number} [skip]
 * @param {number} [limit]
 */
export async function listComparisons(skip = 0, limit = 20) {
  const res = await api.get('/comparisons', { params: { skip, limit } })
  return res.data
}

/**
 * Delete a comparison.
 * @param {number} id
 */
export async function deleteComparison(id) {
  await api.delete(`/comparisons/${id}`)
}

/**
 * Get upload session history.
 * @param {number} [skip]
 * @param {number} [limit]
 */
export async function getHistory(skip = 0, limit = 20) {
  const res = await api.get('/history', { params: { skip, limit } })
  return res.data
}

/**
 * Ask a natural language question about a stored comparison.
 * @param {number} comparisonId
 * @param {string} question
 * @returns {{ question: string, answer: string, confidence: string, relevant_sections: string[] }}
 */
export async function askQuestion(comparisonId, question) {
  const res = await api.post(
    `/comparisons/${comparisonId}/ask`,
    { question },
    { params: llmParams() },
  )
  return res.data
}

/**
 * Download the PDF report for a comparison.
 * Triggers a browser file-save dialog.
 * @param {number} comparisonId
 */
export async function downloadPdf(comparisonId) {
  const response = await fetch(`/api/comparisons/${comparisonId}/export.pdf`)
  if (!response.ok) {
    const errData = await response.json().catch(() => ({}))
    throw new Error(errData.detail || `PDF export failed (HTTP ${response.status})`)
  }
  const blob = await response.blob()
  const url  = URL.createObjectURL(blob)
  const a    = document.createElement('a')
  a.href     = url
  a.download = `comparison_${comparisonId}.pdf`
  document.body.appendChild(a)
  a.click()
  document.body.removeChild(a)
  URL.revokeObjectURL(url)
}

/**
 * Fetch chart-ready visualisation data for a comparison.
 * @param {number} comparisonId
 * @returns {Promise<import('../types').VisualisationResponse>}
 */
export async function getVisualisation(comparisonId) {
  const res = await api.get(`/comparisons/${comparisonId}/visualisation`)
  return res.data
}

/**
 * Get LLM-powered policy recommendations for a user profile.
 * @param {number} comparisonId
 * @param {object} profile  - UserProfileInput fields (all optional)
 */
export async function getRecommendations(comparisonId, profile) {
  const res = await api.post(`/comparisons/${comparisonId}/recommend`, profile, {
    params: llmParams(),
  })
  return res.data
}

/**
 * Run anomaly detection on a completed comparison.
 * @param {number} comparisonId
 */
export async function getAnomalies(comparisonId) {
  const res = await api.get(`/comparisons/${comparisonId}/anomalies`, {
    params: llmParams(),
  })
  return res.data
}

/**
 * Generate a plain-English consumer-friendly summary of a comparison.
 * @param {number} comparisonId
 */
export async function getPlainSummary(comparisonId) {
  const res = await api.get(`/comparisons/${comparisonId}/plain-summary`, {
    params: llmParams(),
  })
  return res.data
}

