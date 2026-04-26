<template>
  <div class="video-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Video Detection Workspace</p>
          <h1>视频检测</h1>
          <p class="hero-text">
            上传一段视频后，系统会按设定帧率逐帧识别水果与成熟度，并生成可下载的处理后视频和检测报告。
          </p>
        </div>

        <div class="hero-status">
          <div class="hero-badge">{{ selectedFile ? `当前文件：${selectedFile.name}` : '等待上传视频' }}</div>
          <div class="hero-badge">{{ currentTask ? `任务状态：${getStatusText(currentTask.status)}` : '暂无任务' }}</div>
          <div class="hero-badge">{{ reportData ? '报告已生成' : '报告未生成' }}</div>
        </div>
      </section>

      <section class="guide-strip">
        <article class="guide-step">
          <span class="guide-index">1</span>
          <div>
            <h3>上传视频</h3>
            <p>支持 MP4、AVI、MOV 等格式，建议优先使用清晰稳定的视频。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">2</span>
          <div>
            <h3>开始处理</h3>
            <p>设置处理帧率后开始任务，系统会自动轮询处理进度。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">3</span>
          <div>
            <h3>查看并下载结果</h3>
            <p>处理完成后可预览结果视频，并下载报告或处理后视频。</p>
          </div>
        </article>
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
                <h2>上传与处理</h2>
                <p>先上传视频，再设置处理帧率并提交任务。</p>
              </div>
            </div>

            <div
              class="upload-area"
              :class="{ 'drag-over': dragOver }"
              @drop="handleDrop"
              @dragover="handleDragOver"
              @dragleave="dragOver = false"
              @click="triggerFileInput"
            >
              <input
                ref="fileInput"
                type="file"
                accept="video/*"
                @change="handleFileSelect"
                style="display: none"
              />
              <div class="upload-content">
                <span class="upload-icon">▣</span>
                <h3>点击或拖拽视频到这里</h3>
                <p>支持 MP4 / AVI / MOV，建议不超过 500MB</p>
              </div>
            </div>

            <div v-if="selectedFile" class="file-card">
              <div class="file-details">
                <strong>{{ selectedFile.name }}</strong>
                <div class="file-meta">
                  <span>大小：{{ formatFileSize(selectedFile.size) }}</span>
                  <span>类型：{{ selectedFile.type || 'video/mp4' }}</span>
                </div>
              </div>

              <div class="fps-row">
                <label for="fpsInput">处理帧率 (FPS)</label>
                <input id="fpsInput" v-model.number="processFps" type="number" min="1" max="30" class="fps-input" />
                <span class="fps-hint">较低帧率会更快，较高帧率细节更多。</span>
              </div>

              <div class="action-row">
                <button @click="startProcessing" :disabled="isProcessing" class="btn btn-primary">
                  <span v-if="isProcessing">处理中...</span>
                  <span v-else>开始处理视频</span>
                </button>
              </div>
            </div>
          </section>

          <section v-if="currentTask && currentTask.status !== 'completed'" class="panel-card">
            <div class="panel-header">
              <div>
                <h2>处理进度</h2>
                <p>任务执行过程中会自动刷新当前进度。</p>
              </div>
              <span class="panel-badge">{{ currentTask.progress || 0 }}%</span>
            </div>

            <div class="progress-card">
              <div class="progress-top">
                <span>视频处理中</span>
                <span>{{ currentTask.progress || 0 }}%</span>
              </div>
              <div class="progress-bar">
                <div
                  class="progress-fill"
                  :style="{ width: (currentTask.progress || 0) + '%' }"
                  :class="{ animate: currentTask.progress < 100 }"
                ></div>
              </div>
              <div class="progress-meta">
                <span v-if="currentTask.processedFrames && currentTask.totalFrames">
                  已处理 {{ currentTask.processedFrames }} / {{ currentTask.totalFrames }} 帧
                </span>
                <span v-if="currentTask.message">{{ currentTask.message }}</span>
              </div>
              <div v-if="currentTask.status === 'error'" class="retry-row">
                <button @click="retryProcessing" class="btn btn-secondary">重新尝试</button>
              </div>
            </div>
          </section>

          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>视频预览</h2>
                <p>左侧为原视频，右侧为处理后视频。</p>
              </div>
            </div>

            <div class="video-grid">
              <div class="video-card">
                <h3>原视频</h3>
                <video
                  v-if="originalVideoUrl"
                  :src="originalVideoUrl"
                  controls
                  class="video-player"
                  @error="handleVideoError"
                ></video>
                <div v-else class="video-placeholder">尚未选择视频</div>
              </div>
              <div class="video-card">
                <h3>处理后视频</h3>
                <video v-if="processedVideoUrl" :src="processedVideoUrl" controls class="video-player"></video>
                <div v-else class="video-placeholder">等待处理完成</div>
              </div>
            </div>

            <div v-if="currentTask && currentTask.status === 'completed'" class="action-row">
              <button @click="downloadVideo" class="btn btn-success">下载处理后视频</button>
              <button @click="cleanupTask" class="btn btn-secondary">清理当前任务</button>
            </div>
          </section>
        </div>

        <div class="workspace-side">
          <section v-if="reportData" class="panel-card">
            <div class="panel-header">
              <div>
                <h2>检测报告</h2>
                <p>按水果种类和成熟度展示视频中的识别统计。</p>
              </div>
            </div>

            <div class="summary-card">
              <span>总检测目标数（帧级）</span>
              <strong>{{ reportData.total_targets }}</strong>
            </div>

            <div class="table-shell">
              <h3>水果种类统计</h3>
              <table class="report-table">
                <thead>
                  <tr>
                    <th>排名</th>
                    <th>水果种类</th>
                    <th>出现次数</th>
                    <th>占比</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(item, index) in sortedFruitCounts" :key="item.fruit">
                    <td>{{ index + 1 }}</td>
                    <td>{{ getFruitIcon(item.fruit) }} {{ item.fruit }}</td>
                    <td>{{ item.count }}</td>
                    <td>{{ getPercentage(item.count, reportData.total_targets) }}%</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div v-if="sortedRipenessData.length" class="table-shell">
              <h3>成熟度统计</h3>
              <table class="report-table">
                <thead>
                  <tr>
                    <th>水果种类</th>
                    <th>成熟度</th>
                    <th>出现次数</th>
                    <th>占比</th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="item in sortedRipenessData" :key="`${item.fruit}-${item.ripeness}`">
                    <td>{{ item.fruit }}</td>
                    <td><span :class="getRipenessClass(item.ripeness)">{{ item.ripeness }}</span></td>
                    <td>{{ item.count }}</td>
                    <td>{{ getPercentage(item.count, getFruitTotal(item.fruit)) }}%</td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="action-row">
              <button @click="downloadReport" class="btn btn-success">下载 JSON 报告</button>
            </div>
          </section>

          <section v-if="taskHistory.length" class="panel-card">
            <div class="panel-header">
              <div>
                <h2>历史任务</h2>
                <p>保留最近的视频处理记录，方便回看与下载。</p>
              </div>
            </div>

            <div class="history-list">
              <div v-for="task in taskHistory" :key="task.taskId" class="history-item">
                <div class="history-copy">
                  <strong>{{ task.originalFileName }}</strong>
                  <div class="history-meta">
                    <span class="status-chip" :class="task.status">{{ getStatusText(task.status) }}</span>
                    <span v-if="task.progress !== undefined">{{ task.progress }}%</span>
                  </div>
                </div>
                <div class="history-actions">
                  <button v-if="task.status === 'completed'" @click="downloadHistoryVideo(task.taskId)" class="mini-btn">下载</button>
                  <button @click="removeHistoryTask(task.taskId)" class="mini-btn danger">删除</button>
                </div>
              </div>
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
              <li>上传视频后设置一个合适的处理帧率，默认 5 FPS 就够用。</li>
              <li>处理完成后可预览并下载处理后视频。</li>
              <li>右侧报告会按水果种类和成熟度给出统计结果。</li>
              <li>历史任务会保留最近记录，方便重复下载与查看。</li>
            </ul>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { uploadVideo, getVideoProgress, downloadVideo, cleanupVideoTask } from '@/api/detection'

