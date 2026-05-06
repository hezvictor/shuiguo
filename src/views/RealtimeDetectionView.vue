<template>
  <div class="realtime-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Realtime Detection Workspace</p>
          <h1>实时检测</h1>
          <p class="hero-text">
            实时检测会复用摄像头拍照与配置页保存的默认设备方案，按固定时间间隔从摄像头采样，并将采样结果沿用图片检测同一套批处理和
            Excel 报告链路。双目与混合模式下，实时页面只展示左相机预览画面；右侧黑白相机仍会在后台继续参与果径检测，不影响现有测量流程。
          </p>
        </div>

        <div class="hero-badges">
          <span class="hero-badge">当前模式：{{ modeText }}</span>
          <span class="hero-badge">推荐间隔：{{ suggestedIntervalMs }} ms</span>
          <span class="hero-badge">运行状态：{{ isRunning ? '采样中' : '未启动' }}</span>
        </div>
      </section>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="true"
        @close="errorMessage = ''"
      />

      <el-alert
        v-if="workspaceNotice"
        :title="workspaceNotice"
        :type="workspaceNoticeType"
        show-icon
        :closable="false"
      />

      <section class="workspace-grid">
        <div class="workspace-main">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>实时摄像头画面</h2>
                <p>{{ previewDescription }}</p>
              </div>
              <span class="panel-badge">{{ lastDetectTime }}</span>
            </div>

            <div class="frame-stage">
              <img v-if="previewImageUrl" :src="previewImageUrl" alt="realtime preview" class="frame-image" />
              <div v-else class="frame-placeholder">
                <h3>{{ previewEnabled ? '等待预览画面' : '摄像头未启动' }}</h3>
                <p>
                  {{
                    previewEnabled
                      ? 'WebSocket 已建立，正在等待摄像头返回画面。'
                      : '请先点击“启动摄像头”，然后再开始实时检测。'
                  }}
                </p>
              </div>
            </div>

            <p v-if="previewErrorMessage" class="preview-error">{{ previewErrorMessage }}</p>
          </section>

          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>最近一次检测结果</h2>
                <p>这里展示本轮最新检测的标注图和目标详情，单摄、果径、混合三种模式统一显示。</p>
              </div>
            </div>

            <div v-if="lastDetectionPayload?.annotated_image_url" class="latest-result-frame">
              <img :src="lastDetectionPayload.annotated_image_url" alt="latest detection result" class="latest-result-image" />
            </div>

            <div v-if="currentTargets.length" class="result-grid">
              <article v-for="(target, index) in currentTargets" :key="`target-${index}`" class="result-item">
                <div class="result-head">
                  <strong>{{ targetTitle(target) }}</strong>
                  <span class="result-source">{{ targetSourceLabel(target) }}</span>
                </div>
                <p>位置：{{ formatBbox(target.bbox) }}</p>
                <p>
                  种类：{{ targetFruitLabel(target) }}
                  <span v-if="targetFruitConfidence(target) !== '-'">({{ targetFruitConfidence(target) }})</span>
                </p>
                <p v-if="target.ripeness">
                  熟度：{{ targetRipenessLabel(target) }} ({{ targetRipenessConfidence(target) }})
                </p>
                <p v-if="targetHasDiameter(target)">果径：{{ targetDiameterText(target) }}</p>
              </article>
            </div>

            <div v-else class="result-empty">
              <h3>暂无检测结果</h3>
              <p>启动实时检测后，最新识别结果会显示在这里。</p>
            </div>
          </section>
        </div>

        <div class="workspace-side">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>检测模式与设备</h2>
                <p>右侧控制区会复用摄像头配置页保存的默认单摄和双摄方案。</p>
              </div>
            </div>

            <div class="form-grid">
              <el-form label-position="top">
                <el-form-item label="检测任务">
                  <div class="task-grid">
                    <el-checkbox v-model="detectClassification" :disabled="isRunning || !classificationTaskAvailable">水果种类检测</el-checkbox>
                    <el-checkbox v-model="detectRipeness" :disabled="isRunning || !detectClassification || !ripenessTaskAvailable">熟度检测</el-checkbox>
                    <el-checkbox v-model="detectDiameter" :disabled="isRunning || !diameterTaskAvailable">果径检测</el-checkbox>
                  </div>
                  <p class="task-hint">当前执行模式：{{ modeText }}</p>
                  <p v-if="!classificationTaskAvailable" class="task-hint">水果种类/熟度检测：{{ singleCapabilityMessage }}</p>
                  <p v-if="!diameterTaskAvailable" class="task-hint">果径检测：{{ dualCapabilityMessage }}</p>
                </el-form-item>

                <el-form-item label="检测间隔 (ms)">
                  <div class="interval-row">
                    <el-input-number v-model="intervalMs" :min="500" :step="500" />
                    <el-button @click="applySuggestedInterval">使用推荐默认值</el-button>
                  </div>
                </el-form-item>

                <el-form-item label="采样组数">
                  <div class="interval-row">
                    <el-input-number v-model="targetGroupCount" :min="1" :max="500" :step="1" :disabled="isRunning" />
                    <span class="task-hint">已采样 {{ capturedGroupCount }} / {{ targetGroupCount }} 组</span>
                  </div>
                </el-form-item>

                <el-form-item label="当前全局相机方案">
                  <div class="selection-summary">
                    <p>默认单摄：{{ singleCameraLabel }}</p>
                    <p>默认双摄：{{ dualPairLabel }}</p>
                    <p>当前预览源：{{ activePreviewDeviceLabel }}</p>
                    <p>预览连接：{{ previewConnected ? 'WebSocket 已连接' : 'WebSocket 未连接' }}</p>
                    <p>当前会话：{{ sessionId || '未建立' }}</p>
                  </div>
                  <p class="task-hint">双目/混合模式下前端只显示左相机画面，右相机仍在后台参与果径测量，不影响现有检测流程。</p>
                </el-form-item>
              </el-form>
            </div>

            <div class="action-row action-row--stacked">
              <el-button type="primary" :loading="scanning" @click="refreshDevices">刷新设备并同步全局</el-button>
              <el-button @click="goToCameraConfig">前往摄像头拍照与配置页</el-button>
              <el-button type="primary" :disabled="previewEnabled || !canStartPreview" @click="startPreview">启动摄像头</el-button>
              <el-button type="warning" :disabled="!previewEnabled" @click="stopPreview">停止摄像头</el-button>
              <el-button type="success" :disabled="isRunning || !canStartDetection" :loading="runningRequest" @click="startLoop">开始实时检测</el-button>
              <el-button type="warning" :disabled="!isRunning" @click="stopLoop">停止实时检测</el-button>
              <el-button :disabled="!sessionId || !capturedGroupCount || saving" :loading="saving" @click="saveSessionReport">
                保存本次会话
              </el-button>
              <el-button :disabled="isRunning || saving || !hasDraftContent" @click="clearDraftManually">清空草稿</el-button>
            </div>
          </section>

          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>本次会话统计</h2>
                <p>这里会累计显示当前实时检测会话的识别数量、熟度分布和果径统计。</p>
              </div>
            </div>

            <div class="stats-grid">
              <div class="metric-box">
                <span>累计目标数</span>
                <strong>{{ sessionSummary.total_targets }}</strong>
              </div>
              <div class="metric-box">
                <span>检测次数</span>
                <strong>{{ sessionSummary.sample_count }}</strong>
              </div>
              <div class="metric-box">
                <span>采样进度</span>
                <strong>{{ capturedGroupCount }} / {{ targetGroupCount }}</strong>
              </div>
              <div v-if="showDiameterMetrics" class="metric-box">
                <span>横向平均果径</span>
                <strong>{{ diameterMetric('horizontal', 'avg') }}</strong>
              </div>
              <div v-if="showDiameterMetrics" class="metric-box">
                <span>竖向平均果径</span>
                <strong>{{ diameterMetric('vertical', 'avg') }}</strong>
              </div>
              <div v-if="showDiameterMetrics" class="metric-box">
                <span>有效目标数</span>
                <strong>{{ sessionSummary.valid_measurements }}</strong>
              </div>
              <div v-if="showDiameterMetrics" class="metric-box">
                <span>横向有效数</span>
                <strong>{{ sessionSummary.valid_measurements_by_axis.horizontal }}</strong>
              </div>
              <div v-if="showDiameterMetrics" class="metric-box">
                <span>竖向有效数</span>
                <strong>{{ sessionSummary.valid_measurements_by_axis.vertical }}</strong>
              </div>
            </div>

            <div v-if="fruitStats.length" class="stats-block">
              <h3>水果种类统计</h3>
              <div v-for="item in fruitStats" :key="item.fruit" class="stat-item">
                <div class="stat-top">
                  <span>{{ item.fruit }}</span>
                  <span>{{ item.count }}</span>
                </div>
                <div class="stat-bar">
                  <div class="stat-fill" :style="{ width: statWidth(item.count) }"></div>
                </div>
              </div>
            </div>

            <div v-if="ripenessStats.length" class="stats-block">
              <h3>熟度统计</h3>
              <div v-for="item in ripenessStats" :key="`${item.fruit}-${item.ripeness}`" class="stat-item">
                <div class="stat-top">
                  <span>{{ item.fruit }} - {{ item.ripeness }}</span>
                  <span>{{ item.count }}</span>
                </div>
                <div class="stat-bar">
                  <div class="stat-fill alt" :style="{ width: statWidth(item.count) }"></div>
                </div>
              </div>
            </div>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { detectRealtimeCurrentFrame, saveRealtimeReport } from '@/api/detection'
