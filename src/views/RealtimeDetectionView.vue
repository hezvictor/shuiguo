<template>
  <div class="realtime-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Realtime Detection Workspace</p>
          <h1>实时检测</h1>
          <p class="hero-text">
            实时检测会读取摄像头配置页保存的默认设备方案。左侧持续展示 WebSocket 实时画面，右侧负责切换检测任务、
            调整检测间隔，并控制摄像头与检测会话的开始和停止。
          </p>
        </div>

        <div class="hero-badges">
          <span class="hero-badge">当前模式：{{ modeText }}</span>
          <span class="hero-badge">检测间隔：{{ intervalMs }} ms</span>
          <span class="hero-badge">运行状态：{{ isRunning ? '检测中' : '未启动' }}</span>
        </div>
      </section>

      <section class="guide-strip">
        <article class="guide-step">
          <span class="guide-index">1</span>
          <div>
            <h3>选择检测任务</h3>
            <p>可以只做种类检测、种类+熟度检测、果径检测，或混合模式同时做单摄与双摄分析。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">2</span>
          <div>
            <h3>启动摄像头预览</h3>
            <p>页面通过 WebSocket 持续刷新实时画面，不再依赖轮询抓拍图片来模拟实时预览。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">3</span>
          <div>
            <h3>开始实时检测</h3>
            <p>检测循环会按设定间隔抓取当前帧，并把本次会话的统计结果持续累加到右侧面板。</p>
          </div>
        </article>
      </section>

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="true"
        @close="errorMessage = ''"
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
                <p>混合模式下会同时展示单摄分类结果和双摄果径结果，并标明结果来源。</p>
              </div>
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
                  <span v-if="targetFruitConfidence(target) !== '-'"> ({{ targetFruitConfidence(target) }})</span>
                </p>
                <p v-if="target.ripeness">
                  熟度：{{ targetRipenessLabel(target) }} ({{ targetRipenessConfidence(target) }})
                </p>
                <p v-if="targetHasDiameter(target)">果径：{{ targetDiameterText(target) }}</p>
              </article>
            </div>

            <div v-else class="result-empty">
              <h3>暂无检测结果</h3>
              <p>启动实时检测后，最新识别结果会展示在这里。</p>
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
                    <el-checkbox v-model="detectClassification" :disabled="isRunning">水果种类检测</el-checkbox>
                    <el-checkbox v-model="detectRipeness" :disabled="isRunning || !detectClassification">熟度检测</el-checkbox>
                    <el-checkbox v-model="detectDiameter" :disabled="isRunning">果径检测</el-checkbox>
                  </div>
                  <p class="task-hint">当前执行模式：{{ modeText }}</p>
                </el-form-item>

                <el-form-item label="检测间隔 (ms)">
                  <div class="interval-row">
                    <el-input-number v-model="intervalMs" :min="500" :step="500" />
                    <el-button @click="applySuggestedInterval">使用建议默认值</el-button>
                  </div>
                </el-form-item>

                <el-form-item label="当前全局相机方案">
                  <div class="selection-summary">
                    <p>默认单摄：{{ singleCameraLabel }}</p>
                    <p>默认双摄：{{ dualPairLabel }}</p>
                    <p>当前预览源：{{ activePreviewDeviceLabel }}</p>
                    <p>预览连接：{{ previewConnected ? 'WebSocket 已连接' : 'WebSocket 未连接' }}</p>
                  </div>
                </el-form-item>
              </el-form>
            </div>

            <div class="action-row action-row--stacked">
              <el-button type="primary" :loading="scanning" @click="refreshDevices">刷新设备并同步全局</el-button>
              <el-button @click="goToCameraConfig">前往摄像头配置页</el-button>
              <el-button type="primary" :disabled="previewEnabled || !canStartPreview" @click="startPreview">
                启动摄像头
              </el-button>
              <el-button type="warning" :disabled="!previewEnabled" @click="stopPreview">
                停止摄像头
              </el-button>
              <el-button type="success" :disabled="isRunning" :loading="runningRequest" @click="startLoop">
                开始实时检测
              </el-button>
              <el-button type="warning" :disabled="!isRunning" @click="stopLoop">停止实时检测</el-button>
              <el-button :disabled="!sessionSummary.total_targets || saving" :loading="saving" @click="saveSessionReport">
                保存本次会话
              </el-button>
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
                <span>采样次数</span>
                <strong>{{ sessionSummary.sample_count }}</strong>
              </div>
              <div v-if="showDiameterMetrics" class="metric-box">
                <span>有效果径数</span>
                <strong>{{ sessionSummary.valid_measurements }}</strong>
              </div>
              <div v-if="showDiameterMetrics" class="metric-box">
                <span>平均果径</span>
                <strong>{{ diameterMetric('avg') }}</strong>
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
import { computed, defineComponent, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import { detectRealtimeCurrentFrame, saveRealtimeReport } from '@/api/detection'
import { useCameraPreviewSocket } from '@/composables/useCameraPreviewSocket'
import { useCameraWorkspace } from '@/composables/useCameraWorkspace'

function createEmptySummary() {
  return {
    total_targets: 0,
    sample_count: 0,
    fruit_counts: {},
    ripeness_counts: {},
    valid_measurements: 0,
    diameter_values: []
  }
}

export default defineComponent({
  name: 'RealtimeDetectionView',
  setup() {
    const router = useRouter()
    const { state, loadRegistry, scanRegistry } = useCameraWorkspace()

    const intervalMs = ref(1500)
    const detectClassification = ref(true)
    const detectRipeness = ref(false)
    const detectDiameter = ref(false)
    const previewEnabled = ref(false)
    const isRunning = ref(false)
    const runningRequest = ref(false)
    const saving = ref(false)
    const scanning = ref(false)
    const errorMessage = ref('')
    const currentTargets = ref([])
    const lastDetectAt = ref(null)
    const sessionSummary = ref(createEmptySummary())
    const sessionMode = ref('')
    let loopTimer = null

    const registry = computed(() => state.registry)
    const singleIntervalMs = computed(() => registry.value.suggested_intervals?.single_interval_ms || 1500)
    const dualIntervalMs = computed(() => registry.value.suggested_intervals?.dual_interval_ms || 5000)
    const effectiveMode = computed(() => {
      if (detectDiameter.value && detectClassification.value) {
        return 'hybrid'
      }
      if (detectDiameter.value) {
        return 'dual'
      }
      if (detectClassification.value) {
        return 'single'
      }
      return ''
    })
    const previewMode = computed(() => (detectDiameter.value ? 'dual' : 'single'))
    const modeText = computed(() => {
      if (effectiveMode.value === 'single') {
        return detectRipeness.value ? '单摄种类 + 熟度检测' : '单摄种类检测'
      }
      if (effectiveMode.value === 'dual') {
        return '双摄果径检测'
      }
      if (effectiveMode.value === 'hybrid') {
        return detectRipeness.value ? '混合模式（种类 + 熟度 + 果径）' : '混合模式（种类 + 果径）'
      }
      return '未选择检测任务'
    })
    const previewDescription = computed(() =>
      previewMode.value === 'dual'
        ? '当前预览使用默认双摄设备，便于在果径检测或混合模式下直接观察左右相机画面。'
        : '当前预览使用默认单摄设备，适用于水果种类和熟度实时检测。'
    )
    const showDiameterMetrics = computed(
      () => detectDiameter.value || sessionSummary.value.valid_measurements > 0 || sessionSummary.value.diameter_values.length > 0
    )
    const singleCameraIndex = computed(() => registry.value.selection?.single_camera_index ?? 0)
    const dualLeftCameraIndex = computed(() => registry.value.selection?.dual_left_camera_index ?? 0)
    const dualRightCameraIndex = computed(() => registry.value.selection?.dual_right_camera_index ?? 1)

    const resolveCameraLabel = (cameraIndex) => {
      const matched = (registry.value.last_scan?.results || []).find((item) => item.camera_index === cameraIndex)
      return matched?.device_name ? `${matched.device_name}（索引 ${cameraIndex}）` : `相机 ${cameraIndex}`
    }

    const singleCameraLabel = computed(() => resolveCameraLabel(singleCameraIndex.value))
    const dualPairLabel = computed(() => {
      const leftLabel = resolveCameraLabel(dualLeftCameraIndex.value)
      const rightLabel = resolveCameraLabel(dualRightCameraIndex.value)
      return `${leftLabel} / ${rightLabel}`
    })
    const activePreviewDeviceLabel = computed(() =>
      previewMode.value === 'dual' ? dualPairLabel.value : singleCameraLabel.value
    )
    const lastDetectTime = computed(() => (lastDetectAt.value ? new Date(lastDetectAt.value).toLocaleString('zh-CN') : '暂无'))
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
      if (effectiveMode.value === 'dual') {
        return dualIntervalMs.value
      }
      if (effectiveMode.value === 'hybrid') {
        return Math.max(singleIntervalMs.value, dualIntervalMs.value)
      }
      return singleIntervalMs.value
    })

    const previewPayload = computed(() => {
      if (previewMode.value === 'dual') {
        return {
          mode: 'dual',
          left_camera_index: dualLeftCameraIndex.value,
          right_camera_index: dualRightCameraIndex.value,
          detect: false,
          fps: 6
        }
      }
      return {
        mode: 'single',
        camera_index: singleCameraIndex.value,
        detect: false,
        fps: 6
      }
    })

    const canStartPreview = computed(() => {
      if (previewMode.value === 'dual') {
        return dualLeftCameraIndex.value !== dualRightCameraIndex.value
      }
      return true
    })

    const previewActive = computed(() => previewEnabled.value && canStartPreview.value)

    const {
      connected: previewConnected,
      errorMessage: previewErrorMessage,
      frameDataUrl: previewFrameDataUrl,
      imageUrl: previewImageUrl
    } = useCameraPreviewSocket({
      active: previewActive,
      payload: previewPayload
    })

    const applySuggestedInterval = () => {
      intervalMs.value = suggestedIntervalMs.value
    }

    const normalizeTaskSelection = () => {
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
        errorMessage.value = '当前预览所需的摄像头配置无效，请先检查双摄左右相机是否重复。'
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
        applySuggestedInterval()
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '读取摄像头配置失败'
      }
    }

    const refreshDevices = async () => {
      scanning.value = true
      errorMessage.value = ''
      try {
        await scanRegistry({ max_index: 8 })
        applySuggestedInterval()
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
      ;(payload.targets || []).forEach((target) => {
        const distance = target.diameter?.distance_mm
        if (distance !== null && distance !== undefined) {
          sessionSummary.value.diameter_values.push(Number(distance))
        }
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
          frame_data_url: mode === 'single' ? previewFrameDataUrl.value || undefined : undefined
        })
        currentTargets.value = payload.targets || []
        lastDetectAt.value = Date.now()
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
        scheduleNext()
      }, intervalMs.value)
    }

    const startLoop = async () => {
      if (isRunning.value) return
      if (!effectiveMode.value) {
        errorMessage.value = '请至少勾选一种检测任务后再启动实时检测'
        return
      }
      if (!canStartPreview.value) {
        errorMessage.value = '当前模式对应的摄像头配置无效，请先到摄像头配置页修正默认设备'
        return
      }
      if (!previewEnabled.value) {
        previewEnabled.value = true
      }

      sessionMode.value = effectiveMode.value
      sessionSummary.value = createEmptySummary()
      currentTargets.value = []
      isRunning.value = true

      const ok = await runDetectionOnce()
      if (!ok) {
        isRunning.value = false
        sessionMode.value = ''
        return
      }

      scheduleNext()
      ElMessage.success('实时检测已启动')
    }

    const diameterMetric = (type) => {
      const values = sessionSummary.value.diameter_values || []
      if (!values.length) return '-'
      if (type === 'avg') {
        return `${(values.reduce((sum, value) => sum + value, 0) / values.length).toFixed(2)} mm`
      }
      if (type === 'min') {
        return `${Math.min(...values).toFixed(2)} mm`
      }
      return `${Math.max(...values).toFixed(2)} mm`
    }

    const saveSessionReport = async () => {
      const mode = sessionMode.value || effectiveMode.value
      if (!mode) {
        errorMessage.value = '当前没有可保存的检测模式'
        return
      }

      saving.value = true
      try {
        const includeDiameterStats =
          sessionSummary.value.valid_measurements > 0 || sessionSummary.value.diameter_values.length > 0
        await saveRealtimeReport({
          mode,
          interval_ms: intervalMs.value,
          sample_count: sessionSummary.value.sample_count,
          total_targets: sessionSummary.value.total_targets,
          fruit_counts: sessionSummary.value.fruit_counts,
          ripeness_counts: sessionSummary.value.ripeness_counts,
          valid_measurements: sessionSummary.value.valid_measurements,
          statistics: includeDiameterStats
            ? {
                avg_diameter_mm: sessionSummary.value.diameter_values.length
                  ? Number(
                      (
                        sessionSummary.value.diameter_values.reduce((sum, value) => sum + value, 0) /
                        sessionSummary.value.diameter_values.length
                      ).toFixed(6)
                    )
                  : null,
                min_diameter_mm: sessionSummary.value.diameter_values.length
                  ? Number(Math.min(...sessionSummary.value.diameter_values).toFixed(6))
                  : null,
                max_diameter_mm: sessionSummary.value.diameter_values.length
                  ? Number(Math.max(...sessionSummary.value.diameter_values).toFixed(6))
                  : null
              }
            : {},
          camera_profile: {
            single_camera_index: singleCameraIndex.value,
            dual_left_camera_index: dualLeftCameraIndex.value,
            dual_right_camera_index: dualRightCameraIndex.value
          }
        })
        ElMessage.success('本次实时检测会话已保存到历史记录')
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '保存会话失败'
      } finally {
        saving.value = false
      }
    }

    const goToCameraConfig = () => {
      router.push('/camera/config')
    }

    const targetSourceLabel = (target) => {
      if (target?.source_mode === 'dual') {
        return '双摄'
      }
      if (target?.source_mode === 'single') {
        return '单摄'
      }
      return '检测目标'
    }

    const targetFruitLabel = (target) => {
      if (target?.source_mode === 'dual') {
        return target?.classification?.class || target?.label || '未识别'
      }
      return target?.fruit_class || target?.label || '未识别'
    }

    const targetFruitConfidence = (target) => {
      const confidence =
        target?.source_mode === 'dual' ? target?.classification?.confidence ?? target?.confidence : target?.fruit_confidence
      if (confidence === null || confidence === undefined) {
        return '-'
      }
      return `${(Number(confidence) * 100).toFixed(1)}%`
    }

    const targetRipenessLabel = (target) => target?.ripeness?.class || '-'
    const targetRipenessConfidence = (target) => {
      if (target?.ripeness?.confidence === null || target?.ripeness?.confidence === undefined) {
        return '-'
      }
      return `${(Number(target.ripeness.confidence) * 100).toFixed(1)}%`
    }
    const targetHasDiameter = (target) => target?.diameter?.distance_mm !== null && target?.diameter?.distance_mm !== undefined
    const targetDiameterText = (target) => {
      if (targetHasDiameter(target)) {
        return `${Number(target.diameter.distance_mm).toFixed(2)} mm`
      }
      return target?.diameter?.status || '-'
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
      () => {
        normalizeTaskSelection()
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

    onMounted(() => {
      loadWorkspace()
    })

    onBeforeUnmount(() => {
      stopLoop(false)
    })

    return {
      activePreviewDeviceLabel,
      applySuggestedInterval,
      canStartPreview,
      currentTargets,
      detectClassification,
      detectDiameter,
      detectRipeness,
      diameterMetric,
      dualPairLabel,
      errorMessage,
      formatBbox,
      fruitStats,
      goToCameraConfig,
      intervalMs,
      isRunning,
      lastDetectTime,
      modeText,
      previewConnected,
      previewDescription,
      previewEnabled,
      previewErrorMessage,
      previewImageUrl,
      refreshDevices,
      ripenessStats,
      runningRequest,
      saveSessionReport,
      saving,
      scanning,
      sessionSummary,
      showDiameterMetrics,
      singleCameraLabel,
      startLoop,
      startPreview,
      statWidth,
      stopLoop,
      stopPreview,
      targetDiameterText,
      targetFruitConfidence,
      targetFruitLabel,
      targetHasDiameter,
      targetRipenessConfidence,
      targetRipenessLabel,
      targetSourceLabel,
      targetTitle
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

.guide-strip {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.guide-step {
  display: flex;
  gap: 14px;
  padding: 18px 20px;
  border-radius: 22px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 14px 34px rgba(29, 54, 44, 0.06);
}

.guide-index {
  flex: 0 0 40px;
  width: 40px;
  height: 40px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: #173b32;
  color: #f6fbf8;
  font-weight: 700;
}

.guide-step h3,
.panel-header h2 {
  margin: 0 0 6px;
  color: #173b32;
}

.guide-step p,
.panel-header p {
  margin: 0;
  color: #587166;
  line-height: 1.7;
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
  .hero,
  .guide-strip {
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
