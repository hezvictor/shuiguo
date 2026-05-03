<template>
  <div class="image-page">
    <div class="page-shell">
      <section class="hero card">
        <div>
          <p class="eyebrow">Image Detection Workspace</p>
          <h1>图片检测</h1>
          <p class="hero-text">
            单图片输入用于种类识别或种类 + 熟度识别；果径图片输入用于左右图果径测量；混合输入用于同时完成种类 + 熟度 + 果径。
          </p>
        </div>
        <div class="hero-stats">
          <span class="badge">单图 {{ singleInputs.length }}</span>
          <span class="badge">果径 {{ diameterInputs.length }}</span>
          <span class="badge">混合 {{ mixedInputs.length }}</span>
          <span class="badge">最近结果 {{ visibleRecords.length }}</span>
        </div>
      </section>

      <div v-if="errorMessage" class="error-banner">{{ errorMessage }}</div>

      <section class="workspace">
        <div class="main-column">
          <section class="card">
            <div class="section-head">
              <div>
                <h2>检测选项</h2>
                <p>勾选后，单图输入和混合输入会继续执行熟度识别。</p>
              </div>
            </div>
            <label class="checkbox-row">
              <input v-model="options.detectRipeness" type="checkbox" />
              <span>开启熟度检测</span>
            </label>
          </section>

          <section class="card">
            <div class="section-head">
              <div>
                <h2>单图片输入</h2>
                <p>支持图片和 ZIP。只上传这里时，只做种类/熟度，不做果径。</p>
              </div>
            </div>
            <div class="upload-box" @click="$refs.singleInput.click()">
              <strong>选择单图片或 ZIP</strong>
              <span>支持 JPG / PNG / WEBP / BMP / ZIP</span>
              <input ref="singleInput" type="file" multiple accept="image/*,.zip" hidden @change="onSingleInputsSelected" />
            </div>
            <div v-if="singleInputs.length" class="preview-grid">
              <article v-for="item in singleInputs" :key="item.uid" class="preview-card">
                <button class="remove-btn" @click.stop="removeSingleInput(item.uid)">×</button>
                <img v-if="item.previewUrl" :src="item.previewUrl" :alt="item.name" class="preview-image" />
                <div v-else class="archive-box">ZIP</div>
                <strong>{{ item.name }}</strong>
                <span>{{ item.kindLabel }} · {{ formatFileSize(item.size) }}</span>
              </article>
            </div>
          </section>

          <section class="card">
            <div class="section-head">
              <div>
                <h2>果径图片输入</h2>
                <p>支持左右图片直接上传，或按分组规则组织的 ZIP。只上传这里时，只做果径。</p>
              </div>
            </div>
            <div class="upload-box" @click="$refs.diameterInput.click()">
              <strong>选择果径图片或 ZIP</strong>
              <span>文件名需包含 left / right，或 ZIP 内按分组目录组织</span>
              <input ref="diameterInput" type="file" multiple accept="image/*,.zip" hidden @change="onDiameterInputsSelected" />
            </div>
            <div v-if="diameterInputs.length" class="preview-grid">
              <article v-for="item in diameterInputs" :key="item.uid" class="preview-card">
                <button class="remove-btn" @click.stop="removeDiameterInput(item.uid)">×</button>
                <img v-if="item.previewUrl" :src="item.previewUrl" :alt="item.name" class="preview-image" />
                <div v-else class="archive-box">ZIP</div>
                <strong>{{ item.name }}</strong>
                <span>{{ item.kindLabel }} · {{ formatFileSize(item.size) }}</span>
              </article>
            </div>
          </section>

          <section class="card">
            <div class="section-head">
              <div>
                <h2>混合输入</h2>
                <p>只支持 ZIP。每组数据包含左图和右图；默认右图为彩图，左图为黑白图。</p>
              </div>
            </div>
            <div class="upload-box" @click="$refs.mixedInput.click()">
              <strong>选择混合 ZIP</strong>
              <span>后端会先对右图原图做 YOLO，再合并种类、熟度和果径结果</span>
              <input ref="mixedInput" type="file" multiple accept=".zip" hidden @change="onMixedInputsSelected" />
            </div>
            <div v-if="mixedInputs.length" class="preview-grid">
              <article v-for="item in mixedInputs" :key="item.uid" class="preview-card">
                <button class="remove-btn" @click.stop="removeMixedInput(item.uid)">×</button>
                <div class="archive-box">ZIP</div>
                <strong>{{ item.name }}</strong>
                <span>{{ item.kindLabel }} · {{ formatFileSize(item.size) }}</span>
              </article>
            </div>
          </section>

          <section class="card action-card">
            <button class="btn primary" :disabled="submitting" @click="submitTask">
              {{ submitting ? '检测中...' : '开始检测并生成报告' }}
            </button>
            <button class="btn" :disabled="submitting" @click="resetPendingUploads">清空待上传</button>
            <button class="btn" :disabled="loadingRecent" @click="fetchRecentResults">刷新最近结果</button>
          </section>

          <section v-if="taskProgressVisible" class="card progress-card">
            <div class="section-head">
              <div>
                <h2>任务进度</h2>
                <p>{{ taskProgressDescription }}</p>
              </div>
              <strong>{{ taskProgressPercentText }}</strong>
            </div>
            <div class="progress-track">
              <div class="progress-fill" :style="{ width: `${taskProgressPercent}%` }"></div>
            </div>
            <p class="progress-meta">
              已处理 {{ taskProcessedItems }} / {{ taskTotalItems }}
              <span v-if="taskCurrentLabel"> · 当前 {{ taskCurrentLabel }}</span>
              <span> · 状态 {{ taskStatusLabel }}</span>
            </p>
          </section>
        </div>

        <aside class="side-column">
          <section class="card">
            <div class="section-head">
              <div>
                <h2>最近结果</h2>
                <p>结果来自后端历史记录。</p>
              </div>
              <button v-if="dismissedIds.length" class="btn small" @click="restoreDismissed">恢复隐藏 {{ dismissedIds.length }}</button>
            </div>
            <div v-if="loadingRecent" class="empty-state">正在加载...</div>
            <div v-else-if="visibleRecords.length" class="result-list">
              <article v-for="record in visibleRecords" :key="record.id" class="result-card">
                <button class="remove-btn" @click="dismissRecord(record.id)">×</button>
                <div class="result-top">
                  <strong>{{ compactTitle(record) }}</strong>
                  <span>{{ formatDateTime(record.created_at) }}</span>
                </div>
                <div class="tag-row">
                  <span class="tag">{{ sourceLabel(record) }}</span>
                  <span v-for="tag in operationTags(record)" :key="`${record.id}-${tag}`" class="tag accent">{{ tag }}</span>
                </div>
                <p class="summary-text">{{ compactSummary(record) }}</p>
                <div class="action-row">
                  <button class="btn small" @click="viewDetail(record)">查看详情</button>
                  <button v-if="record.report_file || record.report_url" class="btn small primary" @click="downloadReport(record)">下载报告</button>
                  <button class="btn small" @click="goToHistory">历史记录</button>
                </div>
              </article>
            </div>
            <div v-else class="empty-state">暂无结果</div>
          </section>
        </aside>
      </section>

      <el-dialog v-model="detailVisible" title="图片检测详情" width="88%" :close-on-click-modal="false">
        <div v-if="currentDetail" class="detail-shell">
          <p><strong>标题：</strong>{{ currentDetail.title || `图片检测 #${currentDetail.id}` }}</p>
          <p><strong>时间：</strong>{{ formatDateTime(currentDetail.created_at) }}</p>
          <p><strong>状态：</strong>{{ currentDetail.status_display || currentDetail.status }}</p>
          <p><strong>目标总数：</strong>{{ currentDetail.summary?.total_targets ?? 0 }}</p>

          <div v-for="(item, index) in normalizedDetailItems" :key="`${item.display_name}-${index}`" class="detail-item">
            <div class="section-head">
              <div>
                <h3>{{ item.display_name }}</h3>
                <p>{{ detailTypeLabel(item.item_type) }}</p>
              </div>
            </div>
            <div class="detail-images">
              <figure v-if="item.originalImageUrl">
                <img :src="item.originalImageUrl" alt="original" />
                <figcaption>左图 / 原图</figcaption>
              </figure>
              <figure v-if="item.rightImageUrl">
                <img :src="item.rightImageUrl" alt="right" />
                <figcaption>右图</figcaption>
              </figure>
              <figure v-if="item.annotatedImageUrl">
                <img :src="item.annotatedImageUrl" alt="annotated" />
                <figcaption>检测结果图</figcaption>
              </figure>
            </div>

            <el-table :data="item.targets || []" border style="width: 100%">
              <el-table-column label="边界框" min-width="160">
                <template #default="{ row }">[{{ (row.bbox || []).join(', ') }}]</template>
              </el-table-column>
              <el-table-column label="种类" min-width="140">
                <template #default="{ row }">{{ translateFruitLabel(row.classification?.class) }}</template>
              </el-table-column>
              <el-table-column label="熟度" min-width="160">
                <template #default="{ row }">{{ translateRipenessLabel(row.ripeness?.predicted_class) }}</template>
              </el-table-column>
              <el-table-column label="果径(mm)" width="120">
                <template #default="{ row }">{{ formatDiameter(row.diameter?.distance_mm) }}</template>
              </el-table-column>
              <el-table-column label="状态" min-width="120">
                <template #default="{ row }">{{ row.diameter?.status || 'ok' }}</template>
              </el-table-column>
            </el-table>
          </div>
        </div>
        <template #footer>
          <div class="detail-actions">
            <button class="btn" @click="closeDetailDialog">退出界面</button>
          </div>
        </template>
      </el-dialog>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { createImageDetectionTask, getDetectionHistoryDetail, getDetectionHistoryList } from '@/api/detection'