import { useCameraPreviewSocket } from '@/composables/useCameraPreviewSocket'
import { useCameraWorkspace } from '@/composables/useCameraWorkspace'
import { translateFruitLabel, translateRipenessLabel } from '@/utils/labelMap'
import {
  clearRealtimeDetectionDraft,
  loadRealtimeDetectionDraft,
  saveRealtimeDetectionDraft
} from '@/utils/realtimeDetectionWorkspace'

function createEmptySummary() {
  return {
    total_targets: 0,
    sample_count: 0,
    fruit_counts: {},
    ripeness_counts: {},
    valid_measurements: 0,
    valid_measurements_by_axis: {
      horizontal: 0,
      vertical: 0
    },
    diameter_axes: {
      horizontal: {
        sum_mm: 0,
        count: 0,
        min_mm: null,
        max_mm: null
      },
      vertical: {
        sum_mm: 0,
        count: 0,
        min_mm: null,
        max_mm: null
      }
    }
  }
}

function getDiameterAxes(target) {
  return target?.diameter?.diameter_axes || {}
}

function getAxisDistance(target, axisName) {
  const axis = getDiameterAxes(target)[axisName] || {}
  if (axis.distance_mm === null || axis.distance_mm === undefined) return null
  return Number(axis.distance_mm)
}

