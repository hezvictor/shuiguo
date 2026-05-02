<template>
  <div class="camera-config-page">
    <div class="page-shell">
      <section class="hero">
        <div>
          <p class="eyebrow">Camera Configuration Workspace</p>
          <h1>摄像头配置</h1>
          <p class="hero-text">
            先扫描当前设备并同步全局摄像头方案，再选择单摄、双摄和预览设备。预览区域通过 WebSocket
            直接展示实时画面，不再轮询静态截图。
          </p>
        </div>

        <div class="hero-actions">
          <el-button type="primary" :loading="scanning" @click="scanDevices">扫描并同步设备</el-button>
          <el-button :loading="savingSelection" @click="saveCurrentSelection">保存当前选择</el-button>
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

      <section class="summary-grid">
        <article class="summary-card">
          <span class="summary-label">已扫描设备</span>
          <strong class="summary-value">{{ availableCameraOptions.length }}</strong>
          <p>{{ lastScanText }}</p>
        </article>

        <article class="summary-card">
          <span class="summary-label">默认单摄</span>
          <strong class="summary-value">{{ cameraLabel(localSelection.single_camera_index) }}</strong>
          <p>用于单摄识别与成熟度检测。</p>
        </article>

        <article class="summary-card">
          <span class="summary-label">默认双摄</span>
          <strong class="summary-value">{{ dualPairLabel }}</strong>
          <p>用于果径检测和双目测量。</p>
        </article>

        <article class="summary-card">
          <span class="summary-label">建议检测间隔</span>
          <strong class="summary-value">
            单摄 {{ registry.suggested_intervals.single_interval_ms }} ms / 双摄
            {{ registry.suggested_intervals.dual_interval_ms }} ms
          </strong>
          <p>根据当前后端运行状态给出的保守默认值。</p>
        </article>
      </section>

      <section class="workspace-grid">
        <div class="workspace-main">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>设备扫描结果</h2>
                <p>勾选要在本页实时预览的摄像头，扫描结果会同步到整个系统。</p>
              </div>
            </div>

            <div v-if="availableCameraOptions.length" class="device-list">
              <label v-for="camera in availableCameraOptions" :key="camera.camera_index" class="device-row">
                <input
                  v-model="localSelection.preview_camera_indices"
                  type="checkbox"
                  :value="camera.camera_index"
                />
                <div class="device-copy">
                  <strong>{{ camera.optionLabel }}</strong>
                  <span>索引 {{ camera.camera_index }} | {{ camera.opened ? '可打开' : '不可打开' }}</span>
                </div>
              </label>
            </div>
            <el-empty v-else description="暂未扫描到可用摄像头，请先点击上方按钮扫描设备。" />
          </section>

          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>默认使用方案</h2>
                <p>保存后，实时检测页会直接复用这里的单摄和双摄配置。</p>
              </div>
            </div>

            <div class="form-grid">
              <el-form label-position="top">
                <el-form-item label="默认单摄">
                  <el-select v-model="localSelection.single_camera_index" filterable placeholder="请选择单摄">
                    <el-option
                      v-for="camera in availableCameraOptions"
                      :key="`single-${camera.camera_index}`"
                      :label="camera.optionLabel"
                      :value="camera.camera_index"
                    />
                  </el-select>
                </el-form-item>

                <el-form-item label="双摄左相机">
                  <el-select v-model="localSelection.dual_left_camera_index" filterable placeholder="请选择左相机">
                    <el-option
                      v-for="camera in availableCameraOptions"
                      :key="`left-${camera.camera_index}`"
                      :label="camera.optionLabel"
                      :value="camera.camera_index"
                    />
                  </el-select>
                </el-form-item>

                <el-form-item label="双摄右相机">
                  <el-select v-model="localSelection.dual_right_camera_index" filterable placeholder="请选择右相机">
                    <el-option
                      v-for="camera in availableCameraOptions"
                      :key="`right-${camera.camera_index}`"
                      :label="camera.optionLabel"
                      :value="camera.camera_index"
                    />
                  </el-select>
                </el-form-item>
              </el-form>
            </div>
          </section>

          <section class="panel-card">
            <div class="panel-header panel-header--actions">
              <div>
                <h2>预览与拍照</h2>
                <p>预览卡片通过独立 WebSocket 连接显示实时画面，拍照测试会临时释放预览后再自动恢复。</p>
              </div>
              <div class="preview-actions">
                <el-button type="primary" :disabled="!previewCameraIndices.length || previewEnabled" @click="startPreview">
                  启动摄像头
                </el-button>
                <el-button type="warning" :disabled="!previewEnabled" @click="stopPreview">
                  停止摄像头
                </el-button>
                <el-button
                  type="success"
                  :loading="capturing"
                  :disabled="!canCapture"
                  @click="captureSelected"
                >
                  拍照测试
                </el-button>
              </div>
            </div>

            <div v-if="previewCameraIndices.length" class="preview-grid">
              <CameraPreviewCard
                v-for="cameraIndex in previewCameraIndices"
                :key="cameraIndex"
                :camera-index="cameraIndex"
                :title="cameraLabel(cameraIndex)"
                :active="previewEnabled && previewCameraIndices.includes(cameraIndex)"
              />
            </div>
            <el-empty v-else description="请先在上方勾选要预览的摄像头。" />
          </section>
        </div>

        <div class="workspace-side">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>拍照结果</h2>
                <p>单摄图片支持直接下载，双摄记录支持查看左右图并批量下载 ZIP。</p>
              </div>
            </div>

            <div class="capture-toolbar">
              <el-button size="small" @click="loadCaptureRecords">刷新列表</el-button>
              <el-button
                size="small"
                type="primary"
                :disabled="!selectedCaptureIds.length || downloadingZip"
                :loading="downloadingZip"
                @click="downloadSelectedZip"
              >
                下载选中 ZIP
              </el-button>
            </div>

            <div v-if="captureRecords.length" class="capture-list">
              <article v-for="record in captureRecords" :key="record.id" class="capture-item">
                <label class="capture-select">
                  <input v-model="selectedCaptureIds" type="checkbox" :value="record.id" />
                  <span>{{ record.capture_mode === 'dual' ? '双摄记录' : '单摄图片' }}</span>
                </label>

                <div class="capture-meta">
                  <strong>
                    {{
                      record.capture_mode === 'dual'
                        ? (record.group_name || record.id)
                        : (record.files[0]?.file_name || record.id)
                    }}
                  </strong>
                  <span>{{ formatDateTime(record.created_at) }}</span>
                </div>

                <div class="capture-files">
                  <a
                    v-for="fileInfo in record.files"
                    :key="`${record.id}-${fileInfo.file_name}`"
                    class="capture-link"
                    :href="fileInfo.file_url"
                    target="_blank"
                    rel="noopener"
                  >
                    {{ fileInfo.role || 'image' }}: {{ fileInfo.file_name }}
                  </a>
                </div>
              </article>
            </div>
            <el-empty v-else description="还没有拍照记录。" />
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { computed, defineComponent, onMounted, reactive, ref, watch } from 'vue'
import { ElMessage } from 'element-plus'
import { captureCameraImages, downloadCameraCaptures } from '@/api/detection'
import CameraPreviewCard from '@/components/CameraPreviewCard.vue'
import { useCameraWorkspace } from '@/composables/useCameraWorkspace'