import { dismissHistoryId, loadDismissedIds, restoreHistoryId, saveDismissedIds } from '@/utils/imageDetectionWorkspace'
import { translateFruitLabel, translateRipenessLabel } from '@/utils/labelMap'

export default {
  name: 'ImageDetectionView',
  data() {
    return {
      singleInputs: [],
      diameterInputs: [],
      mixedInputs: [],
      options: {
        detectRipeness: true
      },
      submitting: false,
      loadingRecent: false,
      taskPolling: false,
      activeTaskId: null,
      activeTaskDetail: null,
      taskPollTimer: null,
      errorMessage: '',
      recentRecords: [],
      dismissedIds: [],
      detailVisible: false,
      currentDetail: null
    }
  },
  computed: {
    visibleRecords() {
      return this.recentRecords.filter((item) => !this.dismissedIds.includes(item.id))
    },
    normalizedDetailItems() {
      const items = this.currentDetail?.detail_data?.items || []
      return items.map((item) => ({
        ...item,
        originalImageUrl: this.resolveMediaUrl(item.original_image),
        rightImageUrl: this.resolveMediaUrl(item.right_image),
        annotatedImageUrl: this.resolveMediaUrl(item.annotated_image)
      }))
    },
    activeTaskProgress() {
      return this.activeTaskDetail?.detail_data?.progress || this.activeTaskDetail?.summary?.progress || null
    },
    taskProgressVisible() {
      return Boolean(this.activeTaskId && this.activeTaskProgress)
    },
    taskProcessedItems() {
      return Number(this.activeTaskProgress?.processed_items || 0)
    },
    taskTotalItems() {
      return Number(this.activeTaskProgress?.total_items || this.activeTaskDetail?.input_count || 0)
    },
    taskProgressPercent() {
      return Number(this.activeTaskProgress?.progress_percent || 0)
    },
    taskProgressPercentText() {
      return `${this.taskProgressPercent.toFixed(0)}%`
    },
    taskCurrentLabel() {
      return this.activeTaskProgress?.current_item_label || ''
    },
    taskStatusLabel() {
      return this.activeTaskDetail?.status_display || this.activeTaskDetail?.status || '-'
    },
    taskProgressDescription() {
      if (!this.activeTaskDetail) return '正在准备任务...'
      if (this.taskCurrentLabel) return `正在处理：${this.taskCurrentLabel}`
      if (this.isTaskTerminalStatus(this.activeTaskDetail.status)) return '任务已完成，结果已写入历史记录。'
      return '后台正在顺序处理输入组。'
    }
  },
  mounted() {
    this.dismissedIds = loadDismissedIds()
    this.fetchRecentResults()
  },
  beforeUnmount() {
    this.stopTaskPolling()
    this.resetPendingUploads()
  },
  methods: {
    onSingleInputsSelected(event) {
      const files = Array.from(event.target.files || [])
      files.forEach((file) => {
        if (!this.isSupportedUpload(file)) return
        this.singleInputs.push(this.buildUploadItem(file))
      })
      event.target.value = ''
    },
    onDiameterInputsSelected(event) {
      const files = Array.from(event.target.files || [])
      files.forEach((file) => {
        if (!this.isSupportedUpload(file)) return
        this.diameterInputs.push(this.buildUploadItem(file))
      })
      event.target.value = ''
    },
    onMixedInputsSelected(event) {
      const files = Array.from(event.target.files || [])
      files.forEach((file) => {
        if (!this.isArchiveFile(file)) return
        this.mixedInputs.push(this.buildUploadItem(file))
      })
      event.target.value = ''
    },
    isSupportedUpload(file) {
      const lowerName = String(file.name || '').toLowerCase()
      return lowerName.endsWith('.zip') || file.type.startsWith('image/')
    },
    isArchiveFile(file) {
      return String(file.name || '').toLowerCase().endsWith('.zip')
    },
    buildUploadItem(file) {
      const isArchive = this.isArchiveFile(file)
      return {
        uid: `${Date.now()}_${Math.random().toString(16).slice(2)}`,
        file,
        name: file.name,
        size: file.size,
        isArchive,
        previewUrl: !isArchive && file.type.startsWith('image/') ? URL.createObjectURL(file) : '',
        kindLabel: isArchive ? 'ZIP' : '图片'
      }
    },
    removeSingleInput(uid) {
      const target = this.singleInputs.find((item) => item.uid === uid)
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
      this.singleInputs = this.singleInputs.filter((item) => item.uid !== uid)
    },
    removeDiameterInput(uid) {
      const target = this.diameterInputs.find((item) => item.uid === uid)
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
      this.diameterInputs = this.diameterInputs.filter((item) => item.uid !== uid)
    },
    removeMixedInput(uid) {
      const target = this.mixedInputs.find((item) => item.uid === uid)
      if (target?.previewUrl) URL.revokeObjectURL(target.previewUrl)
      this.mixedInputs = this.mixedInputs.filter((item) => item.uid !== uid)
    },
    async submitTask() {
      this.errorMessage = ''
      if (!this.singleInputs.length && !this.diameterInputs.length && !this.mixedInputs.length) {
        this.errorMessage = '请至少上传单图片输入、果径图片输入或混合 ZIP。'
        return
      }

      const formData = new FormData()
      formData.append('detect_ripeness', this.options.detectRipeness ? 'true' : 'false')
      this.singleInputs.forEach((item) => formData.append('single_inputs', item.file))
      this.diameterInputs.forEach((item) => formData.append('diameter_inputs', item.file))
      this.mixedInputs.forEach((item) => formData.append('mixed_inputs', item.file))

      this.submitting = true
      try {
        const res = await createImageDetectionTask(formData)
        this.activeTaskId = res.history_id
        this.activeTaskDetail = {
          id: res.history_id,
          title: res.title,
          status: res.task_status,
          summary: res.summary,
          detail_data: res.detail_data,
          input_count: res.summary?.input_count || this.singleInputs.length + this.diameterInputs.length + this.mixedInputs.length
        }
        this.startTaskPolling(res.history_id)
        restoreHistoryId(res.history_id)
        this.dismissedIds = loadDismissedIds()
        this.resetPendingUploads()
        await this.fetchRecentResults()
        ElMessage.success('图片检测任务已创建。')
      } catch (error) {
        console.error('create image detection task failed', error)
        this.errorMessage = error?.response?.data?.error || error.message || '图片检测失败，请稍后重试。'
      } finally {
        this.submitting = false
      }
    },
    async fetchRecentResults() {
      this.loadingRecent = true
      try {
        const res = await getDetectionHistoryList({
          detection_type: 'image',
          page: 1,
          page_size: 20
        })
        this.recentRecords = (res.results || res || []).map((item) => ({ ...item }))
        this.resumePendingTaskPolling()
        this.errorMessage = ''
      } catch (error) {
        console.error('load recent image detection records failed', error)
        this.errorMessage = '获取最近图片检测结果失败。'
      } finally {
        this.loadingRecent = false
      }
    },
    dismissRecord(id) {
      this.dismissedIds = dismissHistoryId(id)
    },
    isTaskActiveStatus(status) {
      return ['pending', 'running'].includes(status)
    },
    isTaskTerminalStatus(status) {
      return ['completed', 'partial', 'failed'].includes(status)
    },
    updateRecentRecord(detail) {
      const index = this.recentRecords.findIndex((item) => item.id === detail.id)
      if (index >= 0) {
        this.recentRecords.splice(index, 1, { ...this.recentRecords[index], ...detail })
        return
      }
      this.recentRecords = [detail, ...this.recentRecords]
    },
    stopTaskPolling() {
      this.taskPolling = false
      if (this.taskPollTimer) {
        window.clearTimeout(this.taskPollTimer)
        this.taskPollTimer = null
      }
    },
    scheduleTaskPoll(delay = 1200) {
      this.stopTaskPolling()
      if (!this.activeTaskId) return
      this.taskPolling = true
      this.taskPollTimer = window.setTimeout(() => {
        this.pollTaskDetail()
      }, delay)
    },
    startTaskPolling(historyId) {
      this.stopTaskPolling()
      this.activeTaskId = historyId
      this.pollTaskDetail()
    },
    resumePendingTaskPolling() {
      if (this.activeTaskId && this.isTaskActiveStatus(this.activeTaskDetail?.status)) {
        if (!this.taskPolling) this.scheduleTaskPoll()
        return
      }
      const pendingRecord = this.recentRecords.find((item) => this.isTaskActiveStatus(item.status))
      if (!pendingRecord) return
      this.activeTaskId = pendingRecord.id
      if (!this.activeTaskDetail || this.activeTaskDetail.id !== pendingRecord.id) {
        this.activeTaskDetail = pendingRecord
      }
      if (!this.taskPolling) this.scheduleTaskPoll(200)
    },
    async pollTaskDetail() {
      if (!this.activeTaskId) return
      this.taskPolling = false
      try {
        const detail = await getDetectionHistoryDetail(this.activeTaskId)
        this.activeTaskDetail = detail
        this.updateRecentRecord(detail)
        if (this.isTaskActiveStatus(detail.status)) {
          this.scheduleTaskPoll()
          return
        }
        await this.fetchRecentResults()
        if (detail.status === 'completed') ElMessage.success('图片检测任务已完成。')
        if (detail.status === 'partial') ElMessage.warning('图片检测任务已完成，但部分输入处理失败。')
        if (detail.status === 'failed') ElMessage.error('图片检测任务执行失败。')
      } catch (error) {
        console.error('poll image detection task failed', error)
        if (this.activeTaskId) this.scheduleTaskPoll(2000)
      }
    },
    restoreDismissed() {
      this.dismissedIds = []
      saveDismissedIds([])
    },
    async viewDetail(record) {
      try {
        this.currentDetail = await getDetectionHistoryDetail(record.id)
        this.detailVisible = true
      } catch (error) {
        console.error('load image detection detail failed', error)
        ElMessage.error('获取详情失败')
      }
    },
    closeDetailDialog() {
      this.detailVisible = false
      this.currentDetail = null
    },
    downloadReport(record) {
      const targetUrl = record.report_url || this.resolveMediaUrl(record.report_file)
      if (!targetUrl) {
        ElMessage.warning('该记录没有可下载的报告文件。')
        return
      }
      const anchor = document.createElement('a')
      anchor.href = targetUrl
      anchor.download = (record.report_file || 'image_detection_report.xlsx').split('/').pop()
      document.body.appendChild(anchor)
      anchor.click()
      document.body.removeChild(anchor)
    },
    goToHistory() {
      this.$router.push('/history')
    },
    resolveMediaUrl(path) {
      if (!path) return ''
      if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/media/')) return path
      return `/media/${String(path).replace(/^\/+/, '')}`
    },
    resetPendingUploads() {
      ;[...this.singleInputs, ...this.diameterInputs, ...this.mixedInputs].forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl)
      })
      this.singleInputs = []
      this.diameterInputs = []
      this.mixedInputs = []
    },
    formatDateTime(value) {
      return value ? new Date(value).toLocaleString('zh-CN') : '-'
    },
    formatFileSize(size) {
      if (!size) return '0 B'
      if (size < 1024) return `${size} B`
      if (size < 1024 * 1024) return `${(size / 1024).toFixed(1)} KB`
      return `${(size / (1024 * 1024)).toFixed(2)} MB`
    },
    formatDiameter(value) {
      return value === null || value === undefined ? '-' : Number(value).toFixed(2)
    },
    compactTitle(record) {
      const title = record.title || `图片检测 #${record.id}`
      return title.length > 26 ? `${title.slice(0, 26)}...` : title
    },
    sourceLabel(record) {
      return record.options?.source === 'stereo_camera' ? '双目相机' : '上传文件'
    },
    operationTags(record) {
      const tags = []
      if (record.options?.detect_classification) tags.push('种类')
      if (record.options?.detect_ripeness) tags.push('熟度')
      if (record.options?.detect_diameter) tags.push('果径')
      if (record.options?.has_mixed_inputs) tags.push('混合')
      return tags.length ? tags : ['检测']
    },
    compactSummary(record) {
      if (this.isTaskActiveStatus(record.status)) {
        const progress = record.summary?.progress || {}
        return `已处理 ${progress.processed_items || 0} / ${progress.total_items || record.input_count || 0} · ${Number(
          progress.progress_percent || 0
        ).toFixed(0)}%`
      }
      const summary = record.summary || {}
      const parts = [`输入 ${record.input_count ?? summary.input_count ?? 0}`, `目标 ${summary.total_targets ?? 0}`]
      if (summary.valid_measurements) parts.push(`有效果径 ${summary.valid_measurements}`)
      return parts.join(' · ')
    },
    detailTypeLabel(itemType) {
      if (itemType === 'diameter_group') return '果径图片组'
      if (itemType === 'mixed_group') return '混合图片组'
      if (itemType === 'camera_diameter') return '双目实时果径测量'
      return '单图片输入'
    },
    translateFruitLabel,
    translateRipenessLabel
  }
}
</script>

