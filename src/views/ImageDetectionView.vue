<template>
  <div class="image-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Image Detection Workspace</p>
          <h1>图片检测</h1>
          <p class="hero-text">
            页面包含两个输入框。单图片输入用于水果种类识别，或水果种类识别加熟度识别；果径图片输入用于左右图成组的果径测量。
            两个输入框都支持直接上传图片，也支持上传压缩包后批量检测。
          </p>
        </div>
        <div class="hero-status">
          <div class="hero-badge">单图片输入：{{ singleInputs.length }} 项</div>
          <div class="hero-badge">果径图片输入：{{ diameterInputs.length }} 项</div>
          <div class="hero-badge">最近结果：{{ visibleRecords.length }} 条</div>
        </div>
      </section>

      <div v-if="errorMessage" class="error-banner">
        <strong>处理失败</strong>
        <span>{{ errorMessage }}</span>
      </div>

      <section class="workspace-grid">
        <div class="workspace-main">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>检测选项</h2>
                <p>单图片输入默认执行水果种类识别；如需同时识别熟度，请勾选下面的选项。果径检测是否执行由是否上传果径输入决定。</p>
              </div>
            </div>

            <div class="option-grid option-grid--single">
              <label class="option-item">
                <input type="checkbox" v-model="options.detectRipeness" />
                <span>单图片同时进行熟度检测</span>
              </label>
            </div>
          </section>

          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>单图片输入</h2>
                <p>支持上传单张或多张图片，也支持上传文件夹压缩包。压缩包中的所有可识别图片都会参与检测。</p>
              </div>
            </div>

            <div class="upload-area" @click="$refs.singleInput.click()">
              <div class="upload-content">
                <span class="upload-icon">图</span>
                <p class="upload-text">点击选择单图片或压缩包</p>
                <p class="upload-hint">支持 JPG / PNG / WEBP / BMP / ZIP，可一次选择多个文件</p>
              </div>
              <input
                ref="singleInput"
                type="file"
                multiple
                accept="image/*,.zip"
                style="display: none"
                @change="onSingleInputsSelected"
              />
            </div>

            <div v-if="singleInputs.length" class="preview-grid">
              <article v-for="item in singleInputs" :key="item.uid" class="preview-card">
                <button class="remove-btn" @click.stop="removeSingleInput(item.uid)">×</button>
                <div v-if="item.previewUrl" class="preview-visual">
                  <img :src="item.previewUrl" :alt="item.name" class="preview-image" />
                </div>
                <div v-else class="archive-placeholder">ZIP</div>
                <div class="preview-meta">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.kindLabel }} · {{ formatFileSize(item.size) }}</span>
                </div>
              </article>
            </div>
          </section>

          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>果径图片输入</h2>
                <p>
                  直接上传时，文件名需包含 left 或 right，系统会自动配对；上传压缩包时，要求一级目录下只包含文件夹，每个二级目录内必须恰好有一张 left 图和一张 right 图。
                </p>
              </div>
            </div>

            <div class="upload-area" @click="$refs.diameterInput.click()">
              <div class="upload-content">
                <span class="upload-icon">径</span>
                <p class="upload-text">点击选择果径图片或压缩包</p>
                <p class="upload-hint">支持左右图图片或 ZIP；ZIP 内部目录结构必须符合果径分组规则</p>
              </div>
              <input
                ref="diameterInput"
                type="file"
                multiple
                accept="image/*,.zip"
                style="display: none"
                @change="onDiameterInputsSelected"
              />
            </div>

            <div v-if="diameterInputs.length" class="preview-grid">
              <article v-for="item in diameterInputs" :key="item.uid" class="preview-card">
                <button class="remove-btn" @click.stop="removeDiameterInput(item.uid)">×</button>
                <div v-if="item.previewUrl" class="preview-visual">
                  <img :src="item.previewUrl" :alt="item.name" class="preview-image" />
                </div>
                <div v-else class="archive-placeholder">{{ item.isArchive ? 'ZIP' : '图' }}</div>
                <div class="preview-meta">
                  <strong>{{ item.name }}</strong>
                  <span>{{ item.kindLabel }} · {{ formatFileSize(item.size) }}</span>
                </div>
              </article>
            </div>
            <div v-else class="empty-inline-tip">当前未上传果径输入；如果没有果径数据，开始检测时将自动跳过果径测量。</div>
          </section>

          <section class="panel-card">
            <div class="action-row">
              <button class="btn btn-primary" :disabled="submitting" @click="submitTask">
                {{ submitting ? '检测中...' : '开始检测并生成报告' }}
              </button>
              <button class="btn btn-secondary" :disabled="submitting" @click="resetPendingUploads">清空待上传</button>
              <button class="btn btn-secondary" :disabled="loadingRecent" @click="fetchRecentResults">刷新最近结果</button>
            </div>
          </section>
        </div>

        <div class="workspace-side">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>最近图片检测结果</h2>
                <p>这些记录来自后端检测历史；关闭当前页面后仍会保留。</p>
              </div>
              <button v-if="dismissedIds.length" class="btn btn-secondary btn-mini" @click="restoreDismissed">
                恢复隐藏 {{ dismissedIds.length }}
              </button>
            </div>

            <div v-if="loadingRecent" class="empty-inline-tip">正在加载最近结果...</div>
            <div v-else-if="visibleRecords.length" class="result-list">
              <article v-for="record in visibleRecords" :key="record.id" class="result-card">
                <button class="remove-btn" @click="dismissRecord(record.id)">×</button>
                <div class="result-main">
                  <div class="result-copy">
                    <strong>{{ compactTitle(record) }}</strong>
                    <div class="result-tags">
                      <span class="result-tag">{{ sourceLabel(record) }}</span>
                      <span
                        v-for="tag in operationTags(record)"
                        :key="`${record.id}-${tag}`"
                        class="result-tag result-tag--accent"
                      >
                        {{ tag }}
                      </span>
                    </div>
                    <span>{{ formatDateTime(record.created_at) }}</span>
                    <span>{{ compactSummary(record) }}</span>
                  </div>
                  <div class="result-actions">
                    <button class="btn btn-secondary btn-mini" @click="viewDetail(record)">查看详情</button>
                    <button
                      v-if="record.report_file || record.report_url"
                      class="btn btn-success btn-mini"
                      @click="downloadReport(record)"
                    >
                      下载报告
                    </button>
                    <button class="btn btn-secondary btn-mini" @click="goToHistory">检测历史</button>
                  </div>
                </div>

                <div class="result-source-panel">
                  <span class="result-source-label">输入源</span>
                  <div v-if="record.source_entries?.length" class="result-source-list">
                    <template v-for="(entry, index) in record.source_entries" :key="`${record.id}-source-${index}`">
                      <a
                        v-if="entry.url"
                        class="result-source-chip result-source-chip--link"
                        :href="entry.url"
                        target="_blank"
                        rel="noopener"
                      >
                        {{ entry.label }}
                      </a>
                      <span v-else class="result-source-chip">
                        {{ entry.label }}
                      </span>
                    </template>
                  </div>
                  <span v-else class="result-source-empty">暂无输入源名称</span>
                </div>
              </article>
            </div>
            <div v-else class="empty-inline-tip">暂无图片检测结果，提交一次任务后会显示在这里。</div>
          </section>
        </div>
      </section>

      <el-dialog v-model="detailVisible" title="图片检测详情" width="88%" :close-on-click-modal="false">
        <div v-if="currentDetail" class="detail-shell">
          <div class="detail-summary">
            <p><strong>任务标题：</strong>{{ currentDetail.title || `图片检测 #${currentDetail.id}` }}</p>
            <p><strong>检测时间：</strong>{{ formatDateTime(currentDetail.created_at) }}</p>
            <p><strong>任务状态：</strong>{{ currentDetail.status_display || currentDetail.status }}</p>
            <p><strong>目标总数：</strong>{{ currentDetail.summary?.total_targets ?? 0 }}</p>
          </div>

          <div
            v-for="(item, index) in normalizedDetailItems"
            :key="`${item.display_name}-${index}`"
            class="detail-item"
          >
            <div class="panel-header">
              <div>
                <h2>{{ item.display_name }}</h2>
                <p>
                  {{ detailTypeLabel(item.item_type) }}
                  <span v-if="item.archive_name"> · {{ item.archive_name }}</span>
                  <span v-if="item.archive_path"> · {{ item.archive_path }}</span>
                </p>
              </div>
            </div>

            <div class="detail-image-grid">
              <figure v-if="item.originalImageUrl" class="detail-figure">
                <img :src="item.originalImageUrl" alt="original" class="detail-image" />
                <figcaption>原图</figcaption>
              </figure>
              <figure v-if="item.rightImageUrl" class="detail-figure">
                <img :src="item.rightImageUrl" alt="right original" class="detail-image" />
                <figcaption>右图</figcaption>
              </figure>
              <figure v-if="item.annotatedImageUrl" class="detail-figure">
                <img :src="item.annotatedImageUrl" alt="annotated" class="detail-image" />
                <figcaption>检测结果</figcaption>
              </figure>
            </div>

            <el-table :data="item.targets || []" border style="width: 100%">
              <el-table-column prop="target_index" label="目标序号" width="90" />
              <el-table-column label="边界框" min-width="150">
                <template #default="{ row }">[{{ (row.bbox || []).join(', ') }}]</template>
              </el-table-column>
              <el-table-column label="种类" min-width="140">
                <template #default="{ row }">{{ row.classification?.class || '-' }}</template>
              </el-table-column>
              <el-table-column label="熟度" min-width="180">
                <template #default="{ row }">{{ row.ripeness?.predicted_class || '-' }}</template>
              </el-table-column>
              <el-table-column label="果径(mm)" width="110">
                <template #default="{ row }">{{ formatDiameter(row.diameter?.distance_mm) }}</template>
              </el-table-column>
              <el-table-column label="状态" min-width="120">
                <template #default="{ row }">{{ row.diameter?.status || 'ok' }}</template>
              </el-table-column>
            </el-table>
          </div>

          <div class="detail-footer">
            <button class="btn btn-secondary" @click="detailVisible = false">关闭窗口</button>
          </div>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import {
  createImageDetectionTask,
  getDetectionHistoryDetail,
  getDetectionHistoryList
} from '@/api/detection'
import { dismissHistoryId, loadDismissedIds, restoreHistoryId, saveDismissedIds } from '@/utils/imageDetectionWorkspace'