function getAxisStatus(target, axisName) {
  return (getDiameterAxes(target)[axisName] || {}).status || '-'
}

function cropDualPreviewToLeftBlob(blob) {
  return new Promise((resolve, reject) => {
    const image = new Image()
    const objectUrl = URL.createObjectURL(blob)

    const cleanup = () => {
      URL.revokeObjectURL(objectUrl)
    }

    image.onload = () => {
      try {
        const sourceWidth = Number(image.naturalWidth || 0)
        const sourceHeight = Number(image.naturalHeight || 0)
        if (sourceWidth < 2 || sourceHeight < 1) {
          cleanup()
          resolve(blob)
          return
        }

        const targetWidth = Math.max(1, Math.floor(sourceWidth / 2))
        const canvas = document.createElement('canvas')
        canvas.width = targetWidth
        canvas.height = sourceHeight

        const context = canvas.getContext('2d')
        if (!context) {
          cleanup()
          resolve(blob)
          return
        }

        context.drawImage(image, 0, 0, targetWidth, sourceHeight, 0, 0, targetWidth, sourceHeight)
        canvas.toBlob(
          (croppedBlob) => {
            cleanup()
            resolve(croppedBlob || blob)
          },
          'image/jpeg',
          0.9
        )
      } catch (error) {
        cleanup()
        reject(error)
      }
    }

    image.onerror = () => {
      cleanup()
      reject(new Error('failed to crop dual preview frame'))
    }

    image.src = objectUrl
  })
}

function isTimeoutError(error) {
  const message = String(error?.message || '')
  return error?.code === 'ECONNABORTED' || /timeout/i.test(message)
}

