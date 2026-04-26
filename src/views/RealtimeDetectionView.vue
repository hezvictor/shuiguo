<template>
  <div class="realtime-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Realtime Detection Workspace</p>
          <h1>实时检测</h1>
          <p class="hero-text">
            启动浏览器摄像头后，系统会通过 WebSocket 持续上传画面并识别水果。你可以随时开始、暂停、保存当前会话报告。
          </p>
        </div>

        <div class="hero-status">
          <div class="hero-badge">摄像头：{{ isStreaming ? '运行中' : '未启动' }}</div>
          <div class="hero-badge">连接：{{ isConnected ? '已连接' : '未连接' }}</div>
          <div class="hero-badge">识别：{{ isProcessing ? '进行中' : '已停止' }}</div>
        </div>
      </section>

      <section class="guide-strip">
        <article class="guide-step">
          <span class="guide-index">1</span>
          <div>
            <h3>启动摄像头</h3>
            <p>允许浏览器访问摄像头后，系统会显示实时取景画面。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">2</span>
          <div>
            <h3>开始识别</h3>
            <p>开始后会持续识别水果和成熟度，并在画面中绘制结果。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">3</span>
          <div>
            <h3>保存或下载会话</h3>
            <p>当前会话可保存到历史，也可以导出当前统计报告。</p>
          </div>
        </article>
      </section>

      <div v-if="errorMessage" class="error-banner">
        <strong>运行异常</strong>
        <span>{{ errorMessage }}</span>
      </div>

      <section class="workspace-grid">
        <div class="workspace-main">
          <section class="panel-card">
            <div class="panel-header">
              <div>
                <h2>实时画面</h2>
                <p>这里显示摄像头预览和识别框，右上角会同步显示识别帧率。</p>
              </div>
              <span class="panel-badge">{{ fps }} fps</span>
            </div>

            <div class="video-wrapper">
              <video ref="videoElement" class="video-preview" autoplay playsinline muted></video>
              <canvas ref="canvasElement" class="overlay-canvas"></canvas>
            </div>

            <div class="camera-picker">
              <div class="camera-picker__header">
                <strong>浏览器摄像头</strong>
                <button type="button" class="mini-btn" @click="loadCameraDevices(true)" :disabled="cameraScanLoading">
                  {{ cameraScanLoading ? '刷新中...' : '刷新列表' }}
                </button>
              </div>
              <div class="camera-picker__row">
                <select v-model="selectedCameraId" class="camera-select" @change="onCameraSelectionChange">
                  <option value="">默认摄像头</option>
                  <option v-for="camera in availableCameras" :key="camera.deviceId" :value="camera.deviceId">
                    {{ camera.label }}
                  </option>
                </select>
                <span class="camera-picker__hint">
                  {{ isStreaming ? '修改后需重新启动摄像头才会生效。' : '启动时会使用当前选中的摄像头。' }}
                </span>
              </div>
            </div>

            <div class="action-row">
              <button type="button" class="btn btn-primary" @click="startCamera" :disabled="isStreaming || cameraLoading">
                {{ cameraLoading ? '启动中...' : '启动摄像头' }}
              </button>
              <button type="button" class="btn btn-danger" @click="stopCamera" :disabled="!isStreaming">
                停止摄像头
              </button>
              <button
                type="button"
                class="btn"
                :class="isProcessing ? 'btn-warning' : 'btn-success'"
                @click="toggleProcessing"
                :disabled="!isStreaming || !isConnected || processingLoading"
              >
                {{ isProcessing ? '暂停识别' : '开始识别' }}
              </button>
              <button type="button" class="btn btn-secondary" @click="saveCurrentReport" :disabled="!hasHistory || saving">
                {{ saving ? '保存中...' : '保存本次记录' }}
              </button>
              <button type="button" class="btn btn-secondary" @click="resetStatistics" :disabled="!hasHistory">
                重置统计
              </button>
              <button type="button" class="btn btn-secondary" @click="generateReport" :disabled="!hasHistory">
                下载报告
              </button>
            </div>

            <div class="status-row">
              <span class="status-chip" :class="{ active: isStreaming }">摄像头 {{ isStreaming ? '运行中' : '未启动' }}</span>
              <span class="status-chip" :class="{ active: isConnected }">WebSocket {{ isConnected ? '已连接' : '未连接' }}</span>
              <span class="status-chip" :class="{ warning: isProcessing }">识别 {{ isProcessing ? '进行中' : '已停止' }}</span>
              <span v-if="statistics.total_targets > 0" class="status-chip neutral">已检测总数 {{ statistics.total_targets }}</span>
            </div>
          </section>

          <section v-if="currentResults.length > 0" class="panel-card">
            <div class="panel-header">
              <div>
                <h2>当前识别结果</h2>
                <p>这里展示最近一帧中识别到的水果和成熟度。</p>
              </div>
            </div>

            <div class="result-grid">
              <div v-for="(res, idx) in currentResults" :key="idx" class="result-item">
                <div class="result-head">
                  <span class="fruit-name">{{ getFruitIcon(res.fruit_class) }} {{ res.fruit_class }}</span>
                  <span class="confidence">{{ (res.fruit_confidence * 100).toFixed(1) }}%</span>
                </div>
                <div v-if="res.ripeness" class="ripeness-line">
                  成熟度：{{ res.ripeness.class }} ({{ (res.ripeness.confidence * 100).toFixed(1) }}%)
                </div>
                <div class="bbox-line">位置：[{{ res.bbox.join(', ') }}]</div>
              </div>
            </div>
          </section>
        </div>

        <div class="workspace-side">
          <section v-if="statistics.total_targets > 0" class="panel-card">
            <div class="panel-header">
              <div>
                <h2>本次识别统计</h2>
                <p>统计当前会话中累计识别到的水果与成熟度分布。</p>
              </div>
            </div>

            <div class="stats-block">
              <h3>水果种类次数</h3>
              <div v-for="(item, idx) in sortedFruitStats" :key="item.fruit" class="stat-item">
                <div class="stat-top">
                  <span>{{ idx + 1 }}. {{ item.fruit }}</span>
                  <span>{{ item.count }}</span>
                </div>
                <div class="stat-bar">
                  <div class="stat-fill" :style="{ width: getPercentage(item.count, statistics.total_targets) + '%' }"></div>
                </div>
              </div>
            </div>

            <div v-if="sortedRipenessData.length" class="stats-block">
              <h3>成熟度分布</h3>
              <div v-for="item in sortedRipenessData" :key="`${item.fruit}-${item.ripeness}`" class="stat-item">
                <div class="stat-top">
                  <span>{{ item.fruit }} - {{ item.ripeness }}</span>
                  <span>{{ item.count }}</span>
                </div>
                <div class="stat-bar">
                  <div class="stat-fill alt" :style="{ width: getPercentage(item.count, getFruitTotal(item.fruit)) + '%' }"></div>
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
              <li>先启动摄像头，确认取景区域内水果清晰可见。</li>
              <li>点击“开始识别”后，系统会持续识别并更新右侧统计。</li>
              <li>如果要开始新一轮统计，可点击“重置统计”。</li>
              <li>本次会话可保存到历史，也可以直接下载 JSON 报告。</li>
            </ul>
          </section>
        </div>
      </section>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { saveRealtimeReport } from '@/api/detection'