export default {
  name: 'ImageDetectionView',
  data() {
    return {
      singleInputs: [],
      diameterInputs: [],
      options: {
        detectRipeness: true
      },
      submitting: false,
      loadingRecent: false,
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
    }
  },
  mounted() {
    this.dismissedIds = loadDismissedIds()
    this.fetchRecentResults()
  },
  beforeUnmount() {
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
        kindLabel: isArchive ? '压缩包' : '图片'
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
    async submitTask() {
      this.errorMessage = ''

      if (!this.singleInputs.length && !this.diameterInputs.length) {
        this.errorMessage = '请至少上传单图片输入或果径图片输入。'
        return
      }

      const formData = new FormData()
      formData.append('detect_ripeness', this.options.detectRipeness ? 'true' : 'false')

      this.singleInputs.forEach((item) => {
        formData.append('single_inputs', item.file)
      })
      this.diameterInputs.forEach((item) => {
        formData.append('diameter_inputs', item.file)
      })

      this.submitting = true
      try {
        const res = await createImageDetectionTask(formData)
        restoreHistoryId(res.history_id)
        this.dismissedIds = loadDismissedIds()
        this.resetPendingUploads()
        await this.fetchRecentResults()
        ElMessage.success('图片检测完成，结果已写入检测历史。')
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
        this.recentRecords = (res.results || res || []).map((item) => ({
          ...item
        }))
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
    resolveRecordCover(record) {
      return record.cover_image_url || this.resolveMediaUrl(record.cover_image)
    },
    resetPendingUploads() {
      this.singleInputs.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl)
      })
      this.diameterInputs.forEach((item) => {
        if (item.previewUrl) URL.revokeObjectURL(item.previewUrl)
      })
      this.singleInputs = []
      this.diameterInputs = []
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
      return tags.length ? tags : ['检测']
    },
    compactSummary(record) {
      const summary = record.summary || {}
      const parts = [
        `输入 ${record.input_count ?? summary.input_count ?? 0} 项`,
        `目标 ${summary.total_targets ?? 0} 个`
      ]
      if (summary.valid_measurements) parts.push(`有效果径 ${summary.valid_measurements} 个`)
      return parts.join(' · ')
    },
    detailTypeLabel(itemType) {
      if (itemType === 'diameter_group') return '果径图片组'
      if (itemType === 'camera_diameter') return '双目实时果径测量'
      return '单图片输入'
    }
  }
}
</script>