export default defineComponent({
  name: 'RealtimeDetectionView',
  setup() {
    const router = useRouter()
    const { state, loadRegistry, scanRegistry } = useCameraWorkspace()

    const intervalMs = ref(2000)
    const targetGroupCount = ref(10)
    const detectClassification = ref(true)
    const detectRipeness = ref(false)
    const detectDiameter = ref(false)
    const previewEnabled = ref(false)
    const isRunning = ref(false)
    const runningRequest = ref(false)
    const saving = ref(false)
    const scanning = ref(false)
    const errorMessage = ref('')
    const currentResultItems = ref([])
    const lastDetectionPayload = ref(null)
    const lastDetectAt = ref(null)
    const sessionSummary = ref(createEmptySummary())
    const sessionMode = ref('')
    const sessionId = ref('')
    const capturedGroupCount = ref(0)
    const restoredDraft = ref(false)
    let loopTimer = null

    const registry = computed(() => state.registry)
    const capabilities = computed(() => registry.value.capabilities || {})
    const realtimeCapabilities = computed(() => capabilities.value.realtime || {})
    const singleIntervalMs = computed(() => registry.value.suggested_intervals?.single_interval_ms || 2000)
    const dualIntervalMs = computed(() => registry.value.suggested_intervals?.dual_interval_ms || 6000)
    const classificationTaskAvailable = computed(() => !!realtimeCapabilities.value.classification_available)
    const ripenessTaskAvailable = computed(() => !!realtimeCapabilities.value.ripeness_available)
    const diameterTaskAvailable = computed(() => !!realtimeCapabilities.value.diameter_available)
    const singleCapabilityMessage = computed(
      () => capabilities.value.single?.message || '尚未配置默认单摄像头，实时检测暂不可用。'
    )
    const dualCapabilityMessage = computed(
      () => capabilities.value.dual?.message || '尚未配置默认双目摄像头，果径实时检测暂不可用。'
    )

    const effectiveMode = computed(() => {
      if (detectDiameter.value && detectClassification.value) return 'hybrid'
      if (detectDiameter.value) return 'dual'
      if (detectClassification.value) return 'single'
      return ''
    })

    const previewMode = computed(() => (detectDiameter.value ? 'dual' : 'single'))
    const modeText = computed(() => {
      if (effectiveMode.value === 'single') return detectRipeness.value ? '单摄种类 + 熟度检测' : '单摄种类检测'
      if (effectiveMode.value === 'dual') return '双摄果径检测'
      if (effectiveMode.value === 'hybrid') return detectRipeness.value ? '混合模式（种类 + 熟度 + 果径）' : '混合模式（种类 + 果径）'
      return '未选择检测任务'
    })
    const previewShowsLeftCameraOnly = computed(() => previewMode.value === 'dual')
    const previewDescription = computed(() =>
      previewShowsLeftCameraOnly.value
        ? '当前预览已切换为默认双摄中的左相机画面；右相机会继续在后台参与果径检测与测量。'
        : '当前预览使用默认单摄设备，适用于水果种类和熟度实时检测。'
    )
    const showDiameterMetrics = computed(
      () =>
        detectDiameter.value ||
        sessionSummary.value.valid_measurements > 0 ||
        sessionSummary.value.diameter_axes.horizontal.count > 0 ||
        sessionSummary.value.diameter_axes.vertical.count > 0
    )

    const singleCameraIndex = computed(() => registry.value.selection?.single_camera_index ?? null)
    const dualLeftCameraIndex = computed(() => registry.value.selection?.dual_left_camera_index ?? null)
    const dualRightCameraIndex = computed(() => registry.value.selection?.dual_right_camera_index ?? null)

    const resolveCameraLabel = (cameraIndex) => {
      if (cameraIndex === null || cameraIndex === undefined) {
        return '未配置'
      }
      const matched = (registry.value.last_scan?.results || []).find((item) => item.camera_index === cameraIndex)
      return matched?.device_name ? `${matched.device_name}（索引 ${cameraIndex}）` : `相机 ${cameraIndex}`
    }

    const singleCameraLabel = computed(() => resolveCameraLabel(singleCameraIndex.value))
    const dualPairLabel = computed(() => {
      if (dualLeftCameraIndex.value === null && dualRightCameraIndex.value === null) {
        return '未配置'
      }
      if (dualLeftCameraIndex.value === null || dualRightCameraIndex.value === null) {
        return '请补全左右相机'
      }
      return `${resolveCameraLabel(dualLeftCameraIndex.value)} / ${resolveCameraLabel(dualRightCameraIndex.value)}`
    })
    const activePreviewDeviceLabel = computed(() => (previewMode.value === 'dual' ? dualPairLabel.value : singleCameraLabel.value))
    const lastDetectTime = computed(() => (lastDetectAt.value ? new Date(lastDetectAt.value).toLocaleString('zh-CN') : '暂无'))
    const workspaceNotice = computed(() => {
      if (!capabilities.value.scan_completed) {
        return singleCapabilityMessage.value
      }
      if (classificationTaskAvailable.value && !diameterTaskAvailable.value) {
        return dualCapabilityMessage.value
      }
      if (!classificationTaskAvailable.value && !diameterTaskAvailable.value) {
        return [singleCapabilityMessage.value, dualCapabilityMessage.value].filter(Boolean).join(' ')
      }
      return ''
    })
    const workspaceNoticeType = computed(() => (classificationTaskAvailable.value || diameterTaskAvailable.value ? 'warning' : 'error'))

    const currentTargets = computed(() => currentResultItems.value.flatMap((item) => item.targets || []))
    const hasDraftContent = computed(
      () =>
        !!sessionId.value ||
        capturedGroupCount.value > 0 ||
        !!lastDetectionPayload.value ||
        currentResultItems.value.length > 0 ||
        Number(sessionSummary.value.total_targets || 0) > 0
    )
    const fruitStats = computed(() =>
      Object.entries(sessionSummary.value.fruit_counts || {})
        .map(([fruit, count]) => ({ fruit, count }))
        .sort((a, b) => b.count - a.count)
    )
    const ripenessStats = computed(() => {
      const result = []
      Object.entries(sessionSummary.value.ripeness_counts || {}).forEach(([fruit, ripenessMap]) => {
        Object.entries(ripenessMap || {}).forEach(([ripeness, count]) => {
          result.push({ fruit, ripeness, count })
        })
      })
      return result
    })

    const suggestedIntervalMs = computed(() => {
      if (effectiveMode.value === 'dual') return dualIntervalMs.value
      if (effectiveMode.value === 'hybrid') return Math.max(singleIntervalMs.value, dualIntervalMs.value)
      return singleIntervalMs.value
    })

    const modeAvailability = computed(() => {
      if (effectiveMode.value === 'single') {
        return {
          available: classificationTaskAvailable.value,
          message: singleCapabilityMessage.value
        }
      }
      if (effectiveMode.value === 'dual' || effectiveMode.value === 'hybrid') {
        return {
          available: diameterTaskAvailable.value,
          message: dualCapabilityMessage.value
        }
      }
      return {
        available: false,
        message: '请至少勾选一种检测任务后再启动实时检测'
      }
    })

    const previewPayload = computed(() => {
      if (previewMode.value === 'dual') {
        return {
          mode: 'dual',
          left_camera_index: dualLeftCameraIndex.value,
          right_camera_index: dualRightCameraIndex.value,
          detect: false,
          fps: 12
        }
      }
      return {
        mode: 'single',
        camera_index: singleCameraIndex.value,
        detect: false,
        fps: 12
      }
    })

    const canStartPreview = computed(() => {
      if (previewMode.value === 'dual') {
        return diameterTaskAvailable.value && dualLeftCameraIndex.value !== dualRightCameraIndex.value
      }
      return classificationTaskAvailable.value
    })
    const canStartDetection = computed(() => !!effectiveMode.value && modeAvailability.value.available)
    const previewActive = computed(() => previewEnabled.value && canStartPreview.value)

    const {
      connected: previewConnected,
      errorMessage: previewErrorMessage,
      imageUrl: previewImageUrl
    } = useCameraPreviewSocket({
      active: previewActive,
      payload: previewPayload,
      transformFrameBlob: async (blob) => {
        if (!previewShowsLeftCameraOnly.value) {
          return blob
        }
        return cropDualPreviewToLeftBlob(blob)
      }
    })

    const draftPersistencePaused = ref(false)

    const applySuggestedInterval = () => {
      intervalMs.value = suggestedIntervalMs.value
    }

    const resetSessionDraftState = async () => {
      draftPersistencePaused.value = true
      currentResultItems.value = []
      lastDetectionPayload.value = null
      lastDetectAt.value = null
      sessionSummary.value = createEmptySummary()
      sessionMode.value = ''
      sessionId.value = ''
      capturedGroupCount.value = 0
      restoredDraft.value = false
      clearRealtimeDetectionDraft()
      await nextTick()
      draftPersistencePaused.value = false
      persistRealtimeDraft()
    }

    const clearSessionDraftState = async () => {
      await resetSessionDraftState()
    }

    const clearDraftManually = async () => {
      errorMessage.value = ''
      await clearSessionDraftState()
      ElMessage.success('实时检测草稿已清空')
    }

    const persistRealtimeDraft = () => {
      saveRealtimeDetectionDraft({
        intervalMs: intervalMs.value,
        targetGroupCount: targetGroupCount.value,
        detectClassification: detectClassification.value,
        detectRipeness: detectRipeness.value,
        detectDiameter: detectDiameter.value,
        currentResultItems: currentResultItems.value,
        lastDetectionPayload: lastDetectionPayload.value,
        lastDetectAt: lastDetectAt.value,
        sessionSummary: sessionSummary.value,
        sessionMode: sessionMode.value,
        sessionId: sessionId.value,
        capturedGroupCount: capturedGroupCount.value
      })
    }

    const restoreRealtimeDraft = () => {
      const draft = loadRealtimeDetectionDraft()
      if (!draft) return false

      intervalMs.value = Number(draft.intervalMs || intervalMs.value)
      targetGroupCount.value = Number(draft.targetGroupCount || targetGroupCount.value)
      detectClassification.value = draft.detectClassification !== false
      detectRipeness.value = !!draft.detectRipeness
      detectDiameter.value = !!draft.detectDiameter
      currentResultItems.value = Array.isArray(draft.currentResultItems) ? draft.currentResultItems : []
      lastDetectionPayload.value = draft.lastDetectionPayload || null
      lastDetectAt.value = draft.lastDetectAt || null
      sessionSummary.value = draft.sessionSummary || createEmptySummary()
      sessionMode.value = draft.sessionMode || ''
      sessionId.value = draft.sessionId || ''
      capturedGroupCount.value = Number(draft.capturedGroupCount || 0)
      restoredDraft.value = true
      return true
    }

    const normalizeTaskSelection = () => {
      if (!classificationTaskAvailable.value) {
        detectClassification.value = false
        detectRipeness.value = false
      }
      if (!diameterTaskAvailable.value) {
        detectDiameter.value = false
      }
      if (detectRipeness.value && !detectClassification.value) {
        detectClassification.value = true
      }
      if (!detectClassification.value) {
        detectRipeness.value = false
      }
    }

    const stopLoop = (showMessage = true) => {
      const wasRunning = isRunning.value
      isRunning.value = false
      if (loopTimer) {
        window.clearTimeout(loopTimer)
        loopTimer = null
      }
      if (showMessage && wasRunning) {
        ElMessage.info('实时检测已停止')
      }
    }

    const startPreview = () => {
      if (!canStartPreview.value) {
        errorMessage.value = modeAvailability.value.message
        return
      }
      previewEnabled.value = true
      errorMessage.value = ''
      ElMessage.success('摄像头预览已启动')
    }

    const stopPreview = () => {
      if (isRunning.value) {
        stopLoop(false)
      }
      previewEnabled.value = false
      ElMessage.info('摄像头预览已停止')
    }

    const loadWorkspace = async () => {
      try {
        await loadRegistry()
        const hasDraft = restoreRealtimeDraft()
        if (!hasDraft) {
          applySuggestedInterval()
        }
        normalizeTaskSelection()
        if (restoredDraft.value) {
          ElMessage.info('已恢复未保存的实时检测会话，可继续查看结果或直接保存到历史记录。')
        }
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '读取摄像头配置失败'
      }
    }

    const refreshDevices = async () => {
      scanning.value = true
      errorMessage.value = ''
      try {
        await scanRegistry({ max_index: 8 })
        if (!sessionId.value && !capturedGroupCount.value) {
          applySuggestedInterval()
        }
        normalizeTaskSelection()
        ElMessage.success('设备列表已刷新并同步到全局配置')
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '刷新设备失败'
      } finally {
        scanning.value = false
      }
    }

    const updateSessionSummary = (payload) => {
      const summary = payload.summary || {}
      sessionSummary.value.total_targets += summary.total_targets || 0
      sessionSummary.value.sample_count += 1

      Object.entries(summary.fruit_counts || {}).forEach(([fruit, count]) => {
        sessionSummary.value.fruit_counts[fruit] = (sessionSummary.value.fruit_counts[fruit] || 0) + count
      })

      Object.entries(summary.ripeness_counts || {}).forEach(([fruit, ripenessMap]) => {
        if (!sessionSummary.value.ripeness_counts[fruit]) {
          sessionSummary.value.ripeness_counts[fruit] = {}
        }
        Object.entries(ripenessMap || {}).forEach(([ripeness, count]) => {
          sessionSummary.value.ripeness_counts[fruit][ripeness] =
            (sessionSummary.value.ripeness_counts[fruit][ripeness] || 0) + count
        })
      })

      sessionSummary.value.valid_measurements += summary.valid_measurements || 0
      sessionSummary.value.valid_measurements_by_axis.horizontal += summary.valid_measurements_by_axis?.horizontal || 0
      sessionSummary.value.valid_measurements_by_axis.vertical += summary.valid_measurements_by_axis?.vertical || 0

      ;(payload.targets || []).forEach((target) => {
        ;['horizontal', 'vertical'].forEach((axisName) => {
          const distance = getAxisDistance(target, axisName)
          if (distance === null) return
          const axisSummary = sessionSummary.value.diameter_axes[axisName]
          axisSummary.sum_mm += distance
          axisSummary.count += 1
          axisSummary.min_mm = axisSummary.min_mm === null ? distance : Math.min(axisSummary.min_mm, distance)
          axisSummary.max_mm = axisSummary.max_mm === null ? distance : Math.max(axisSummary.max_mm, distance)
        })
      })
    }

    const runDetectionOnce = async () => {
      const mode = sessionMode.value || effectiveMode.value
      if (!mode) {
        errorMessage.value = '请至少选择一种检测任务'
        return false
      }

      runningRequest.value = true
      errorMessage.value = ''
      try {
        const payload = await detectRealtimeCurrentFrame({
          mode,
          camera_index: mode === 'single' || mode === 'hybrid' ? singleCameraIndex.value : undefined,
          left_camera_index: mode === 'dual' || mode === 'hybrid' ? dualLeftCameraIndex.value : undefined,
          right_camera_index: mode === 'dual' || mode === 'hybrid' ? dualRightCameraIndex.value : undefined,
          conf: 0.25,
          detect_classification: detectClassification.value,
          detect_ripeness: detectClassification.value ? detectRipeness.value : false,
          detect_diameter: detectDiameter.value,
          session_id: sessionId.value || undefined,
          collect_sample: true,
          target_group_count: targetGroupCount.value,
          interval_ms: intervalMs.value
        })
        currentResultItems.value = payload.items || []
        lastDetectionPayload.value = payload
        lastDetectAt.value = Date.now()
        sessionId.value = payload.session_id || sessionId.value
        capturedGroupCount.value = payload.captured_group_count || capturedGroupCount.value
        updateSessionSummary(payload)
        return true
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '实时检测失败'
        return false
      } finally {
        runningRequest.value = false
      }
    }

    const scheduleNext = () => {
      if (!isRunning.value) return
      loopTimer = window.setTimeout(async () => {
        if (!isRunning.value) return
        await runDetectionOnce()
        if (capturedGroupCount.value >= targetGroupCount.value) {
          stopLoop(false)
          ElMessage.success(`已完成 ${capturedGroupCount.value} 组实时采样`)
          return
        }
        scheduleNext()
      }, intervalMs.value)
    }

    const startLoop = async () => {
      if (isRunning.value) return
      if (!effectiveMode.value) {
        errorMessage.value = '请至少勾选一种检测任务后再启动实时检测'
        return
      }
      if (!modeAvailability.value.available) {
        errorMessage.value = modeAvailability.value.message
        return
      }
      if (!previewEnabled.value) {
        previewEnabled.value = true
      }

      await resetSessionDraftState()
      sessionMode.value = effectiveMode.value
      isRunning.value = true

      const ok = await runDetectionOnce()
      if (!ok) {
        isRunning.value = false
        sessionMode.value = ''
        return
      }

      if (capturedGroupCount.value >= targetGroupCount.value) {
        stopLoop(false)
        ElMessage.success(`已完成 ${capturedGroupCount.value} 组实时采样`)
        return
      }

      scheduleNext()
      ElMessage.success('实时检测已启动')
    }

    const diameterMetric = (axisName, type) => {
      const axisSummary = sessionSummary.value.diameter_axes[axisName] || {}
      if (!axisSummary.count) return '-'
      if (type === 'avg') {
        return `${(axisSummary.sum_mm / axisSummary.count).toFixed(2)} mm`
      }
      if (type === 'min') {
        return `${Number(axisSummary.min_mm).toFixed(2)} mm`
      }
      return `${Number(axisSummary.max_mm).toFixed(2)} mm`
    }

    const saveSessionReport = async () => {
      const mode = sessionMode.value || effectiveMode.value
      if (!mode) {
        errorMessage.value = '当前没有可保存的检测模式'
        return
      }
      if (!sessionId.value) {
        errorMessage.value = '当前实时会话没有可保存的采样数据'
        return
      }

      saving.value = true
      try {
        await saveRealtimeReport({
          session_id: sessionId.value,
          mode,
          interval_ms: intervalMs.value,
          camera_profile: {
            single_camera_index: singleCameraIndex.value,
            dual_left_camera_index: dualLeftCameraIndex.value,
            dual_right_camera_index: dualRightCameraIndex.value
          }
        })
        await clearSessionDraftState()
        ElMessage.success('本次实时检测会话已保存到历史记录')
      } catch (error) {
        if (isTimeoutError(error)) {
          errorMessage.value = '保存实时会话超时。后台仍可能在继续生成报告，请稍后到历史记录页确认；如果只想重置当前页面，可直接点击“清空草稿”。'
        } else {
          errorMessage.value = error?.response?.data?.error || error.message || '保存会话失败'
        }
      } finally {
        saving.value = false
      }
    }

    const goToCameraConfig = () => {
      router.push('/camera/config')
    }

    const targetSourceLabel = (target) => {
      if (target?.source_mode === 'dual') return '双摄'
      if (target?.source_mode === 'single') return '单摄'
      if (target?.source_mode === 'hybrid') return '混合'
      return '检测目标'
    }

    const targetFruitLabel = (target) => translateFruitLabel(target?.classification?.class || target?.fruit_class || target?.label || '未识别')
    const targetFruitConfidence = (target) => {
      const confidence = target?.classification?.confidence ?? target?.fruit_confidence ?? target?.confidence
      if (confidence === null || confidence === undefined) return '-'
      return `${(Number(confidence) * 100).toFixed(1)}%`
    }
    const targetRipenessLabel = (target) => translateRipenessLabel(target?.ripeness?.predicted_class || target?.ripeness?.class)
    const targetRipenessConfidence = (target) => {
      if (target?.ripeness?.confidence === null || target?.ripeness?.confidence === undefined) return '-'
      return `${(Number(target.ripeness.confidence) * 100).toFixed(1)}%`
    }
    const targetHasDiameter = (target) => getAxisDistance(target, 'horizontal') !== null || getAxisDistance(target, 'vertical') !== null
    const targetDiameterText = (target) => {
      const parts = []
      const horizontalDistance = getAxisDistance(target, 'horizontal')
      const verticalDistance = getAxisDistance(target, 'vertical')
      if (horizontalDistance !== null) {
        parts.push(`横向 ${horizontalDistance.toFixed(2)} mm`)
      } else if (getDiameterAxes(target).horizontal) {
        parts.push(`横向 ${getAxisStatus(target, 'horizontal')}`)
      }
      if (verticalDistance !== null) {
        parts.push(`竖向 ${verticalDistance.toFixed(2)} mm`)
      } else if (getDiameterAxes(target).vertical) {
        parts.push(`竖向 ${getAxisStatus(target, 'vertical')}`)
      }
      return parts.length ? parts.join(' / ') : target?.diameter?.status || '-'
    }
    const targetTitle = (target) => `${targetSourceLabel(target)} · ${targetFruitLabel(target)}`

    const formatBbox = (bbox) => (Array.isArray(bbox) && bbox.length === 4 ? `[${bbox.join(', ')}]` : '-')
    const statWidth = (count) => {
      if (!sessionSummary.value.total_targets) return '0%'
      return `${Math.min(100, ((count / sessionSummary.value.total_targets) * 100).toFixed(1))}%`
    }

    watch(
      () => detectRipeness.value,
      () => {
        normalizeTaskSelection()
      }
    )

    watch(
      () => detectClassification.value,
      (value, previousValue) => {
        if (value && !classificationTaskAvailable.value) {
          detectClassification.value = false
          if (!isRunning.value && previousValue !== value) {
            ElMessage.warning(singleCapabilityMessage.value)
          }
          return
        }
        normalizeTaskSelection()
      }
    )

    watch(
      () => detectDiameter.value,
      (value, previousValue) => {
        if (value && !diameterTaskAvailable.value) {
          detectDiameter.value = false
          if (!isRunning.value && previousValue !== value) {
            ElMessage.warning(dualCapabilityMessage.value)
          }
          return
        }
      }
    )

    watch(
      () => effectiveMode.value,
      () => {
        applySuggestedInterval()
      }
    )

    watch(
      () => canStartPreview.value,
      (value) => {
        if (!value && previewEnabled.value) {
          previewEnabled.value = false
        }
      }
    )

    watch(
      () => [classificationTaskAvailable.value, diameterTaskAvailable.value],
      () => {
        normalizeTaskSelection()
      },
      { immediate: true }
    )

    watch(
      () => [
        intervalMs.value,
        targetGroupCount.value,
        detectClassification.value,
        detectRipeness.value,
        detectDiameter.value,
        currentResultItems.value,
        lastDetectionPayload.value,
        lastDetectAt.value,
        sessionSummary.value,
        sessionMode.value,
        sessionId.value,
        capturedGroupCount.value
      ],
      () => {
        if (draftPersistencePaused.value) return
        persistRealtimeDraft()
      },
      { deep: true }
    )

    onMounted(() => {
      loadWorkspace()
    })

    onBeforeUnmount(() => {
      stopLoop(false)
    })

    return {
      activePreviewDeviceLabel,
      applySuggestedInterval,
      canStartDetection,
      canStartPreview,
      capturedGroupCount,
      classificationTaskAvailable,
      clearDraftManually,
      currentResultItems,
      currentTargets,
      detectClassification,
      detectDiameter,
      detectRipeness,
      diameterMetric,
      diameterTaskAvailable,
      dualPairLabel,
      dualCapabilityMessage,
      errorMessage,
      formatBbox,
      fruitStats,
      goToCameraConfig,
      hasDraftContent,
      intervalMs,
      isRunning,
      lastDetectTime,
      lastDetectionPayload,
      modeText,
      previewConnected,
      previewDescription,
      previewEnabled,
      previewErrorMessage,
      previewImageUrl,
      refreshDevices,
      ripenessTaskAvailable,
      ripenessStats,
      runningRequest,
      saveSessionReport,
      saving,
      scanning,
      sessionId,
      sessionSummary,
      showDiameterMetrics,
      singleCameraLabel,
      singleCapabilityMessage,
      startLoop,
      startPreview,
      statWidth,
      stopLoop,
      stopPreview,
      suggestedIntervalMs,
      targetDiameterText,
      targetFruitConfidence,
      targetFruitLabel,
      targetGroupCount,
      targetHasDiameter,
      targetRipenessConfidence,
      targetRipenessLabel,
      targetSourceLabel,
      targetTitle,
      workspaceNotice,
      workspaceNoticeType
    }
  }
})
</script>

