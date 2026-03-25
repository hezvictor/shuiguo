<template>
  <div class="image-detection">
    <div class="container">
      <h1>图片水果识别系统</h1>

      <!-- 上传区域 -->
      <div class="upload-section">
        <div
          class="upload-area"
          :class="{ 'drag-over': dragOver }"
          @drop="onDrop"
          @dragover="onDragOver"
          @dragleave="onDragLeave"
          @click="triggerFileInput"
        >
          <div class="upload-content">
            <i class="upload-icon">📁</i>
            <p class="upload-text">点击选择图片或拖拽图片到这里</p>
            <p class="upload-hint">支持 JPG、PNG 格式，最大 5MB</p>
          </div>
          <input
            ref="fileInput"
            type="file"
            accept="image/*"
            @change="onFileSelected"
            style="display: none"
          />
        </div>

        <div class="upload-controls">
          <button
            @click="triggerFileInput"
            class="btn btn-primary"
            :disabled="isProcessing"
          >
            <span v-if="isProcessing">处理中...</span>
            <span v-else>选择图片</span>
          </button>
          <button
            @click="detectImage"
            class="btn btn-success"
            :disabled="!selectedFile || isProcessing"
          >
            {{ isProcessing ? '检测中...' : '开始检测' }}
          </button>
          <button @click="clearAll" class="btn btn-secondary" :disabled="isProcessing">
            清空
          </button>
        </div>
      </div>

      <!-- 图片展示区域 -->
      <div v-if="selectedFile" class="image-section">
        <div class="image-comparison">
          <!-- 原图 + Canvas 绘制区域 -->
          <div class="image-container canvas-container">
            <h3>检测结果 <span v-if="selectedTargets.length > 0" class="highlight-badge">已选中 {{ selectedTargets.length }} 个目标</span></h3>
            <div class="image-wrapper canvas-wrapper">
              <canvas
                ref="resultCanvas"
                class="result-canvas"
                :style="{ width: canvasWidth + 'px', height: canvasHeight + 'px' }"
              ></canvas>
              <div v-if="!targetsList.length && !isProcessing" class="no-image">等待检测结果</div>
              <div v-if="isProcessing" class="processing-overlay">
                <div class="spinner"></div>
                <span>检测中...</span>
              </div>
            </div>
            <div v-if="targetsList.length > 0" class="image-info">
              共检测到 {{ targetsList.length }} 个目标 | 处理时间: {{ processingTime }}ms
            </div>
          </div>
        </div>

        <!-- 目标列表（带复选框，点击时高亮对应框） -->
        <div v-if="targetsList.length > 0" class="targets-section">
          <div class="targets-header">
            <h3>检测到的目标</h3>
            <div class="select-all">
              <input type="checkbox" id="selectAll" v-model="selectAll" @change="onSelectAllChange" />
              <label for="selectAll">全选 ({{ targetsList.length }})</label>
            </div>
          </div>
          <div class="targets-list">
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
              <span class="target-label">
                {{ target.label }}
                <span class="confidence-badge">{{ (target.confidence * 100).toFixed(1) }}%</span>
              </span>
              <span class="target-bbox">框: [{{ target.bbox.join(',') }}]</span>
            </div>
          </div>
          <div class="report-actions">
            <button
              @click="generateReport"
              class="btn btn-primary"
              :disabled="isGeneratingReport || selectedTargets.length === 0"
            >
              {{ isGeneratingReport ? '生成中...' : `生成报告 (${selectedTargets.length}个目标)` }}
            </button>
          </div>
        </div>

        <!-- 报告展示区域 -->
        <div v-if="reportData" class="report-section">
          <h3>检测报告</h3>
          <div class="report-content">
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
                  <td>[{{ item.bbox.join(',') }}]</td>
                  <td>{{ item.fruit_classification.class }}</td>
                  <td>{{ (item.fruit_classification.confidence * 100).toFixed(1) }}%</td>
                  <td>{{ item.ripeness ? item.ripeness.predicted_class : '不适用' }}</td>
                  <td>{{ item.ripeness ? (item.ripeness.confidence * 100).toFixed(1) + '%' : '-' }}</td>
                </tr>
              </tbody>
            </table>
          </div>
          <div class="download-report">
            <button @click="downloadReportAsHtml" class="btn btn-success">下载报告（HTML）</button>
          </div>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="errorMessage" class="error-message">
        <i class="error-icon">⚠️</i>
        {{ errorMessage }}
      </div>

      <!-- 使用说明 -->
      <div class="instructions">
        <h3>使用说明</h3>
        <ul>
          <li>点击"选择图片"按钮或拖拽图片到上传区域</li>
          <li>支持 JPG、PNG 格式的图片文件，大小建议不超过 5MB</li>
          <li>点击"开始检测"进行目标检测，图片上会显示检测框</li>
          <li><strong>点击左侧目标列表或勾选复选框，对应的检测框会高亮显示（蓝色边框）</strong></li>
          <li>勾选需要分析的目标，点击"生成报告"获取详细的水果分类和成熟度信息</li>
          <li>报告生成后可以下载为 HTML 文件保存</li>
        </ul>
      </div>
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
      originalImage: null,      // 存储原始 Image 对象，用于 Canvas 绘制
      targetsList: [],           // 从 detectImage 获取的目标列表
      selectedTargets: [],       // 选中的目标索引
      selectAll: false,          // 全选状态
      isProcessing: false,
      isGeneratingReport: false,
      processingTime: 0,
      errorMessage: '',
      dragOver: false,
      canvasWidth: 0,
      canvasHeight: 0,
      reportData: null,          // 存储生成的报告数据
      canvasContext: null
    }
  },
  watch: {
    // 监听选中的目标变化，重新绘制 Canvas 高亮
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
      if (file) this.handleFile(file)
    },
    onDragOver(event) {
      event.preventDefault()
      this.dragOver = true
    },
    onDragLeave(event) {
      this.dragOver = false
    },
    onDrop(event) {
      event.preventDefault()
      this.dragOver = false
      const file = event.dataTransfer.files[0]
      if (file) this.handleFile(file)
    },
    handleFile(file) {
      if (!file.type.startsWith('image/')) {
        this.errorMessage = '请选择图片文件（JPG、PNG等格式）'
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

      // 原图预览
      if (this.originalImageUrl) URL.revokeObjectURL(this.originalImageUrl)
      this.originalImageUrl = URL.createObjectURL(file)

      // 加载原始图片到 Image 对象，用于 Canvas 绘制
      const img = new Image()
      img.onload = () => {
        this.originalImage = img
        this.canvasWidth = img.width
        this.canvasHeight = img.height
        
        // 初始化 Canvas
        this.initCanvas()
        
        // 如果有检测结果，重新绘制
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
        
        // 绘制原始图片
        this.canvasContext.drawImage(this.originalImage, 0, 0)
      }
    },

    // 绘制所有检测框，并根据选中的索引高亮
    redrawCanvasWithHighlights() {
      const canvas = this.$refs.resultCanvas
      const ctx = this.canvasContext
      
      if (!canvas || !ctx || !this.originalImage) return
      
      // 清除画布并重新绘制原始图片
      ctx.clearRect(0, 0, canvas.width, canvas.height)
      ctx.drawImage(this.originalImage, 0, 0)
      
      // 绘制所有检测框
      this.targetsList.forEach((target, idx) => {
        const [x1, y1, x2, y2] = target.bbox
        const isSelected = this.selectedTargets.includes(idx)
        
        // 根据是否选中设置不同样式
        if (isSelected) {
          // 选中的框：蓝色，更粗边框，带发光效果
          ctx.strokeStyle = '#3b82f6'
          ctx.lineWidth = 4
          ctx.shadowBlur = 8
          ctx.shadowColor = '#3b82f6'
        } else {
          // 未选中的框：红色，正常边框
          ctx.strokeStyle = '#ef4444'
          ctx.lineWidth = 2
          ctx.shadowBlur = 0
        }
        
        ctx.strokeRect(x1, y1, x2 - x1, y2 - y1)
        
        // 绘制标签背景
        const label = `${target.label} ${(target.confidence * 100).toFixed(1)}%`
        ctx.font = 'bold 14px "Inter", "Segoe UI", Arial'
        const textWidth = ctx.measureText(label).width
        const textHeight = 20
        const padding = 4
        
        // 标签背景
        ctx.fillStyle = isSelected ? 'rgba(59, 130, 246, 0.85)' : 'rgba(239, 68, 68, 0.85)'
        ctx.fillRect(x1, y1 - textHeight - padding, textWidth + padding * 2, textHeight + padding)
        
        // 标签文字
        ctx.fillStyle = '#ffffff'
        ctx.fillText(label, x1 + padding, y1 - padding)
      })
      
      // 重置阴影
      ctx.shadowBlur = 0
    },

    // 切换目标选择（点击整行）
    toggleTargetSelection(idx) {
      const index = this.selectedTargets.indexOf(idx)
      if (index === -1) {
        this.selectedTargets.push(idx)
      } else {
        this.selectedTargets.splice(index, 1)
      }
      this.updateSelectAllState()
    },

    // 复选框变化时调用
    onTargetSelectionChange() {
      this.updateSelectAllState()
    },

    // 全选变化
    onSelectAllChange() {
      if (this.selectAll) {
        this.selectedTargets = this.targetsList.map((_, idx) => idx)
      } else {
        this.selectedTargets = []
      }
    },

    // 更新全选状态
    updateSelectAllState() {
      this.selectAll = this.selectedTargets.length === this.targetsList.length && this.targetsList.length > 0
    },

    // 开始检测
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

      const formData = new FormData()
      formData.append('image', this.selectedFile)

      try {
        const startTime = Date.now()

        // 调用检测接口获取目标信息（不获取带框图片）
        const infoResult = await detectImage(formData)

        this.processingTime = Date.now() - startTime

        // 处理目标列表
        if (infoResult.status === 'success') {
          this.targetsList = infoResult.targets.map(target => ({
            bbox: target.bbox,
            label: target.label,
            confidence: target.confidence
          }))
          
          // 绘制检测框（初始时全部未选中）
          if (this.originalImage) {
            this.redrawCanvasWithHighlights()
          }
        } else {
          throw new Error(infoResult.error || '目标检测失败')
        }
      } catch (error) {
        console.error('图片检测失败:', error)
        this.errorMessage = error.message || '检测失败，请稍后重试'
        // 清空画布
        const canvas = this.$refs.resultCanvas
        if (canvas && this.canvasContext && this.originalImage) {
          this.canvasContext.drawImage(this.originalImage, 0, 0)
        }
      } finally {
        this.isProcessing = false
      }
    },

    // 生成报告
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

    // 下载报告为 HTML
    downloadReportAsHtml() {
      if (!this.reportData) return

      const reportHtml = `
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>水果检测报告</title>
  <style>
    body {
      font-family: 'Inter', 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
      padding: 20px;
      background: #f5f7fa;
    }
    .container {
      max-width: 1200px;
      margin: 0 auto;
      background: white;
      border-radius: 16px;
      padding: 24px;
      box-shadow: 0 4px 12px rgba(0,0,0,0.1);
    }
    h1 {
      color: #2c3e50;
      border-bottom: 2px solid #409eff;
      padding-bottom: 10px;
    }
    table {
      width: 100%;
      border-collapse: collapse;
      margin-top: 20px;
    }
    th, td {
      border: 1px solid #ddd;
      padding: 10px;
      text-align: left;
    }
    th {
      background: #f2f2f2;
      font-weight: 600;
    }
    .footer {
      margin-top: 20px;
      text-align: center;
      color: #7f8c8d;
      font-size: 12px;
    }
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
      link.download = `fruit_report_${new Date().toISOString().slice(0,19).replace(/:/g, '-')}.html`
      link.click()
      URL.revokeObjectURL(link.href)
    },

    // 清空所有
    clearAll() {
      this.selectedFile = null
      if (this.originalImageUrl) URL.revokeObjectURL(this.originalImageUrl)
      this.originalImageUrl = null
      this.originalImage = null
      this.targetsList = []
      this.selectedTargets = []
      this.reportData = null
      this.errorMessage = ''
      this.processingTime = 0
      this.canvasWidth = 0
      this.canvasHeight = 0
      if (this.$refs.fileInput) this.$refs.fileInput.value = ''
      
      // 清空 Canvas
      const canvas = this.$refs.resultCanvas
      if (canvas && this.canvasContext) {
        this.canvasContext.clearRect(0, 0, canvas.width, canvas.height)
      }
    }
  },
  beforeUnmount() {
    if (this.originalImageUrl) URL.revokeObjectURL(this.originalImageUrl)
  }
}
</script>

<style scoped>
.image-detection {
  padding: 20px;
  font-family: 'Arial', 'Microsoft YaHei', sans-serif;
  max-width: 1200px;
  margin: 0 auto;
}
.container {
  background: white;
  border-radius: 12px;
  padding: 30px;
  box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
}
h1 {
  text-align: center;
  color: #2c3e50;
  margin-bottom: 30px;
  font-size: 2.2em;
}
.upload-section {
  margin-bottom: 30px;
}
.upload-area {
  border: 3px dashed #dcdfe6;
  border-radius: 8px;
  padding: 60px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #fafafa;
  margin-bottom: 20px;
}
.upload-area:hover {
  border-color: #409eff;
  background-color: #f0f7ff;
}
.upload-area.drag-over {
  border-color: #409eff;
  background-color: #ecf5ff;
}
.upload-content {
  color: #606266;
}
.upload-icon {
  font-size: 48px;
  margin-bottom: 16px;
  display: block;
}
.upload-text {
  font-size: 18px;
  margin-bottom: 8px;
  font-weight: 500;
}
.upload-hint {
  font-size: 14px;
  color: #909399;
}
.upload-controls {
  display: flex;
  gap: 12px;
  justify-content: center;
  flex-wrap: wrap;
}
.btn {
  padding: 12px 24px;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s ease;
  min-width: 100px;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.btn-primary {
  background-color: #409eff;
  color: white;
}
.btn-primary:hover:not(:disabled) {
  background-color: #66b1ff;
}
.btn-success {
  background-color: #67c23a;
  color: white;
}
.btn-success:hover:not(:disabled) {
  background-color: #85ce61;
}
.btn-secondary {
  background-color: #909399;
  color: white;
}
.btn-secondary:hover:not(:disabled) {
  background-color: #a6a9ad;
}
.image-section {
  margin-bottom: 30px;
}
.image-comparison {
  margin-bottom: 30px;
}
.image-container {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  border: 1px solid #e9ecef;
}
.image-container h3 {
  margin-top: 0;
  margin-bottom: 15px;
  color: #495057;
  text-align: center;
  font-size: 1.3em;
}
.highlight-badge {
  font-size: 12px;
  background: #3b82f6;
  color: white;
  padding: 2px 8px;
  border-radius: 20px;
  margin-left: 10px;
}
.image-wrapper {
  background: #1a1a2e;
  border-radius: 6px;
  padding: 10px;
  border: 1px solid #dee2e6;
  min-height: 200px;
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
}
.canvas-wrapper {
  padding: 0;
  background: #f0f0f0;
}
.result-canvas {
  max-width: 100%;
  height: auto;
  border-radius: 4px;
  display: block;
  margin: 0 auto;
}
.no-image {
  color: #6c757d;
  font-style: italic;
  text-align: center;
  padding: 40px;
}
.processing-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.6);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  color: white;
  gap: 12px;
  border-radius: 6px;
}
.spinner {
  width: 40px;
  height: 40px;
  border: 3px solid rgba(255, 255, 255, 0.3);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}
@keyframes spin {
  to { transform: rotate(360deg); }
}
.image-info {
  margin-top: 10px;
  text-align: center;
  color: #6c757d;
  font-size: 14px;
}
.targets-section {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 30px;
}
.targets-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  flex-wrap: wrap;
}
.targets-header h3 {
  margin: 0;
}
.select-all {
  display: flex;
  align-items: center;
  gap: 8px;
}
.targets-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  max-height: 300px;
  overflow-y: auto;
}
.target-item {
  background: white;
  padding: 12px 15px;
  border-radius: 8px;
  border: 1px solid #e9ecef;
  display: flex;
  align-items: center;
  gap: 15px;
  flex-wrap: wrap;
  cursor: pointer;
  transition: all 0.2s ease;
}
.target-item:hover {
  background: #f8f9fa;
  border-color: #3b82f6;
  transform: translateX(2px);
}
.target-item.target-selected {
  background: #eef2ff;
  border-color: #3b82f6;
  border-left: 4px solid #3b82f6;
}
.target-checkbox {
  width: 18px;
  height: 18px;
  cursor: pointer;
}
.target-label {
  font-weight: 500;
  color: #2c3e50;
  display: flex;
  align-items: center;
  gap: 8px;
}
.confidence-badge {
  background: #e9ecef;
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: normal;
  color: #495057;
}
.target-bbox {
  font-size: 12px;
  color: #7f8c8d;
  font-family: monospace;
}
.report-actions {
  margin-top: 20px;
  text-align: center;
}
.report-section {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 20px;
  margin-top: 20px;
}
.report-section h3 {
  margin-top: 0;
  margin-bottom: 15px;
  text-align: center;
}
.report-content {
  overflow-x: auto;
}
.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.report-table th,
.report-table td {
  border: 1px solid #dee2e6;
  padding: 10px;
  text-align: left;
}
.report-table th {
  background: #e9ecef;
  font-weight: 600;
}
.download-report {
  margin-top: 20px;
  text-align: center;
}
.error-message {
  background-color: #f8d7da;
  color: #721c24;
  padding: 15px;
  border-radius: 6px;
  border: 1px solid #f5c6cb;
  margin-bottom: 20px;
  display: flex;
  align-items: center;
  gap: 10px;
}
.error-icon {
  font-size: 18px;
}
.instructions {
  background: #e7f3ff;
  border-radius: 8px;
  padding: 20px;
  border-left: 4px solid #409eff;
}
.instructions h3 {
  margin-top: 0;
  color: #2c3e50;
  margin-bottom: 15px;
}
.instructions ul {
  margin: 0;
  padding-left: 20px;
  color: #495057;
}
.instructions li {
  margin-bottom: 8px;
  line-height: 1.5;
}
@media (max-width: 768px) {
  .upload-controls {
    flex-direction: column;
    align-items: center;
  }
  .btn {
    width: 200px;
  }
  .target-item {
    flex-direction: column;
    align-items: flex-start;
  }
  .report-table {
    font-size: 12px;
  }
}
</style>