const PREVIEW_RELEASE_DELAY_MS = 250

export default defineComponent({
  name: 'CameraConfigView',
  components: {
    CameraPreviewCard
  },
  setup() {
    const { state, loadCaptures, loadRegistry, loadRuntimeStatus, saveSelection, scanRegistry } = useCameraWorkspace()

    const localSelection = reactive({
      single_camera_index: 0,
      dual_left_camera_index: 0,
      dual_right_camera_index: 1,
      preview_camera_indices: []
    })

    const scanning = ref(false)
    const savingSelection = ref(false)
    const capturing = ref(false)
    const downloadingZip = ref(false)
    const errorMessage = ref('')
    const selectedCaptureIds = ref([])
    const previewEnabled = ref(false)

    const registry = computed(() => state.registry)
    const captureRecords = computed(() => state.captures || [])
    const availableCameraOptions = computed(() =>
      (registry.value.last_scan?.results || [])
        .filter((item) => item.opened)
        .map((item) => ({
          ...item,
          optionLabel: item.device_name ? `${item.device_name}（索引 ${item.camera_index}）` : `相机 ${item.camera_index}`
        }))
    )
    const previewCameraIndices = computed(() => localSelection.preview_camera_indices || [])
    const canCapture = computed(() => {
      const count = previewCameraIndices.value.length
      return count === 1 || count === 2
    })
    const dualPairLabel = computed(() => {
      if (localSelection.dual_left_camera_index === localSelection.dual_right_camera_index) {
        return '请重新选择左右相机'
      }
      return `${cameraLabel(localSelection.dual_left_camera_index)} / ${cameraLabel(localSelection.dual_right_camera_index)}`
    })
    const lastScanText = computed(() => {
      const raw = registry.value.last_scan?.updated_at
      if (!raw) return '尚未扫描'
      return `最近扫描时间：${new Date(raw * 1000).toLocaleString('zh-CN')}`
    })

    const patchLocalSelection = () => {
      localSelection.single_camera_index = registry.value.selection?.single_camera_index ?? 0
      localSelection.dual_left_camera_index = registry.value.selection?.dual_left_camera_index ?? 0
      localSelection.dual_right_camera_index = registry.value.selection?.dual_right_camera_index ?? 1
      localSelection.preview_camera_indices = [...(registry.value.selection?.preview_camera_indices || [])]
    }

    const cameraLabel = (cameraIndex) => {
      const current = availableCameraOptions.value.find((item) => item.camera_index === cameraIndex)
      return current?.optionLabel || `相机 ${cameraIndex}`
    }

    const loadCaptureRecords = async () => {
      try {
        await loadCaptures({ limit: 100 })
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '读取拍照记录失败'
      }
    }

    const bootstrap = async () => {
      try {
        await loadRegistry()
        patchLocalSelection()
        await loadRuntimeStatus()
        await loadCaptureRecords()
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '读取摄像头配置失败'
      }
    }

    const scanDevices = async () => {
      scanning.value = true
      errorMessage.value = ''
      try {
        await scanRegistry({ max_index: 8 })
        patchLocalSelection()
        ElMessage.success('扫描完成，设备信息已同步到全局配置')
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '扫描摄像头失败'
      } finally {
        scanning.value = false
      }
    }

    const saveCurrentSelection = async () => {
      if (localSelection.dual_left_camera_index === localSelection.dual_right_camera_index) {
        errorMessage.value = '双摄左相机和右相机不能相同'
        return
      }
      savingSelection.value = true
      errorMessage.value = ''
      try {
        await saveSelection({
          single_camera_index: localSelection.single_camera_index,
          dual_left_camera_index: localSelection.dual_left_camera_index,
          dual_right_camera_index: localSelection.dual_right_camera_index,
          preview_camera_indices: localSelection.preview_camera_indices
        })
        patchLocalSelection()
        ElMessage.success('当前摄像头方案已保存')
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '保存摄像头方案失败'
      } finally {
        savingSelection.value = false
      }
    }

    const startPreview = () => {
      if (!previewCameraIndices.value.length) {
        errorMessage.value = '请先勾选至少一个要预览的摄像头'
        return
      }
      previewEnabled.value = true
      errorMessage.value = ''
      ElMessage.success('摄像头预览已启动')
    }

    const stopPreview = () => {
      previewEnabled.value = false
      ElMessage.info('摄像头预览已停止')
    }

    const captureSelected = async () => {
      const selected = [...previewCameraIndices.value]
      if (!selected.length) {
        errorMessage.value = '请先勾选至少一个用于拍照测试的摄像头'
        return
      }
      if (selected.length > 2) {
        errorMessage.value = '拍照测试仅支持单摄或双摄，请将预览设备控制在 1 到 2 个'
        return
      }

      capturing.value = true
      errorMessage.value = ''
      const shouldResumePreview = previewEnabled.value

      try {
        if (shouldResumePreview) {
          previewEnabled.value = false
          await new Promise((resolve) => window.setTimeout(resolve, PREVIEW_RELEASE_DELAY_MS))
        }

        const isDual = selected.length === 2
        const response = await captureCameraImages({
          camera_indices: selected,
          capture_mode: isDual ? 'dual' : 'single',
          left_camera_index: isDual ? selected[0] : undefined,
          right_camera_index: isDual ? selected[1] : undefined
        })

        await loadCaptureRecords()
        ElMessage.success(`拍照完成，本次生成 ${response.records?.length || 0} 条记录`)
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '拍照失败'
      } finally {
        if (shouldResumePreview) {
          previewEnabled.value = true
        }
        capturing.value = false
      }
    }

    const downloadSelectedZip = async () => {
      if (!selectedCaptureIds.value.length) {
        return
      }
      downloadingZip.value = true
      try {
        const blob = await downloadCameraCaptures({ record_ids: selectedCaptureIds.value })
        const url = URL.createObjectURL(blob)
        const anchor = document.createElement('a')
        anchor.href = url
        anchor.download = `camera_captures_${Date.now()}.zip`
        document.body.appendChild(anchor)
        anchor.click()
        document.body.removeChild(anchor)
        URL.revokeObjectURL(url)
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '批量下载失败'
      } finally {
        downloadingZip.value = false
      }
    }

    const formatDateTime = (value) => (value ? new Date(value).toLocaleString('zh-CN') : '-')

    watch(
      previewCameraIndices,
      (value) => {
        if (!value.length && previewEnabled.value) {
          previewEnabled.value = false
        }
      },
      { deep: true }
    )

    onMounted(() => {
      bootstrap()
    })

    return {
      availableCameraOptions,
      cameraLabel,
      canCapture,
      captureRecords,
      captureSelected,
      capturing,
      downloadingZip,
      downloadSelectedZip,
      dualPairLabel,
      errorMessage,
      formatDateTime,
      lastScanText,
      loadCaptureRecords,
      localSelection,
      previewCameraIndices,
      previewEnabled,
      registry,
      saveCurrentSelection,
      savingSelection,
      scanDevices,
      scanning,
      selectedCaptureIds,
      startPreview,
      stopPreview
    }
  }
})
</script>

