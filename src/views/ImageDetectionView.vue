<template>
  <div class="image-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Image Detection Workspace</p>
          <h1>图片检测</h1>
          <p class="hero-text">
            上传一张水果图片，点击“开始检测”，系统会先圈出所有识别目标；再勾选你关心的水果，生成更详细的分类与成熟度报告。
          </p>
        </div>

        <div class="hero-status">
          <div class="hero-badge">{{ selectedFile ? `当前文件：${selectedFile.name}` : '等待上传图片' }}</div>
          <div class="hero-badge">{{ targetsList.length ? `已检测 ${targetsList.length} 个目标` : '尚未检测' }}</div>
          <div class="hero-badge">{{ reportData ? '报告已生成' : '报告未生成' }}</div>
        </div>
      </section>

      <section class="guide-strip">
        <article class="guide-step">
          <span class="guide-index">1</span>
          <div>
            <h3>上传图片</h3>
            <p>支持 JPG、PNG 等常见格式，拖拽或点击上传都可以。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">2</span>
          <div>
            <h3>开始检测</h3>
            <p>系统会先识别图片中的水果，并在画面里标出检测框。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">3</span>
          <div>
            <h3>勾选并生成报告</h3>
            <p>选择要分析的目标后生成报告，查看分类、成熟度和详情。</p>
          </div>
        </article>
      </section>

      <div v-if="errorMessage" class="error-banner">
        <strong>处理失败</strong>
        <span>{{ errorMessage }}</span>
      </div>

      <section class="workspace-grid">
        <div class="workspace-main">
          <section class="panel-card upload-card">
            <div class="panel-header">
              <div>
                <h2>上传与检测</h2>
                <p>先上传图片，再执行检测。支持拖拽上传。</p>
              </div>
            </div>

            <div
              class="upload-area"
              :class="{ 'drag-over': dragOver }"
              @drop="onDrop"
              @dragover="onDragOver"
              @dragleave="onDragLeave"
              @click="triggerFileInput"
            >
              <div class="upload-content">
                <span class="upload-icon">◫</span>
                <p class="upload-text">点击选择图片或将图片拖到这里</p>
                <p class="upload-hint">支持 JPG / PNG，建议不超过 5MB</p>
              </div>
              <input
                ref="fileInput"
                type="file"
                accept="image/*"
                @change="onFileSelected"
                style="display: none"
              />
            </div>

            <div class="action-row">
              <button @click="triggerFileInput" class="btn btn-primary" :disabled="isProcessing">
                <span v-if="isProcessing">处理中...</span>
                <span v-else>选择图片</span>
              </button>
              <button @click="detectImage" class="btn btn-success" :disabled="!selectedFile || isProcessing">
                {{ isProcessing ? '检测中...' : '开始检测' }}
              </button>
              <button @click="clearAll" class="btn btn-secondary" :disabled="isProcessing">
                清空
              </button>
            </div>

            <div v-if="selectedFile" class="file-meta-card">
              <span>文件名：{{ selectedFile.name }}</span>
              <span>处理时间：{{ processingTime || 0 }} ms</span>
              <span>目标数量：{{ targetsList.length }}</span>
            </div>
          </section>

          <section class="panel-card canvas-card">
            <div class="panel-header">
              <div>
                <h2>检测画面</h2>
                <p>蓝色高亮表示你当前选中的目标。</p>
              </div>
              <span v-if="selectedTargets.length" class="panel-badge">已选 {{ selectedTargets.length }} 个目标</span>
            </div>

            <div v-if="selectedFile" class="canvas-stage">
              <div class="image-wrapper canvas-wrapper">
                <canvas
                  ref="resultCanvas"
                  class="result-canvas"
                  :style="{ width: canvasWidth + 'px', height: canvasHeight + 'px' }"
                ></canvas>
                <div v-if="!targetsList.length && !isProcessing" class="empty-overlay">等待检测结果</div>
                <div v-if="isProcessing" class="processing-overlay">
                  <div class="spinner"></div>
                  <span>检测中...</span>
                </div>
              </div>
            </div>
            <div v-else class="empty-card-state">
              <h3>等待上传图片</h3>
              <p>上传图片后，这里会展示检测框和高亮结果。</p>
            </div>
          </section>
        </div>

        <div class="workspace-side">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>目标列表</h2>
                <p>点击整行或复选框都可以选择目标。</p>
              </div>
              <div v-if="targetsList.length" class="select-all">
                <input type="checkbox" id="selectAll" v-model="selectAll" @change="onSelectAllChange" />
                <label for="selectAll">全选 ({{ targetsList.length }})</label>
              </div>
            </div>

            <div v-if="targetsList.length" class="targets-list">
              <div
                v-for="(target, idx) in targetsList"
                :key="idx"
                class="target-item"
                :class="{ 'target-selected': selectedTargets.includes(idx) }"
                @click="toggleTargetSelection(idx)"
              >
                <input
                  type="checkbox"
                  :value="idx"
                  v-model="selectedTargets"
                  @click.stop
                  @change="onTargetSelectionChange"
                  class="target-checkbox"
                />
                <div class="target-copy">
                  <span class="target-label">
                    {{ target.label }}
                    <span class="confidence-badge">{{ (target.confidence * 100).toFixed(1) }}%</span>
                  </span>
                  <span class="target-bbox">框坐标 [{{ target.bbox.join(', ') }}]</span>
                </div>
              </div>
            </div>
            <div v-else class="empty-inline-tip">
              先完成检测，右侧会列出识别到的水果目标。
            </div>

            <div class="report-actions">
              <button
                @click="generateReport"
                class="btn btn-primary"
                :disabled="isGeneratingReport || selectedTargets.length === 0"
              >
                {{ isGeneratingReport ? '生成中...' : `生成报告 (${selectedTargets.length} 个目标)` }}
              </button>
            </div>
          </section>

          <section v-if="reportData" class="panel-card">
            <div class="panel-header">
              <div>
                <h2>检测报告</h2>
                <p>这里展示你已选择目标的详细识别结果。</p>
              </div>
            </div>

            <div class="table-shell">
              <table class="report-table">
                <thead>
                  <tr>
                    <th>序号</th>
                    <th>框坐标</th>
                    <th>水果分类</th>
                    <th>分类置信度</th>
                    <th>成熟度</th>
                    <th>成熟度置信度</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, idx) in reportData.targets" :key="idx">
                    <td>{{ idx + 1 }}</td>
                    <td>[{{ item.bbox.join(', ') }}]</td>
                    <td>{{ item.fruit_classification.class }}</td>
                    <td>{{ (item.fruit_classification.confidence * 100).toFixed(1) }}%</td>
                    <td>{{ item.ripeness ? item.ripeness.predicted_class : '不适用' }}</td>
                    <td>{{ item.ripeness ? (item.ripeness.confidence * 100).toFixed(1) + '%' : '-' }}</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="report-actions">
              <button @click="downloadReportAsHtml" class="btn btn-success">下载 HTML 报告</button>
            </div>
          </section>

          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>使用说明</h2>
                <p>第一次使用时按下面顺序操作即可。</p>
              </div>
            </div>

            <ul class="tips-list">
              <li>点击“选择图片”或把图片拖到上传区域。</li>
              <li>点击“开始检测”后，系统会在画面中显示检测框。</li>
              <li>在右侧目标列表中勾选你需要继续分析的水果。</li>
              <li>生成报告后，可直接下载 HTML 报告进行保存或分享。</li>
            </ul>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { detectImage, generateReport } from '@/api/detection'