<style scoped>
.realtime-page {
  padding: 20px;
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(44, 123, 83, 0.16), transparent 26%),
    linear-gradient(180deg, #f4f8f5 0%, #edf3ef 100%);
}

.page-shell {
  max-width: 1460px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.hero,
.panel-card {
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 20px 42px rgba(27, 51, 40, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.7fr);
  gap: 24px;
  padding: 28px 30px;
  background: linear-gradient(135deg, #173b32 0%, #235042 58%, #3a7a65 100%);
  color: #f6fbf8;
}

.eyebrow {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(246, 251, 248, 0.72);
}

.hero h1 {
  margin: 0;
  font-size: 36px;
}

.hero-text {
  margin: 14px 0 0;
  line-height: 1.8;
  color: rgba(246, 251, 248, 0.86);
}

.hero-badges {
  display: grid;
  gap: 12px;
}

.hero-badge {
  min-height: 42px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.7fr) 380px;
  gap: 20px;
  align-items: start;
}

.workspace-main,
.workspace-side {
  display: grid;
  gap: 20px;
}

.workspace-side {
  position: sticky;
  top: 16px;
  align-self: start;
}

.panel-card {
  padding: 22px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 16px;
}

.panel-header h2 {
  margin: 0 0 6px;
  color: #173b32;
}

.panel-header p {
  margin: 0;
  color: #587166;
  line-height: 1.7;
}

.panel-badge {
  display: inline-flex;
  align-items: center;
  min-height: 32px;
  padding: 0 12px;
  border-radius: 999px;
  background: #eef9f3;
  color: #18533a;
  font-size: 13px;
}

.form-grid {
  display: grid;
  gap: 16px;
}

.task-grid,
.interval-row,
.action-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.task-hint {
  margin: 10px 0 0;
  color: #587166;
  font-size: 13px;
}

.action-row--stacked .el-button {
  min-width: 148px;
}

.selection-summary {
  display: grid;
  gap: 6px;
  color: #587166;
}

.selection-summary p {
  margin: 0;
}

.frame-stage {
  border-radius: 22px;
  overflow: hidden;
  background: linear-gradient(140deg, #0f172a 0%, #1a2c43 100%);
  min-height: 520px;
  display: grid;
  place-items: center;
}

.frame-image {
  width: 100%;
  min-height: 520px;
  object-fit: cover;
  display: block;
}

.frame-placeholder {
  color: #d5dbe5;
  text-align: center;
  padding: 28px 18px;
}

.preview-error {
  margin: 12px 0 0;
  color: #b42318;
}

.latest-result-frame {
  margin-bottom: 16px;
  border-radius: 18px;
  overflow: hidden;
  background: #f6faf7;
}

.latest-result-image {
  display: block;
  width: 100%;
  max-height: 420px;
  object-fit: contain;
  background: #111827;
}

.result-grid {
  display: grid;
  gap: 12px;
}

.result-item {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f7faf8;
}

.result-head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #173b32;
}

.result-source {
  display: inline-flex;
  align-items: center;
  padding: 0 10px;
  border-radius: 999px;
  background: #eaf5ef;
  color: #235042;
  font-size: 12px;
}

.result-item p {
  margin: 8px 0 0;
  color: #587166;
  font-size: 13px;
}

.result-empty {
  padding: 30px 18px;
  border-radius: 18px;
  background: #f7faf8;
  text-align: center;
  color: #587166;
}

.result-empty h3 {
  margin: 0 0 8px;
  color: #173b32;
}

.result-empty p {
  margin: 0;
}

.stats-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.metric-box {
  padding: 14px 16px;
  border-radius: 16px;
  background: #f6faf7;
}

.metric-box span {
  display: block;
  color: #587166;
  margin-bottom: 8px;
}

.metric-box strong {
  color: #173b32;
  font-size: 18px;
}

.stats-block + .stats-block {
  margin-top: 18px;
}

.stats-block h3 {
  margin: 0 0 10px;
  color: #173b32;
}

.stat-item {
  display: grid;
  gap: 8px;
  margin-bottom: 12px;
}

.stat-top {
  display: flex;
  justify-content: space-between;
  color: #587166;
  font-size: 13px;
}

.stat-bar {
  height: 10px;
  border-radius: 999px;
  background: #e7efe9;
  overflow: hidden;
}

.stat-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2f6c59 0%, #4f927b 100%);
}

.stat-fill.alt {
  background: linear-gradient(90deg, #b8801c 0%, #f59e0b 100%);
}

@media (max-width: 1320px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .workspace-side {
    position: static;
  }
}

@media (max-width: 980px) {
  .hero {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .realtime-page {
    padding: 12px;
  }

  .action-row--stacked .el-button {
    min-width: 0;
  }

  .stats-grid {
    grid-template-columns: 1fr;
  }

  .frame-stage,
  .frame-image {
    min-height: 320px;
  }
}
</style>

