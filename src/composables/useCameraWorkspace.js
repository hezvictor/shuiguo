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
      single_camera_index: null,
      dual_left_camera_index: null,
      dual_right_camera_index: null,
      preview_camera_indices: []
    },
    last_scan: {
      results: [],
      pair_results: [],
      device_catalog: [],
      recommended_dual_pair: null,
      updated_at: null
    },
    suggested_intervals: {
      single_interval_ms: 1500,
      dual_interval_ms: 5000
    },
    capabilities: {
      scan_completed: false,
      readable_camera_count: 0,
      readable_camera_indices: [],
      single: {
        configured: false,
        available: false,
        reason_code: 'camera_not_scanned',
        message: '尚未扫描摄像头，请先到摄像头拍照与配置页扫描并保存默认单摄配置。'
      },
      dual: {
        configured: false,
        available: false,
        reason_code: 'camera_not_scanned',
        message: '尚未扫描摄像头，请先扫描并配置双目摄像头。'
      },
      realtime: {
        classification_available: false,
        ripeness_available: false,
        diameter_available: false,
        hybrid_available: false
      }
    }
  },
  captures: [],
  stagedCaptureGroups: [],
  runtimeStatus: null
})

function normalizeRegistryPayload(payload = {}) {
  return {
    selection: {
      single_camera_index: payload.selection?.single_camera_index ?? null,
      dual_left_camera_index: payload.selection?.dual_left_camera_index ?? null,
      dual_right_camera_index: payload.selection?.dual_right_camera_index ?? null,
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
    },
    capabilities: {
      scan_completed: !!payload.capabilities?.scan_completed,
      readable_camera_count: payload.capabilities?.readable_camera_count || 0,
      readable_camera_indices: payload.capabilities?.readable_camera_indices || [],
      single: {
        configured: !!payload.capabilities?.single?.configured,
        available: !!payload.capabilities?.single?.available,
        reason_code: payload.capabilities?.single?.reason_code || '',
        message: payload.capabilities?.single?.message || ''
      },
      dual: {
        configured: !!payload.capabilities?.dual?.configured,
        available: !!payload.capabilities?.dual?.available,
        reason_code: payload.capabilities?.dual?.reason_code || '',
        message: payload.capabilities?.dual?.message || ''
      },
      realtime: {
        classification_available: !!payload.capabilities?.realtime?.classification_available,
        ripeness_available: !!payload.capabilities?.realtime?.ripeness_available,
        diameter_available: !!payload.capabilities?.realtime?.diameter_available,
        hybrid_available: !!payload.capabilities?.realtime?.hybrid_available
      }
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
  state.stagedCaptureGroups = payload.staged_groups || []
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