<style scoped>
.image-page {
  padding: 16px;
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

.hero,
.panel-card {
  border-radius: 24px;
  border: none;
  background: rgba(255, 255, 255, 0.95);
  box-shadow: 0 20px 42px rgba(27, 51, 40, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.5fr) minmax(260px, 0.7fr);
  gap: 18px;
  padding: 22px 24px;
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
  font-size: 30px;
  line-height: 1.1;
}

.hero-text {
  margin: 10px 0 0;
  line-height: 1.65;
  font-size: 14px;
  color: rgba(246, 251, 248, 0.86);
}

.hero-status {
  display: grid;
  gap: 12px;
  align-content: start;
}

.hero-badge {
  min-height: 38px;
  display: flex;
  align-items: center;
  padding: 0 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 13px;
}

.error-banner {
  display: flex;
  gap: 12px;
  align-items: center;
  padding: 14px 16px;
  border-radius: 18px;
  background: #fef3f2;
  border: 1px solid #fecdca;
  color: #b42318;
}

.workspace-grid {
  display: grid;
  grid-template-columns: minmax(0, 1.35fr) 360px;
  gap: 16px;
  align-items: start;
}

.workspace-main,
.workspace-side {
  display: grid;
  gap: 16px;
}

.workspace-side {
  position: sticky;
  top: 16px;
}

.panel-card {
  padding: 18px;
}

.panel-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 12px;
}