export default {
  name: 'RealtimeDetectionView',
  data() {
    return {
      autoSaved: false,
      isStreaming: false,
      cameraLoading: false,
      cameraScanLoading: false,
      videoStream: null,
      videoElement: null,
      canvasElement: null,
      canvasContext: null,
      availableCameras: [],
      selectedCameraId: '',
      websocket: null,
      isConnected: false,
      processingLoading: false,
      reconnectCount: 0,
      maxReconnect: 3,
      isProcessing: false,
      sendInterval: null,
      targetFPS: 5,
      imageQuality: 0.7,
      currentResults: [],
      fps: 0,
      statistics: {
        total_targets: 0,
        fruit_counts: {},
        ripeness_counts: {}
      },
      lastSendTime: 0,
      fpsCounter: 0,
      fpsUpdateTimer: null,
      errorMessage: '',
      saving: false
    }
  },
  computed: {
    sortedFruitStats() {
      const entries = Object.entries(this.statistics.fruit_counts)
      return entries.map(([fruit, count]) => ({ fruit, count })).sort((a, b) => b.count - a.count)
    },
    sortedRipenessData() {
      const result = []
      Object.entries(this.statistics.ripeness_counts).forEach(([fruit, ripes]) => {
        Object.entries(ripes).forEach(([ripeness, count]) => {
          result.push({ fruit, ripeness, count })
        })
      })
      return result.sort((a, b) => {
        if (a.fruit !== b.fruit) return a.fruit.localeCompare(b.fruit)
        return b.count - a.count
      })
    },
    hasHistory() {
      return this.statistics.total_targets > 0
    }
  },
  mounted() {
    this.initCanvas()
    this.startFPSMonitor()
    this.loadCameraDevices()
  },
  beforeUnmount() {
    this.cleanup()
  },
  methods: {
    initCanvas() {
      this.videoElement = this.$refs.videoElement
      this.canvasElement = this.$refs.canvasElement
      if (this.canvasElement) {
        this.canvasContext = this.canvasElement.getContext('2d')
      }
    },
    startFPSMonitor() {
      this.fpsUpdateTimer = setInterval(() => {
        this.fps = this.fpsCounter
        this.fpsCounter = 0
      }, 1000)
    },
    async loadCameraDevices(requestPermission = false) {
      if (!navigator.mediaDevices || !navigator.mediaDevices.enumerateDevices) {
        return
      }

      this.cameraScanLoading = true
      try {
        let tempStream = null
        if (requestPermission) {
          try {
            tempStream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false })
          } catch (error) {
            console.warn('camera permission warmup failed', error)
          }
        }

        const devices = await navigator.mediaDevices.enumerateDevices()
        const cameras = devices
          .filter((device) => device.kind === 'videoinput')
          .map((device, index) => ({
            deviceId: device.deviceId,
            label: device.label || `摄像头 ${index + 1}`
          }))

        this.availableCameras = cameras

        if (this.selectedCameraId && !cameras.some((camera) => camera.deviceId === this.selectedCameraId)) {
          this.selectedCameraId = ''
        }
        if (!this.selectedCameraId && cameras.length === 1) {
          this.selectedCameraId = cameras[0].deviceId
        }

        if (tempStream) {
          tempStream.getTracks().forEach((track) => track.stop())
        }
      } catch (error) {
        console.error('enumerate camera devices failed', error)
      } finally {
        this.cameraScanLoading = false
      }
    },
    onCameraSelectionChange() {
      if (this.isStreaming) {
        ElMessage.info('已切换选择，重新启动摄像头后生效')
      }
    },
    async startCamera() {
      this.cameraLoading = true
      this.errorMessage = ''
      this.reconnectCount = 0
      try {
        if (!this.availableCameras.length) {
          await this.loadCameraDevices(true)
        }

        const videoConstraints = {
          width: { ideal: 640 },
          height: { ideal: 480 }
        }
        if (this.selectedCameraId) {
          videoConstraints.deviceId = { exact: this.selectedCameraId }
        } else {
          videoConstraints.facingMode = 'environment'
        }

        const stream = await navigator.mediaDevices.getUserMedia({
          video: videoConstraints,
          audio: false
        })
        this.videoStream = stream
        this.videoElement.srcObject = stream
        await this.videoElement.play()
        this.isStreaming = true
        await this.loadCameraDevices()
        this.startDrawing()
        await this.connectWebSocket()
      } catch (err) {
        console.error('开启摄像头失败:', err)
        this.errorMessage = `无法访问摄像头: ${err.message}`
      } finally {
        this.cameraLoading = false
      }
    },
    startDrawing() {
      const drawFrame = () => {
        if (!this.isStreaming) return
        if (this.canvasContext && this.videoElement) {
          if (this.canvasElement.width !== this.videoElement.videoWidth) {
            this.canvasElement.width = this.videoElement.videoWidth
            this.canvasElement.height = this.videoElement.videoHeight
          }
          this.canvasContext.drawImage(this.videoElement, 0, 0, this.canvasElement.width, this.canvasElement.height)
          if (this.currentResults.length > 0) {
            this.drawDetections(this.currentResults)
          }
        }
        requestAnimationFrame(drawFrame)
      }
      drawFrame()
    },
    drawDetections(predictions) {
      const ctx = this.canvasContext
      if (!ctx) return

      const scaleX = this.canvasElement.width / this.videoElement.videoWidth
      const scaleY = this.canvasElement.height / this.videoElement.videoHeight

      predictions.forEach((pred) => {
        const [x1, y1, x2, y2] = pred.bbox.map((v, i) => (i % 2 === 0 ? v * scaleX : v * scaleY))
        const width = x2 - x1
        const height = y2 - y1

        ctx.strokeStyle = '#ef4444'
        ctx.lineWidth = 2
        ctx.strokeRect(x1, y1, width, height)

        let label = `${pred.fruit_class} ${(pred.fruit_confidence * 100).toFixed(1)}%`
        if (pred.ripeness) {
          label += ` | ${pred.ripeness.class}`
        }

        ctx.font = 'bold 14px "Microsoft YaHei", Arial'
        const textWidth = ctx.measureText(label).width
        const textHeight = 20

        ctx.fillStyle = 'rgba(0,0,0,0.7)'
        ctx.fillRect(x1, y1 - textHeight - 4, textWidth + 8, textHeight + 4)

        ctx.fillStyle = '#fff'
        ctx.fillText(label, x1 + 4, y1 - 6)
      })
    },
    async connectWebSocket() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/fruit-recognition/`
      this.websocket = new WebSocket(wsUrl)

      this.websocket.onopen = () => {
        this.isConnected = true
        this.reconnectCount = 0
      }

      this.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.status === 'success') {
          this.currentResults = data.predictions
          this.fpsCounter++
          if (this.isProcessing) {
            this.updateStatistics(data.predictions)
          }
        } else if (data.status === 'error') {
          console.error('识别错误:', data.error)
          this.errorMessage = data.error
        }
      }

      this.websocket.onclose = () => {
        this.isConnected = false
        if (this.isProcessing) {
          this.stopProcessing()
          ElMessage.warning('WebSocket 断开，识别已停止')
        }

        if (this.isStreaming && this.reconnectCount < this.maxReconnect) {
          this.reconnectCount++
          setTimeout(() => this.connectWebSocket(), 2000)
        } else if (this.reconnectCount >= this.maxReconnect) {
          ElMessage.error('WebSocket 连接失败，请检查后端服务')
        }
      }

      this.websocket.onerror = (err) => {
        console.error('WebSocket 错误:', err)
        this.errorMessage = 'WebSocket 连接失败'
      }
    },
    updateStatistics(predictions) {
      this.statistics.total_targets += predictions.length

      predictions.forEach((pred) => {
        const fruit = pred.fruit_class
        this.statistics.fruit_counts[fruit] = (this.statistics.fruit_counts[fruit] || 0) + 1

        if (pred.ripeness) {
          if (!this.statistics.ripeness_counts[fruit]) {
            this.statistics.ripeness_counts[fruit] = {}
          }
          const ripeClass = pred.ripeness.class
          this.statistics.ripeness_counts[fruit][ripeClass] =
            (this.statistics.ripeness_counts[fruit][ripeClass] || 0) + 1
        }
      })
    },
    startProcessing() {
      if (!this.isConnected) {
        ElMessage.error('WebSocket 未连接，请检查服务端')
        return
      }
      if (this.statistics.total_targets === 0) {
        this.statistics = {
          total_targets: 0,
          fruit_counts: {},
          ripeness_counts: {}
        }
        this.autoSaved = false
      }
      this.isProcessing = true
      ElMessage.success('开始实时识别')

      const interval = 1000 / this.targetFPS
      this.sendInterval = setInterval(() => {
        if (this.isProcessing && this.isConnected && this.canvasElement) {
          this.sendFrame()
        }
      }, interval)
    },
    stopProcessing() {
      if (this.sendInterval) {
        clearInterval(this.sendInterval)
        this.sendInterval = null
      }
      this.isProcessing = false
      ElMessage.info('识别已暂停')
    },
    toggleProcessing() {
      if (this.isProcessing) {
        this.stopProcessing()
      } else {
        this.startProcessing()
      }
    },
    sendFrame() {
      if (!this.canvasElement || !this.websocket || this.websocket.readyState !== WebSocket.OPEN) return
      const dataURL = this.canvasElement.toDataURL('image/jpeg', this.imageQuality)
      this.websocket.send(dataURL)
    },
    resetStatistics() {
      if (this.statistics.total_targets === 0) return
      if (!this.autoSaved && this.statistics.total_targets > 0) {
        this.autoSaveReport()
      }
      this.statistics = {
        total_targets: 0,
        fruit_counts: {},
        ripeness_counts: {}
      }
      this.currentResults = []
      this.autoSaved = false
      ElMessage.info('统计已重置，之前的数据已保存')
    },
    async autoSaveReport(snapshot = null) {
      if (this.saving) return
      if (!snapshot && this.statistics.total_targets === 0) return

      this.saving = true
      try {
        const payload = snapshot || {
          total_targets: this.statistics.total_targets,
          fruit_counts: { ...this.statistics.fruit_counts },
          ripeness_counts: JSON.parse(JSON.stringify(this.statistics.ripeness_counts))
        }
        await saveRealtimeReport(payload)
        this.autoSaved = true
        ElMessage.success('检测报告已自动保存至历史记录')
      } catch (error) {
        console.error('自动保存失败:', error)
      } finally {
        this.saving = false
      }
    },
    async saveCurrentReport() {
      if (this.statistics.total_targets === 0) {
        ElMessage.warning('暂无数据可保存')
        return
      }
      if (this.autoSaved) {
        ElMessage.info('当前会话数据已保存过，无需重复保存')
        return
      }
      await this.autoSaveReport()
    },
    generateReport() {
      if (this.statistics.total_targets === 0) {
        ElMessage.warning('暂无识别数据，请先开始识别')
        return
      }

      const reportData = {
        total_targets: this.statistics.total_targets,
        fruit_counts: this.statistics.fruit_counts,
        ripeness_counts: this.statistics.ripeness_counts,
        timestamp: new Date().toISOString(),
        duration: '实时检测会话'
      }

      const blob = new Blob([JSON.stringify(reportData, null, 2)], { type: 'application/json' })
      const url = URL.createObjectURL(blob)
      const a = document.createElement('a')
      a.href = url
      a.download = `realtime_report_${Date.now()}.json`
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
      URL.revokeObjectURL(url)

      ElMessage.success('报告已生成并下载')
    },
    async stopCamera() {
      this.stopProcessing()

      if (this.statistics.total_targets > 0 && !this.autoSaved) {
        await this.autoSaveReport()
      }

      if (this.videoStream) {
        this.videoStream.getTracks().forEach((track) => track.stop())
        this.videoStream = null
      }

      if (this.websocket) {
        this.websocket.close()
      }

      this.isStreaming = false
      this.isConnected = false
      this.currentResults = []
      this.statistics = { total_targets: 0, fruit_counts: {}, ripeness_counts: {} }
      this.errorMessage = ''
      this.reconnectCount = 0

      if (this.canvasContext) {
        this.canvasContext.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height)
      }

      ElMessage.info('摄像头已关闭')
    },
    cleanup() {
      if (this.sendInterval) clearInterval(this.sendInterval)
      if (this.fpsUpdateTimer) clearInterval(this.fpsUpdateTimer)
      if (this.videoStream) {
        this.videoStream.getTracks().forEach((track) => track.stop())
      }
      if (this.websocket) {
        this.websocket.close()
      }
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
    getPercentage(count, total) {
      if (!total) return 0
      return ((count / total) * 100).toFixed(1)
    },
    getFruitTotal(fruit) {
      return this.statistics.fruit_counts[fruit] || 0
    }
  }
}
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
.panel-header h2 {
  margin: 0 0 6px;
  font-size: 18px;
  color: #18352b;
}

.guide-step p,
.panel-header p {
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

.video-wrapper {
  position: relative;
  overflow: hidden;
  border-radius: 22px;
  background: linear-gradient(140deg, #0f172a 0%, #1a2c43 100%);
  min-height: 420px;
}

.camera-picker {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 18px;
  background: #f6faf7;
}

.camera-picker__header,
.camera-picker__row {
  display: flex;
  gap: 12px;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
}

.camera-picker__row {
  margin-top: 12px;
}

.camera-picker__hint {
  color: #587166;
  font-size: 13px;
}

.camera-select {
  min-width: 260px;
  max-width: 100%;
  padding: 10px 12px;
  border: 1px solid #d7e3dc;
  border-radius: 12px;
  background: #fff;
  color: #173b32;
}

.video-preview,
.overlay-canvas {
  width: 100%;
  height: auto;
  display: block;
}

.overlay-canvas {
  position: absolute;
  inset: 0;
}

.action-row,
.status-row {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  margin-top: 16px;
}

.status-chip {
  padding: 6px 10px;
  border-radius: 999px;
  background: #edf3ef;
  color: #587166;
  font-size: 13px;
}

.status-chip.active {
  background: #eef9f3;
  color: #18533a;
}

.status-chip.warning {
  background: #fff8eb;
  color: #7c5a13;
}

.status-chip.neutral {
  background: #eef2f0;
  color: #35594d;
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
  font-weight: 700;
}

.ripeness-line,
.bbox-line {
  margin-top: 8px;
  color: #587166;
  font-size: 13px;
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
  gap: 12px;
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

.btn-warning {
  background: #f59e0b;
  color: #fff;
}

.btn-danger {
  background: #d92d20;
  color: #fff;
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
  .realtime-page {
    padding: 12px;
  }

  .hero {
    padding: 22px 20px;
  }

  .hero h1 {
    font-size: 30px;
  }

  .panel-header,
  .action-row,
  .camera-picker__header,
  .camera-picker__row,
  .status-row,
  .result-head,
  .stat-top {
    flex-direction: column;
  }

  .video-wrapper {
    min-height: 280px;
  }
}
</style>
