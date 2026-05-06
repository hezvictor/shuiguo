const STORAGE_KEY = 'realtimeDetectionDraft'

function hasDraftContent(payload) {
  if (!payload || typeof payload !== 'object') return false
  return Boolean(
    payload.sessionId ||
      payload.capturedGroupCount ||
      payload.lastDetectionPayload ||
      (Array.isArray(payload.currentResultItems) && payload.currentResultItems.length) ||
      (payload.sessionSummary && Number(payload.sessionSummary.total_targets || 0) > 0)
  )
}

export function loadRealtimeDetectionDraft() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    return hasDraftContent(parsed) ? parsed : null
  } catch (_error) {
    return null
  }
}

export function saveRealtimeDetectionDraft(payload) {
  if (!hasDraftContent(payload)) {
    localStorage.removeItem(STORAGE_KEY)
    return
  }
  localStorage.setItem(STORAGE_KEY, JSON.stringify(payload))
}

export function clearRealtimeDetectionDraft() {
  localStorage.removeItem(STORAGE_KEY)
}