.panel-header h2 {
  margin: 0 0 4px;
  font-size: 16px;
  color: #18352b;
}

.panel-header p {
  margin: 0;
  line-height: 1.6;
  font-size: 13px;
  color: #557064;
}

.option-grid {
  display: grid;
  gap: 12px;
}

.option-grid--single {
  grid-template-columns: minmax(0, 1fr);
}

.option-item {
  display: flex;
  gap: 10px;
  align-items: center;
  min-height: 46px;
  padding: 0 14px;
  border-radius: 16px;
  background: #f6faf7;
  color: #18352b;
  font-size: 14px;
}

.empty-inline-tip {
  color: #557064;
  line-height: 1.7;
}

.upload-area {
  border: 2px dashed #cdd9d3;
  border-radius: 20px;
  padding: 28px 18px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  background: linear-gradient(180deg, #f9fbfa 0%, #f2f7f4 100%);
}

.upload-area:hover {
  border-color: #2f6c59;
  background: #eef6f2;
}

.upload-content {
  color: #4f685d;
}

.upload-icon {
  display: inline-flex;
  width: 52px;
  height: 52px;
  align-items: center;
  justify-content: center;
  margin-bottom: 12px;
  border-radius: 16px;
  background: #173b32;
  color: #f6fbf8;
  font-size: 24px;
  font-weight: 700;
}

.upload-text {
  margin: 0 0 8px;
  font-size: 16px;
  font-weight: 600;
}

.upload-hint {
  margin: 0;
  font-size: 13px;
  color: #7a9086;
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(148px, 1fr));
  gap: 12px;
  margin-top: 14px;
}

.preview-card,
.result-card {
  position: relative;
  border-radius: 18px;
  background: #f8fbf9;
  border: 1px solid #e7efea;
  overflow: hidden;
}

.preview-card {
  padding: 10px;
}

.preview-visual {
  border-radius: 14px;
  overflow: hidden;
}

