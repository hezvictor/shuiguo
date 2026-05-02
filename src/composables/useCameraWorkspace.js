import { reactive, readonly } from 'vue'
import {
  getCameraCaptures,
  getCameraRegistry,
  getMeasureRuntimeStatus,
  scanCameraRegistry,
  updateCameraSelection
} from '@/api/detection'

const state = reactive({
  loading: false,
  registry: {
    selection: {
      single_camera_index: 0,
      dual_left_camera_index: 0,
      dual_right_camera_index: 1,
      preview_camera_indices: []
    },
    last_scan: {
      results: [],
      pair_results: [],
      device_catalog: [],
      recommended_dual_pair: null
    },
    suggested_intervals: {
      single_interval_ms: 1500,
      dual_interval_ms: 5000
    }
  },
  captures: [],
  runtimeStatus: null
})

function normalizeRegistryPayload(payload = {}) {
  return {
    selection: {
      single_camera_index: payload.selection?.single_camera_index ?? 0,
      dual_left_camera_index: payload.selection?.dual_left_camera_index ?? 0,
      dual_right_camera_index: payload.selection?.dual_right_camera_index ?? 1,
      preview_camera_indices: payload.selection?.preview_camera_indices || [],
      backend: payload.selection?.backend || ''
    },
    last_scan: {
      backend: payload.last_scan?.backend || '',
      max_index: payload.last_scan?.max_index || 0,
      results: payload.last_scan?.results || [],
      pair_results: payload.last_scan?.pair_results || [],
      device_catalog: payload.last_scan?.device_catalog || [],
      opened_count: payload.last_scan?.opened_count || 0,
      recommended_dual_pair: payload.last_scan?.recommended_dual_pair || null,
      updated_at: payload.last_scan?.updated_at || null
    },
    suggested_intervals: {
      single_interval_ms: payload.suggested_intervals?.single_interval_ms || 1500,
      dual_interval_ms: payload.suggested_intervals?.dual_interval_ms || 5000
    }
  }
}

async function loadRegistry() {
  state.loading = true
  try {
    state.registry = normalizeRegistryPayload(await getCameraRegistry())
    return state.registry
  } finally {
    state.loading = false
  }
}

async function scanRegistry(data = {}) {
  state.loading = true
  try {
    state.registry = normalizeRegistryPayload(await scanCameraRegistry(data))
    return state.registry
  } finally {
    state.loading = false
  }
}

async function saveSelection(data) {
  state.loading = true
  try {
    state.registry = normalizeRegistryPayload(await updateCameraSelection(data))
    return state.registry
  } finally {
    state.loading = false
  }
}

async function loadCaptures(params = {}) {
  const payload = await getCameraCaptures(params)
  state.captures = payload.records || []
  return state.captures
}

async function loadRuntimeStatus() {
  state.runtimeStatus = await getMeasureRuntimeStatus()
  return state.runtimeStatus
}

export function useCameraWorkspace() {
  return {
    state: readonly(state),
    loadRegistry,
    scanRegistry,
    saveSelection,
    loadCaptures,
    loadRuntimeStatus
  }
}