<style scoped>
.image-page {
  padding: 20px;
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(44, 123, 83, 0.16), transparent 26%),
    linear-gradient(180deg, #f4f8f5 0%, #edf3ef 100%);
}

.page-shell {
  max-width: 1320px;
  margin: 0 auto;
  display: grid;
  gap: 16px;
}

.card {
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 20px 42px rgba(27, 51, 40, 0.08);
  padding: 20px;
}

.hero {
  display: grid;
  gap: 20px;
  grid-template-columns: minmax(0, 1.3fr) auto;
}

.eyebrow {
  margin: 0 0 8px;
  letter-spacing: 0.1em;
  text-transform: uppercase;
  color: #3d8063;
  font-weight: 700;
  font-size: 12px;
}

h1,
h2,
h3,
p {
  margin: 0;
}

.hero-text {
  margin-top: 10px;
  color: #4a5a52;
  line-height: 1.7;
}

.hero-stats {
  display: grid;
  gap: 10px;
  align-content: start;
}

.badge,
.tag {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  border-radius: 999px;
  padding: 8px 14px;
  background: #eef5f1;
  color: #25503c;
  font-size: 13px;
  font-weight: 600;
}

.tag-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.tag.accent {
  background: #dff2e8;
}

.error-banner {
  border-radius: 16px;
  background: #ffe4e4;
  color: #b03333;
  padding: 14px 16px;
  font-weight: 600;
}