export default {
  name: 'VideoProcessing',
  data() {
    return {
      selectedFile: null,
      isProcessing: false,
      processFps: 5,
      currentTask: null,
      taskHistory: [],
      errorMessage: '',
      progressInterval: null,
      originalVideoUrl: null,
      processedVideoUrl: null,
      reportData: null,
      dragOver: false
    }
  },
  computed: {
    sortedFruitCounts() {
      if (!this.reportData || !this.reportData.fruit_counts) return []
      const counts = this.reportData.fruit_counts
      return Object.entries(counts)
        .map(([fruit, count]) => ({ fruit, count }))
        .sort((a, b) => b.count - a.count)
    },
    sortedRipenessData() {
      if (!this.reportData || !this.reportData.ripeness_counts) return []
      const result = []
      Object.entries(this.reportData.ripeness_counts).forEach(([fruit, ripenessMap]) => {
        Object.entries(ripenessMap).forEach(([ripeness, count]) => {
          result.push({ fruit, ripeness, count })
        })
      })
      return result.sort((a, b) => {
        if (a.fruit !== b.fruit) return a.fruit.localeCompare(b.fruit)
        return b.count - a.count
      })
    }
  },
  mounted() {
    this.loadTaskHistory()
  },
  beforeUnmount() {
    this.cleanupProgressPolling()
    if (this.originalVideoUrl) URL.revokeObjectURL(this.originalVideoUrl)
    if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl)
  },
  methods: {
    handleVideoError() {
      this.errorMessage = '视频无法播放，可能是编码格式不受当前浏览器支持。你可以下载后用本地播放器查看。'
    },
    triggerFileInput() {
      this.$refs.fileInput.click()
    },
    handleFileSelect(event) {
      const file = event.target.files[0]
      if (file) {
        this.validateAndSetFile(file)
      }
    },
    handleDrop(event) {
      event.preventDefault()
      this.dragOver = false
      const files = event.dataTransfer.files
      if (files.length > 0) {
        this.validateAndSetFile(files[0])
      }
    },
    handleDragOver(event) {
      event.preventDefault()
      this.dragOver = true
    },
    validateAndSetFile(file) {
      if (!file.type.startsWith('video/')) {
        this.errorMessage = '请选择视频文件'
        return
      }
      const maxSize = 500 * 1024 * 1024
      if (file.size > maxSize) {
        this.errorMessage = '文件大小不能超过 500MB'
        return
      }

      this.selectedFile = file
      this.errorMessage = ''
      this.currentTask = null
      this.reportData = null
      this.processedVideoUrl = null

      if (this.originalVideoUrl) URL.revokeObjectURL(this.originalVideoUrl)
      this.originalVideoUrl = URL.createObjectURL(file)
    },
    async startProcessing() {
      if (!this.selectedFile) {
        this.errorMessage = '请先选择视频文件'
        return
      }

      this.isProcessing = true
      this.errorMessage = ''

      const formData = new FormData()
      formData.append('file', this.selectedFile)
      formData.append('processFps', this.processFps.toString())

      try {
        const result = await uploadVideo(formData)
        this.currentTask = result
        this.addToTaskHistory(result)
        this.startProgressPolling(result.taskId)
      } catch (error) {
        console.error('处理视频失败:', error)
        this.errorMessage = `处理失败: ${error.message}`
        this.isProcessing = false
      }
    },
    startProgressPolling(taskId) {
      this.cleanupProgressPolling()
      this.progressInterval = setInterval(async () => {
        try {
          const task = await getVideoProgress(taskId)
          this.currentTask = task
          this.updateTaskHistory(task)

          if (task.status === 'completed') {
            this.isProcessing = false
            this.cleanupProgressPolling()
            await this.fetchProcessedVideo(taskId)
            if (task.report) {
              this.reportData = task.report
            }
          } else if (task.status === 'error') {
            this.isProcessing = false
            this.cleanupProgressPolling()
          }
        } catch (error) {
          console.error('获取进度失败:', error)
        }
      }, 2000)
    },
    async fetchProcessedVideo(taskId) {
      try {
        const blob = await downloadVideo(taskId)
        if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl)
        this.processedVideoUrl = URL.createObjectURL(blob)
      } catch (error) {
        console.error('获取处理后的视频失败:', error)
        this.errorMessage = '获取处理后的视频失败，请检查服务端日志'
      }
    },
    async downloadVideo() {
      if (!this.currentTask || this.currentTask.status !== 'completed') {
        this.errorMessage = '视频尚未处理完成'
        return
      }

      try {
        const blob = await downloadVideo(this.currentTask.taskId)
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `processed_${this.currentTask.originalFileName}`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } catch (error) {
        console.error('下载视频失败:', error)
        this.errorMessage = '下载视频失败'
      }
    },
    async downloadHistoryVideo(taskId) {
      try {
        const blob = await downloadVideo(taskId)
        const url = window.URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        const task = this.taskHistory.find((item) => item.taskId === taskId)
        a.download = `processed_${task?.originalFileName || 'video'}.mp4`
        document.body.appendChild(a)
        a.click()
        window.URL.revokeObjectURL(url)
        document.body.removeChild(a)
      } catch (error) {
        console.error('下载视频失败:', error)
        this.errorMessage = '下载视频失败'
      }
    },
    async cleanupTask() {
      if (!this.currentTask) return

      try {
        await cleanupVideoTask(this.currentTask.taskId)
        this.removeFromTaskHistory(this.currentTask.taskId)
        this.currentTask = null
        this.reportData = null
        if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl)
        this.processedVideoUrl = null
      } catch (error) {
        console.error('清理任务失败:', error)
      }
    },
    removeHistoryTask(taskId) {
      this.removeFromTaskHistory(taskId)
      if (this.currentTask?.taskId === taskId) {
        this.currentTask = null
        this.reportData = null
        if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl)
        this.processedVideoUrl = null
      }
    },
    retryProcessing() {
      if (this.selectedFile) {
        this.startProcessing()
      }
    },
    downloadReport() {
      if (!this.reportData) return
      const reportStr = JSON.stringify(this.reportData, null, 2)
      const blob = new Blob([reportStr], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `video_report_${this.currentTask?.taskId || Date.now()}.json`
      document.body.appendChild(a)
      a.click()
      URL.revokeObjectURL(url)
      document.body.removeChild(a)
    },
    formatFileSize(bytes) {
      if (bytes === 0) return '0 B'
      const k = 1024
      const sizes = ['B', 'KB', 'MB', 'GB']
      const i = Math.floor(Math.log(bytes) / Math.log(k))
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i]
    },
    getPercentage(count, total) {
      if (!total || total === 0) return '0'
      return ((count / total) * 100).toFixed(1)
    },
    getFruitTotal(fruit) {
      if (!this.reportData?.fruit_counts) return 0
      return this.reportData.fruit_counts[fruit] || 0
    },
    getFruitIcon(fruit) {
      const iconMap = {
        香蕉: '🍌',
        芒果: '🥭',
        草莓: '🍓',
        苹果: '🍎',
        橙子: '🍊',
        葡萄: '🍇',
        西瓜: '🍉',
        菠萝: '🍍',
        猕猴桃: '🥝',
        柠檬: '🍋'
      }
      return iconMap[fruit] || '🍎'
    },
    getRipenessClass(ripeness) {
      if (ripeness.includes('Ripe') || ripeness.includes('熟')) return 'ripeness-ripe'
      if (ripeness.includes('Unripe') || ripeness.includes('生')) return 'ripeness-unripe'
      if (ripeness.includes('Half') || ripeness.includes('半')) return 'ripeness-half'
      return ''
    },
    getStatusText(status) {
      const map = {
        processing: '处理中',
        completed: '已完成',
        error: '失败'
      }
      return map[status] || status
    },
    loadTaskHistory() {
      const saved = localStorage.getItem('videoTaskHistory')
      if (saved) {
        try {
          this.taskHistory = JSON.parse(saved)
        } catch (error) {
          console.error('加载历史记录失败', error)
        }
      }
    },
    addToTaskHistory(task) {
      const existing = this.taskHistory.find((item) => item.taskId === task.taskId)
      if (!existing) {
        this.taskHistory.unshift({
          taskId: task.taskId,
          originalFileName: task.originalFileName,
          status: task.status,
          progress: task.progress,
          timestamp: Date.now()
        })
        this.saveTaskHistory()
      }
    },
    updateTaskHistory(updatedTask) {
      const index = this.taskHistory.findIndex((item) => item.taskId === updatedTask.taskId)
      if (index !== -1) {
        this.taskHistory[index] = {
          ...this.taskHistory[index],
          status: updatedTask.status,
          progress: updatedTask.progress
        }
        this.saveTaskHistory()
      }
    },
    removeFromTaskHistory(taskId) {
      this.taskHistory = this.taskHistory.filter((item) => item.taskId !== taskId)
      this.saveTaskHistory()
    },
    saveTaskHistory() {
      localStorage.setItem('videoTaskHistory', JSON.stringify(this.taskHistory.slice(0, 10)))
    },
    cleanupProgressPolling() {
      if (this.progressInterval) {
        clearInterval(this.progressInterval)
        this.progressInterval = null
      }
    }
  }
}
</script>