.preview-image,
.result-cover,
.detail-image {
  width: 100%;
  object-fit: cover;
  border-radius: 14px;
}

.preview-image,
.result-cover {
  aspect-ratio: 1 / 1;
}

.archive-placeholder {
  display: flex;
  align-items: center;
  justify-content: center;
  width: 100%;
  aspect-ratio: 1 / 1;
  border-radius: 14px;
  background: linear-gradient(135deg, #173b32 0%, #3a7a65 100%);
  color: #f6fbf8;
  font-size: 24px;
  font-weight: 700;
}

.preview-meta,
.result-copy {
  display: grid;
  gap: 4px;
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
  margin: 2px 0;
}

.result-tag {
  display: inline-flex;
  align-items: center;
  min-height: 22px;
  padding: 0 8px;
  border-radius: 999px;
  background: #eef4f1;
  color: #355b4d;
  font-size: 12px;
}

.result-tag--accent {
  background: #e8f1ed;
  color: #1f6a4d;
}

.preview-meta strong,
.result-copy strong {
  color: #18352b;
  font-size: 14px;
}

.preview-meta span,
.result-copy span {
  color: #6b8579;
  font-size: 12px;
}

.remove-btn {
  position: absolute;
  top: 10px;
  right: 10px;
  z-index: 1;
  width: 28px;
  height: 28px;
  border: none;
  border-radius: 50%;
  background: rgba(16, 24, 40, 0.72);
  color: #fff;
  cursor: pointer;
}

.result-list {
  display: grid;
  gap: 10px;
}

.result-card {
  padding: 14px;
  display: grid;
  gap: 12px;
}

.result-main {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
}

.result-actions,
.action-row {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.result-actions {
  justify-content: flex-end;
}

.result-source-panel {
  display: grid;
  gap: 8px;
  padding-top: 10px;
  border-top: 1px solid #e4ece7;
}

.result-source-label {
  font-size: 12px;
  font-weight: 700;
  letter-spacing: 0.04em;
  color: #557064;
  text-transform: uppercase;
}

.result-source-list {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.result-source-chip {
  display: inline-flex;
  align-items: center;
  min-height: 30px;
  padding: 0 10px;
  border-radius: 999px;
  background: #eef4f1;
  color: #355b4d;
  font-size: 12px;
  text-decoration: none;
  max-width: 100%;
  word-break: break-all;
}

.result-source-chip--link {
  background: #e8f1ed;
  color: #1f6a4d;
}

.result-source-chip--link:hover {
  background: #dcece5;
}

.result-source-empty {
  font-size: 12px;
  color: #7a9086;
}

.btn {
  min-width: 108px;
  padding: 10px 16px;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  font-size: 13px;
  font-weight: 600;
  transition: transform 0.2s ease, opacity 0.2s ease;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn:not(:disabled):hover {
  transform: translateY(-1px);
}

.btn-primary {
  background: #173b32;
  color: #fff;
}

.btn-success {
  background: #2f6c59;
  color: #fff;
}

.btn-secondary {
  background: #edf3ef;
  color: #244538;
}

.btn-mini {
  min-width: 0;
  padding: 7px 10px;
  font-size: 12px;
  border-radius: 12px;
}

.detail-shell {
  display: grid;
  gap: 20px;
}

.detail-footer {
  display: flex;
  justify-content: flex-end;
}

.detail-summary p {
  margin: 0 0 8px;
}

.detail-item {
  display: grid;
  gap: 16px;
  padding: 18px;
  border-radius: 18px;
  background: #f8fbf9;
}

.detail-image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
}

.detail-figure {
  margin: 0;
}

.detail-image {
  aspect-ratio: 4 / 3;
}

.detail-figure figcaption {
  margin-top: 8px;
  color: #557064;
  text-align: center;
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
  .image-page {
    padding: 12px;
  }

  .hero {
    padding: 18px;
  }

  .hero h1 {
    font-size: 26px;
  }

  .result-main,
  .action-row,
  .result-actions,
  .panel-header {
    flex-direction: column;
  }

  .result-actions {
    justify-content: flex-start;
  }
}
</style>