.workspace {
  display: grid;
  gap: 16px;
  grid-template-columns: minmax(0, 1.55fr) minmax(320px, 0.85fr);
}

.main-column,
.side-column {
  display: grid;
  gap: 16px;
  align-content: start;
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 14px;
}

.section-head p {
  color: #5b6c63;
  line-height: 1.6;
}

.checkbox-row {
  display: inline-flex;
  align-items: center;
  gap: 10px;
  font-weight: 600;
}

.upload-box {
  border: 1px dashed #89b89e;
  border-radius: 18px;
  padding: 24px;
  cursor: pointer;
  display: grid;
  gap: 6px;
  background: linear-gradient(180deg, rgba(239, 247, 243, 0.9) 0%, rgba(250, 252, 250, 0.95) 100%);
}

.upload-box:hover {
  border-color: #3d8063;
}

.preview-grid {
  margin-top: 16px;
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fill, minmax(160px, 1fr));
}

.preview-card,
.result-card {
  position: relative;
  border-radius: 18px;
  border: 1px solid #e2ece5;
  background: #fff;
  padding: 14px;
  display: grid;
  gap: 8px;
}

.preview-card strong,
.result-card strong {
  word-break: break-all;
}

.preview-image,
.detail-images img {
  width: 100%;
  border-radius: 14px;
  object-fit: cover;
}