<style scoped>
.camera-config-page {
  padding: 20px;
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(35, 80, 66, 0.15), transparent 26%),
    linear-gradient(180deg, #f3f7f5 0%, #ebf0ed 100%);
}

.page-shell {
  max-width: 1480px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.hero,
.panel-card,
.summary-card {
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 20px 42px rgba(27, 51, 40, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) auto;
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

.hero-actions {
  display: flex;
  gap: 12px;
  align-items: start;
  flex-wrap: wrap;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 18px 20px;
}

.summary-label {
  display: block;
  color: #557064;
  margin-bottom: 8px;
}

.summary-value {
  display: block;
  color: #173b32;
  font-size: 20px;
  margin-bottom: 8px;
}

.summary-card p {
  margin: 0;
  color: #587166;
  line-height: 1.7;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.45fr) 420px;
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
}

.panel-card {
  padding: 22px;
}

.panel-header {
  margin-bottom: 16px;
}

.panel-header--actions {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
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

.preview-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  align-items: center;
}

.device-list,
.capture-list {
  display: grid;
  gap: 12px;
}

.device-row,
.capture-item {
  display: flex;
  gap: 14px;
  padding: 14px 16px;
  border-radius: 18px;
  background: #f6faf7;
}

.device-copy,
.capture-meta {
  display: grid;
  gap: 4px;
}

.device-copy strong,
.capture-meta strong {
  color: #173b32;
}

.device-copy span,
.capture-meta span {
  color: #587166;
  font-size: 13px;
}

.form-grid {
  display: grid;
  gap: 16px;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
  gap: 16px;
}

.capture-toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.capture-item {
  flex-direction: column;
}

.capture-select {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #35594d;
}

.capture-files {
  display: grid;
  gap: 6px;
}

.capture-link {
  color: #235042;
  text-decoration: none;
  font-size: 13px;
}

@media (max-width: 1320px) {
  .workspace-grid {
    grid-template-columns: 1fr;
  }

  .workspace-side {
    position: static;
  }

  .summary-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }
}

@media (max-width: 900px) {
  .hero,
  .panel-header--actions {
    grid-template-columns: 1fr;
  }

  .panel-header--actions {
    display: grid;
  }
}

@media (max-width: 768px) {
  .camera-config-page {
    padding: 12px;
  }

  .summary-grid {
    grid-template-columns: 1fr;
  }
}
</style>