<style scoped>
.video-page {
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
.video-card h3 {
  margin: 0 0 6px;
  font-size: 18px;
  color: #18352b;
}

.guide-step p,
.panel-header p,
.video-card p {
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

.upload-content h3 {
  margin: 0 0 8px;
}

.file-card {
  margin-top: 18px;
  padding: 16px;
  border-radius: 18px;
  background: #f6faf7;
}

.file-details strong {
  color: #173b32;
}

.file-meta {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 8px;
  color: #587166;
  font-size: 13px;
}

.fps-row {
  display: grid;
  gap: 10px;
  margin-top: 16px;
}

.fps-row label {
  color: #173b32;
  font-weight: 600;
}

.fps-input {
  width: 160px;
  padding: 10px 12px;
  border: 1px solid #d7e3dc;
  border-radius: 12px;
  background: #fff;
}

.fps-hint {
  font-size: 13px;
  color: #6b8579;
}

.action-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.progress-card {
  display: grid;
  gap: 12px;
}

.progress-top,
.progress-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  color: #587166;
}

.progress-bar {
  height: 12px;
  border-radius: 999px;
  background: #e7efe9;
  overflow: hidden;
}

.progress-fill {
  height: 100%;
  border-radius: 999px;
  background: linear-gradient(90deg, #2f6c59 0%, #4f927b 100%);
}

.progress-fill.animate {
  transition: width 0.6s ease;
}

.video-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.video-card {
  padding: 16px;
  border-radius: 18px;
  background: #f7faf8;
}

.video-player {
  width: 100%;
  border-radius: 16px;
  background: #111827;
}

.video-placeholder {
  min-height: 220px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 16px;
  background: linear-gradient(140deg, #0f172a 0%, #1a2c43 100%);
  color: rgba(236, 244, 241, 0.9);
}

.summary-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 14px 16px;
  border-radius: 16px;
  background: #f6faf7;
  color: #587166;
}

.summary-card strong {
  color: #173b32;
  font-size: 24px;
}

.table-shell {
  margin-top: 16px;
  overflow: auto;
}

.table-shell h3 {
  margin: 0 0 10px;
  color: #173b32;
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

.history-list {
  display: grid;
  gap: 10px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 14px;
  border-radius: 16px;
  background: #f7faf8;
}

.history-copy {
  display: grid;
  gap: 6px;
}

.history-meta {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
  color: #587166;
  font-size: 13px;
}

.status-chip {
  padding: 2px 8px;
  border-radius: 999px;
  background: #eef2f0;
}

.status-chip.processing {
  background: #fff8eb;
  color: #7c5a13;
}

.status-chip.completed {
  background: #eef9f3;
  color: #18533a;
}

.status-chip.error {
  background: #fef3f2;
  color: #b42318;
}

.history-actions {
  display: flex;
  gap: 8px;
}

.mini-btn {
  padding: 8px 12px;
  border: none;
  border-radius: 12px;
  background: #173b32;
  color: #fff;
  cursor: pointer;
}

.mini-btn.danger {
  background: #d92d20;
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

.ripeness-ripe {
  color: #18533a;
}

.ripeness-unripe {
  color: #b42318;
}

.ripeness-half {
  color: #7c5a13;
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

  .guide-strip,
  .video-grid {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .video-page {
    padding: 12px;
  }

  .hero {
    padding: 22px 20px;
  }

  .hero h1 {
    font-size: 30px;
  }

  .panel-header,
  .progress-top,
  .progress-meta,
  .action-row,
  .file-meta,
  .history-item {
    flex-direction: column;
  }
}
</style>