.archive-box {
  min-height: 120px;
  border-radius: 14px;
  display: grid;
  place-items: center;
  background: #eef5f1;
  color: #2f654d;
  font-weight: 700;
}

.remove-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 999px;
  background: rgba(14, 36, 27, 0.75);
  color: #fff;
  cursor: pointer;
}

.action-card,
.action-row {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
}

.btn {
  border: none;
  border-radius: 999px;
  padding: 10px 16px;
  background: #eef5f1;
  color: #204d38;
  cursor: pointer;
  font-weight: 600;
}

.btn.primary {
  background: linear-gradient(135deg, #2d7d59 0%, #4b9d75 100%);
  color: #fff;
}

.btn.small {
  padding: 8px 12px;
  font-size: 12px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.result-list {
  display: grid;
  gap: 12px;
}

.result-top,
.progress-meta,
.summary-text {
  color: #4c5d55;
}

.empty-state {
  color: #62746b;
  text-align: center;
  padding: 24px 0;
}

.progress-track {
  width: 100%;
  height: 10px;
  border-radius: 999px;
  background: #edf2ef;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  background: linear-gradient(90deg, #2d7d59 0%, #6cbc96 100%);
}

.detail-shell {
  display: grid;
  gap: 18px;
}

.detail-actions {
  display: flex;
  justify-content: flex-end;
}

.detail-item {
  display: grid;
  gap: 14px;
}

.detail-images {
  display: grid;
  gap: 12px;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
}

.detail-images figure {
  margin: 0;
  display: grid;
  gap: 8px;
}

.detail-images figcaption {
  color: #586961;
  font-size: 13px;
}

@media (max-width: 980px) {
  .hero,
  .workspace {
    grid-template-columns: 1fr;
  }
}
</style>
