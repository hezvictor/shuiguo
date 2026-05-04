<template>
  <div class="camera-config-page">
    <div class="page-shell">
      <section class="hero">
        <div>
          <p class="eyebrow">Camera Configuration Workspace</p>
          <h1>摄像头配置</h1>
          <p class="hero-text">
            先扫描当前设备并同步全局摄像头方案，再选择单摄、双摄和预览设备。预览区域通过 WebSocket
            直接展示实时画面，拍照改为先暂存分组，点击保存后再生成 ZIP 结果。
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
                <p>拍照会先生成待保存分组，不立即写入结果栏。点击保存后，当前分组会打包为 ZIP 并出现在结果区。</p>
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
                  拍照
                </el-button>
                <el-button
                  type="primary"
                  plain
                  :loading="savingPending"
                  :disabled="!pendingCaptureGroups.length"
                  @click="savePendingCaptures"
                >
                  保存
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

            <div class="pending-section">
              <div class="pending-header">
                <h3>待保存照片组</h3>
                <span>{{ pendingCaptureGroups.length }} 组</span>
              </div>

              <div v-if="pendingCaptureGroups.length" class="pending-list">
                <article v-for="group in pendingCaptureGroups" :key="group.stage_id" class="pending-item">
                  <div class="pending-title-row">
                    <strong>{{ group.displayName }}</strong>
                    <div class="pending-title-actions">
                      <span>{{ formatDateTime(group.created_at) }}</span>
                      <button
                        type="button"
                        class="pending-remove"
                        :disabled="deletingPendingStageId === group.stage_id"
                        @click="deletePendingCaptureGroup(group.stage_id)"
                      >
                        ×
                      </button>
                    </div>
                  </div>
                  <p>{{ group.capture_mode === 'dual' ? '双目照片组' : '单摄照片组' }}</p>
                  <div class="pending-files">
                    <a
                      v-for="fileInfo in group.files"
                      :key="`${group.stage_id}-${fileInfo.role}`"
                      class="capture-link"
                      :href="fileInfo.file_url"
                      target="_blank"
                      rel="noopener"
                    >
                      {{ fileInfo.role }}: {{ fileInfo.file_name }}
                    </a>
                  </div>
                </article>
              </div>
              <el-empty v-else description="暂时还没有待保存的照片组。" />
            </div>
          </section>
        </div>

        <div class="workspace-side">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>拍照结果</h2>
                <p>保存后的 ZIP 压缩包会出现在这里，可直接下载，也支持勾选后批量下载。</p>
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
                  <span>{{ recordTypeLabel(record) }}</span>
                </label>

                <div class="capture-meta">
                  <strong>{{ recordTitle(record) }}</strong>
                  <span>{{ formatDateTime(record.created_at) }}</span>
                </div>

                <div v-if="record.archive_file_url" class="capture-files">
                  <a class="capture-link" :href="record.archive_file_url" target="_blank" rel="noopener">
                    ZIP: {{ record.archive_name }}
                  </a>
                  <span class="capture-extra">共 {{ record.group_count || 0 }} 组照片</span>
                </div>

                <div v-else class="capture-files">
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

                <div class="capture-item-actions">
                  <el-button
                    size="small"
                    type="danger"
                    plain
                    :loading="deletingRecordId === record.id"
                    @click="deleteCaptureRecord(record)"
                  >
                    删除
                  </el-button>
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
import { ElMessage, ElMessageBox } from 'element-plus'
import {
  captureCameraImages,
  deleteCameraCaptureRecord,
  deleteCameraCaptureStage,
  downloadCameraCaptures,
  saveCameraCaptureStages
} from '@/api/detection'
import CameraPreviewCard from '@/components/CameraPreviewCard.vue'
import { useCameraWorkspace } from '@/composables/useCameraWorkspace'

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
    const savingPending = ref(false)
    const downloadingZip = ref(false)
    const deletingRecordId = ref('')
    const deletingPendingStageId = ref('')
    const errorMessage = ref('')
    const selectedCaptureIds = ref([])
    const previewEnabled = ref(false)
    const pendingCaptureGroups = computed(() =>
      (state.stagedCaptureGroups || []).map((group, index) => ({
        ...group,
        displayName: `第${index + 1}组图片`
      }))
    )

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

    const recordTypeLabel = (record) => {
      if (record.capture_mode === 'bundle') return '照片压缩包'
      if (record.capture_mode === 'dual') return '双摄记录'
      return '单摄图片'
    }

    const recordTitle = (record) => {
      if (record.archive_name) return record.archive_name
      if (record.capture_mode === 'dual') return record.group_name || record.id
      return record.files?.[0]?.file_name || record.id
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

    const buildCapturePayload = () => {
      const selected = [...previewCameraIndices.value]
      const isDual = selected.length === 2
      return {
        selected,
        payload: {
          camera_indices: selected,
          capture_mode: isDual ? 'dual' : 'single',
          left_camera_index: isDual ? selected[0] : undefined,
          right_camera_index: isDual ? selected[1] : undefined,
          persist: false
        }
      }
    }

    const captureSelected = async () => {
      const { selected, payload } = buildCapturePayload()
      if (!selected.length) {
        errorMessage.value = '请先勾选至少一个用于拍照的摄像头'
        return
      }
      if (selected.length > 2) {
        errorMessage.value = '拍照仅支持单摄或双摄，请将预览设备控制在 1 到 2 个'
        return
      }

      capturing.value = true
      errorMessage.value = ''

      try {
        const response = await captureCameraImages(payload)
        await loadCaptureRecords()
        ElMessage.success(`拍照完成，已加入 ${response.staged_groups?.length || 0} 组待保存照片`)
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '拍照失败'
      } finally {
        capturing.value = false
      }
    }

    const savePendingCaptures = async () => {
      if (!pendingCaptureGroups.value.length) {
        return
      }
      savingPending.value = true
      errorMessage.value = ''
      try {
        const response = await saveCameraCaptureStages({
          stage_ids: pendingCaptureGroups.value.map((group) => group.stage_id)
        })
        selectedCaptureIds.value = []
        await loadCaptureRecords()
        ElMessage.success(`已保存 ${response.record?.group_count || 0} 组照片，ZIP 已加入结果栏`)
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '保存拍照结果失败'
      } finally {
        savingPending.value = false
      }
    }

    const deletePendingCaptureGroup = async (stageId) => {
      deletingPendingStageId.value = stageId
      errorMessage.value = ''
      try {
        await deleteCameraCaptureStage(stageId)
        await loadCaptureRecords()
        ElMessage.success('待保存照片组已删除')
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '删除待保存照片组失败'
      } finally {
        deletingPendingStageId.value = ''
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

    const deleteCaptureRecord = async (record) => {
      try {
        await ElMessageBox.confirm(
          `删除后将移除记录“${recordTitle(record)}”以及对应的 ZIP 和图片文件，是否继续？`,
          '删除拍照结果',
          {
            type: 'warning',
            confirmButtonText: '删除',
            cancelButtonText: '取消'
          }
        )
      } catch {
        return
      }

      deletingRecordId.value = record.id
      errorMessage.value = ''
      try {
        await deleteCameraCaptureRecord(record.id)
        selectedCaptureIds.value = selectedCaptureIds.value.filter((id) => id !== record.id)
        await loadCaptureRecords()
        ElMessage.success('拍照结果已删除')
      } catch (error) {
        errorMessage.value = error?.response?.data?.error || error.message || '删除拍照结果失败'
      } finally {
        deletingRecordId.value = ''
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
      deletingPendingStageId,
      downloadingZip,
      deletingRecordId,
      deletePendingCaptureGroup,
      downloadSelectedZip,
      deleteCaptureRecord,
      dualPairLabel,
      errorMessage,
      formatDateTime,
      lastScanText,
      loadCaptureRecords,
      localSelection,
      pendingCaptureGroups,
      previewCameraIndices,
      previewEnabled,
      recordTitle,
      recordTypeLabel,
      registry,
      saveCurrentSelection,
      savePendingCaptures,
      savingPending,
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
.capture-list,
.pending-list {
  display: grid;
  gap: 12px;
}

.device-row,
.capture-item,
.pending-item {
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

.pending-section {
  margin-top: 20px;
  display: grid;
  gap: 12px;
}

.pending-header,
.pending-title-row,
.capture-toolbar {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
}

.pending-header h3 {
  margin: 0;
  color: #173b32;
}

.pending-header span,
.pending-title-row span,
.pending-item p,
.capture-extra {
  color: #587166;
  font-size: 13px;
}

.pending-item {
  flex-direction: column;
}

.pending-title-row strong {
  color: #173b32;
}

.pending-item p {
  margin: 0;
}

.pending-title-actions {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.pending-remove {
  width: 28px;
  height: 28px;
  border: 0;
  border-radius: 50%;
  background: rgba(35, 80, 66, 0.1);
  color: #235042;
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

.pending-remove:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pending-files,
.capture-files {
  display: grid;
  gap: 6px;
}

.capture-toolbar {
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.capture-item {
  flex-direction: column;
}

.capture-item-actions {
  display: flex;
  justify-content: flex-end;
}

.capture-select {
  display: flex;
  gap: 8px;
  align-items: center;
  color: #35594d;
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
