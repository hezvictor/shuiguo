const STORAGE_KEY = 'imageDetectionDismissedIds'

export function loadDismissedIds() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    return Array.isArray(parsed) ? parsed : []
  } catch (_error) {
    return []
  }
}

export function saveDismissedIds(ids) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(new Set(ids)).slice(0, 200)))
}

export function dismissHistoryId(id) {
  const ids = loadDismissedIds()
  if (!ids.includes(id)) {
    ids.unshift(id)
    saveDismissedIds(ids)
  }
  return ids
}

export function restoreHistoryId(id) {
  const ids = loadDismissedIds().filter((item) => item !== id)
  saveDismissedIds(ids)
  return ids
}