export default {
  name: 'ImageDetection',
  data() {
    return {
      selectedFile: null,
      originalImageUrl: null,
      originalImage: null,
      targetsList: [],
      selectedTargets: [],
      selectAll: false,
      isProcessing: false,
      isGeneratingReport: false,
      processingTime: 0,
      errorMessage: '',
      dragOver: false,
      canvasWidth: 0,
      canvasHeight: 0,
      reportData: null,
      canvasContext: null
    }
  },
  watch: {
    selectedTargets: {
      handler() {
        this.redrawCanvasWithHighlights()
      },
      deep: true
    }
  },
  methods: {
    triggerFileInput() {
      this.$refs.fileInput.click()
    },
    onFileSelected(event) {
      const file = event.target.files[0]
      if (file) {
        this.handleFile(file)
      }
    },
    onDragOver(event) {
      event.preventDefault()
      this.dragOver = true
    },
    onDragLeave() {
      this.dragOver = false
    },
    onDrop(event) {
      event.preventDefault()
      this.dragOver = false
      const file = event.dataTransfer.files[0]
      if (file) {
        this.handleFile(file)
      }
    },
    handleFile(file) {
      if (!file.type.startsWith('image/')) {
        this.errorMessage = '请选择图片文件（JPG、PNG 等格式）'
        return
      }
      if (file.size > 5 * 1024 * 1024) {
        this.errorMessage = '图片大小不能超过 5MB'
        return
      }

      this.selectedFile = file
      this.targetsList = []
      this.selectedTargets = []
      this.reportData = null
      this.errorMessage = ''
      this.selectAll = false
      this.processingTime = 0

      if (this.originalImageUrl) {
        URL.revokeObjectURL(this.originalImageUrl)
      }
      this.originalImageUrl = URL.createObjectURL(file)

      const img = new Image()
      img.onload = () => {
        this.originalImage = img
        this.canvasWidth = img.width
        this.canvasHeight = img.height
        this.initCanvas()
        if (this.targetsList.length > 0) {
          this.redrawCanvasWithHighlights()
        }
      }
      img.src = this.originalImageUrl
    },
    initCanvas() {
      const canvas = this.$refs.resultCanvas
      if (canvas && this.originalImage) {
        canvas.width = this.originalImage.width
        canvas.height = this.originalImage.height
        this.canvasContext = canvas.getContext('2d')
        this.canvasContext.drawImage(this.originalImage, 0, 0)
      }
    },
    redrawCanvasWithHighlights() {
      const canvas = this.$refs.resultCanvas
      const ctx = this.canvasContext
      if (!canvas || !ctx || !this.originalImage) {
        return
      }

      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(this.originalImage, 0, 0)

      this.targetsList.forEach((target, idx) => {
        const [x1, y1, x2, y2] = target.bbox
        const isSelected = this.selectedTargets.includes(idx)

        if (isSelected) {
          ctx.strokeStyle = '#3b82f6'
          ctx.lineWidth = 4
          ctx.shadowBlur = 8
          ctx.shadowColor = '#3b82f6'
        } else {
          ctx.strokeStyle = '#ef4444'
          ctx.lineWidth = 2
          ctx.shadowBlur = 0
        }

        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)

        const label = `${target.label} ${(target.confidence * 100).toFixed(1)}%`
        ctx.font = 'bold 14px "Segoe UI", "Microsoft YaHei", Arial'
        const textWidth = ctx.measureText(label).width
        const textHeight = 20
        const padding = 4

        ctx.fillStyle = isSelected ? 'rgba(59, 130, 246, 0.85)' : 'rgba(239, 68, 68, 0.85)'
        ctx.fillRect(x1, y1 - textHeight - padding, textWidth + padding * 2, textHeight + padding)

        ctx.fillStyle = '#ffffff'
        ctx.fillText(label, x1 + padding, y1 - padding)
      })

      ctx.shadowBlur = 0
    },
    toggleTargetSelection(idx) {
      const index = this.selectedTargets.indexOf(idx)
      if (index === -1) {
        this.selectedTargets.push(idx)
      } else {
        this.selectedTargets.splice(index, 1)
      }
      this.updateSelectAllState()
    },
    onTargetSelectionChange() {
      this.updateSelectAllState()
    },
    onSelectAllChange() {
      if (this.selectAll) {
        this.selectedTargets = this.targetsList.map((_, idx) => idx)
      } else {
        this.selectedTargets = []
      }
    },
    updateSelectAllState() {
      this.selectAll = this.selectedTargets.length === this.targetsList.length && this.targetsList.length > 0
    },
    async detectImage() {
      if (!this.selectedFile) {
        this.errorMessage = '请先选择图片'
        return
      }

      this.isProcessing = true
      this.errorMessage = ''
      this.targetsList = []
      this.selectedTargets = []
      this.reportData = null
      this.selectAll = false

      const formData = new FormData()
      formData.append('image', this.selectedFile)

      try {
        const startTime = Date.now()
        const infoResult = await detectImage(formData)
        this.processingTime = Date.now() - startTime

        if (infoResult.status === 'success') {
          this.targetsList = infoResult.targets.map((target) => ({
            bbox: target.bbox,
            label: target.label,
            confidence: target.confidence
          }))
          if (this.originalImage) {
            this.redrawCanvasWithHighlights()
          }
        } else {
          throw new Error(infoResult.error || '目标检测失败')
        }
      } catch (error) {
        console.error('图片检测失败:', error)
        this.errorMessage = error.message || '检测失败，请稍后重试'
        const canvas = this.$refs.resultCanvas
        if (canvas && this.canvasContext && this.originalImage) {
          this.canvasContext.drawImage(this.originalImage, 0, 0)
        }
      } finally {
        this.isProcessing = false
      }
    },
    async generateReport() {
      if (this.selectedTargets.length === 0) {
        this.errorMessage = '请至少选择一个目标'
        return
      }

      this.isGeneratingReport = true
      this.errorMessage = ''
      this.reportData = null

      const formData = new FormData()
      formData.append('image', this.selectedFile)
      formData.append('selected_indices', JSON.stringify(this.selectedTargets))

      try {
        const res = await generateReport(formData)
        if (res.status === 'success') {
          this.reportData = res.report
        } else {
          throw new Error(res.error || '生成报告失败')
        }
      } catch (error) {
        console.error('生成报告失败:', error)
        this.errorMessage = error.message || '生成报告失败，请稍后重试'
      } finally {
        this.isGeneratingReport = false
      }
    },
    downloadReportAsHtml() {
      if (!this.reportData) {
        return
      }

      const reportHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>水果检测报告</title>
  <style>
    body { font-family: "Segoe UI", "Microsoft YaHei", Arial, sans-serif; padding: 20px; background: #f5f7fa; }
    .container { max-width: 1200px; margin: 0 auto; background: white; border-radius: 16px; padding: 24px; box-shadow: 0 4px 12px rgba(0,0,0,0.1); }
    h1 { color: #2c3e50; border-bottom: 2px solid #409eff; padding-bottom: 10px; }
    table { width: 100%; border-collapse: collapse; margin-top: 20px; }
    th, td { border: 1px solid #ddd; padding: 10px; text-align: left; }
    th { background: #f2f2f2; font-weight: 600; }
    .footer { margin-top: 20px; text-align: center; color: #7f8c8d; font-size: 12px; }
  </style>
</head>
<body>
  <div class="container">
    <h1>水果检测报告</h1>
    <p>生成时间: ${new Date().toLocaleString()}</p>
    <p>共检测到 ${this.reportData.total_targets} 个目标</p>
    <table>
      <thead>
        <tr>
          <th>序号</th>
          <th>框坐标</th>
          <th>水果分类</th>
          <th>分类置信度</th>
          <th>成熟度</th>
          <th>成熟度置信度</th>
        </tr>
      </thead>
      <tbody>
        ${this.reportData.targets.map((item, idx) => `
          <tr>
            <td>${idx + 1}</td>
            <td>[${item.bbox.join(',')}]</td>
            <td>${item.fruit_classification.class}</td>
            <td>${(item.fruit_classification.confidence * 100).toFixed(1)}%</td>
            <td>${item.ripeness ? item.ripeness.predicted_class : '不适用'}</td>
            <td>${item.ripeness ? (item.ripeness.confidence * 100).toFixed(1) + '%' : '-'}</td>
          </tr>
        `).join('')}
      </tbody>
    </table>
    <div class="footer">本报告由智能水果检测系统自动生成</div>
  </div>
</body>
</html>
      `

      const blob = new Blob([reportHtml], { type: 'text/html' })
      const link = document.createElement('a')
      link.href = URL.createObjectURL(blob)
      link.download = `fruit_report_${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.html`
      link.click()
      URL.revokeObjectURL(link.href)
    },
    clearAll() {
      this.selectedFile = null
      if (this.originalImageUrl) {
        URL.revokeObjectURL(this.originalImageUrl)
      }
      this.originalImageUrl = null
      this.originalImage = null
      this.targetsList = []
      this.selectedTargets = []
      this.selectAll = false
      this.reportData = null
      this.errorMessage = ''
      this.processingTime = 0
      this.canvasWidth = 0
      this.canvasHeight = 0
      if (this.$refs.fileInput) {
        this.$refs.fileInput.value = ''
      }

      const canvas = this.$refs.resultCanvas
      if (canvas && this.canvasContext) {
        this.canvasContext.clearRect(0, 0, canvas.width, canvas.height)
      }
    }
  },
  beforeUnmount() {
    if (this.originalImageUrl) {
      URL.revokeObjectURL(this.originalImageUrl)
    }
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
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.hero,
.panel-card {
  border-radius: 24px;
  border: none;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 20px 42px rgba(27, 51, 40, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(320px, 0.8fr);
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
  line-height: 1.1;
}

.hero-text {
  margin: 14px 0 0;
  line-height: 1.8;
  color: rgba(246, 251, 248, 0.86);
}

.hero-status {
  display: grid;
  gap: 12px;
  align-content: start;
}

.hero-badge {
  min-height: 42px;
  display: flex;
  align-items: center;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: #eff8f4;
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
.panel-header h2,
.empty-card-state h3 {
  margin: 0 0 6px;
  font-size: 18px;
  color: #18352b;
}

.guide-step p,
.panel-header p,
.empty-card-state p {
  margin: 0;
  line-height: 1.7;
  color: #557064;
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
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
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

.upload-area {
  border: 2px dashed #cdd9d3;
  border-radius: 20px;
  padding: 56px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.25s ease;
  background: linear-gradient(180deg, #f9fbfa 0%, #f2f7f4 100%);
}

.upload-area:hover,
.upload-area.drag-over {
  border-color: #2f6c59;
  background: #eef6f2;
}

.upload-content {
  color: #4f685d;
}

.upload-icon {
  display: inline-flex;
  width: 64px;
  height: 64px;
  align-items: center;
  justify-content: center;
  margin-bottom: 16px;
  border-radius: 20px;
  background: #173b32;
  color: #f6fbf8;
  font-size: 30px;
}

.upload-text {
  margin: 0 0 8px;
  font-size: 18px;
  font-weight: 600;
}

.upload-hint {
  margin: 0;
  font-size: 14px;
  color: #7a9086;
}

.action-row,
.report-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.file-meta-card {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: #f6faf7;
  color: #587166;
  font-size: 13px;
}

.canvas-stage {
  border-radius: 22px;
  overflow: hidden;
  background: linear-gradient(140deg, #0f172a 0%, #1a2c43 100%);
}

.canvas-wrapper {
  position: relative;
  overflow: auto;
  text-align: center;
  min-height: 420px;
}

.result-canvas {
  display: block;
  max-width: 100%;
  height: auto !important;
  margin: 0 auto;
}

.empty-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  color: rgba(236, 244, 241, 0.9);
}

.processing-overlay {
  position: absolute;
  inset: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
  align-items: center;
  justify-content: center;
  background: rgba(15, 23, 42, 0.5);
  color: #fff;
}

.spinner {
  width: 34px;
  height: 34px;
  border: 3px solid rgba(255, 255, 255, 0.24);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

.empty-card-state,
.empty-inline-tip {
  padding: 18px 0 4px;
  line-height: 1.7;
  color: #557064;
}

.targets-list {
  display: grid;
  gap: 10px;
}

.target-item {
  display: flex;
  gap: 12px;
  align-items: flex-start;
  padding: 14px;
  border-radius: 16px;
  background: #f7faf8;
  border: 1px solid transparent;
  cursor: pointer;
  transition: all 0.2s ease;
}

.target-item:hover {
  border-color: rgba(36, 84, 70, 0.12);
}

.target-selected {
  background: #eef6ff;
  border-color: rgba(59, 130, 246, 0.28);
}

.target-copy {
  display: grid;
  gap: 6px;
}

.target-label {
  font-weight: 700;
  color: #173b32;
}

.target-bbox {
  font-size: 13px;
  color: #6b8579;
}

.confidence-badge {
  margin-left: 8px;
  padding: 2px 8px;
  border-radius: 999px;
  background: rgba(23, 59, 50, 0.08);
  color: #2f6c59;
  font-size: 12px;
}

.table-shell {
  overflow: auto;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
}

.report-table th,
.report-table td {
  padding: 12px 10px;
  border-bottom: 1px solid #e5ece8;
  text-align: left;
  font-size: 13px;
}

.report-table th {
  color: #587166;
  font-weight: 700;
}

.tips-list {
  margin: 0;
  padding-left: 18px;
  color: #557064;
  line-height: 1.9;
}

.btn {
  min-width: 108px;
  padding: 12px 18px;
  border: none;
  border-radius: 14px;
  cursor: pointer;
  font-size: 14px;
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

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
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

  .guide-strip {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .image-page {
    padding: 12px;
  }

  .hero {
    padding: 22px 20px;
  }

  .hero h1 {
    font-size: 30px;
  }

  .action-row,
  .report-actions,
  .file-meta-card {
    flex-direction: column;
  }

  .panel-header {
    flex-direction: column;
  }

  .canvas-wrapper {
    min-height: 280px;
  }
}
</style>
