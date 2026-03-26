<template>
  <div class="realtime-detection">
    <div class="container">
      <h1>🍎 实时水果识别系统</h1>

      <!-- 摄像头画面 -->
      <div class="video-wrapper">
        <video ref="videoElement" class="video-preview" autoplay playsinline muted></video>
        <canvas ref="canvasElement" class="overlay-canvas"></canvas>
      </div>

      <!-- 控制栏 -->
      <div class="controls">
        <el-button
          type="primary"
          @click="startCamera"
          :disabled="isStreaming"
          :loading="cameraLoading"
        >
          <el-icon><Camera /></el-icon> 开启摄像头
        </el-button>
        <el-button
          type="danger"
          @click="stopCamera"
          :disabled="!isStreaming"
        >
          <el-icon><Close /></el-icon> 关闭摄像头
        </el-button>
        <el-button
          :type="isProcessing ? 'warning' : 'success'"
          @click="toggleProcessing"
          :disabled="!isStreaming || !isConnected"
          :loading="processingLoading"
        >
          <el-icon><VideoCamera /></el-icon>
          {{ isProcessing ? '停止识别' : '开始识别' }}
        </el-button>
        <el-button
          type="info"
          @click="generateReport"
          :disabled="!hasHistory"
        >
          <el-icon><Document /></el-icon> 生成报告
        </el-button>
      </div>

      <!-- 实时识别结果 -->
      <div v-if="currentResults.length > 0" class="results-panel">
        <h3>📊 实时检测结果 <span class="fps-badge">{{ fps }} fps</span></h3>
        <div class="results-list">
          <div
            v-for="(res, idx) in currentResults"
            :key="idx"
            class="result-item"
          >
            <div class="result-header">
              <span class="fruit-name">
                <span class="fruit-icon">{{ getFruitIcon(res.fruit_class) }}</span>
                {{ res.fruit_class }}
              </span>
              <span class="confidence">{{ (res.fruit_confidence * 100).toFixed(1) }}%</span>
            </div>
            <div v-if="res.ripeness" class="ripeness">
              🍌 成熟度: {{ res.ripeness.class }} ({{ (res.ripeness.confidence * 100).toFixed(1) }}%)
            </div>
            <div class="bbox-info">位置: [{{ res.bbox.join(',') }}]</div>
          </div>
        </div>
      </div>

      <!-- 统计概览 -->
      <div v-if="statistics.total_targets > 0" class="stats-panel">
        <h3>📈 本次识别统计</h3>
        <el-row :gutter="20">
          <el-col :span="12">
            <div class="stat-card">
              <h4>水果种类次数</h4>
              <div v-for="(item, idx) in sortedFruitStats" :key="item.fruit" class="stat-item">
                <span>{{ idx + 1 }}. {{ item.fruit }}</span>
                <el-progress :percentage="getPercentage(item.count, statistics.total_targets)" :stroke-width="8" />
                <span class="count">{{ item.count }} 次</span>
              </div>
            </div>
          </el-col>
          <el-col :span="12">
            <div v-if="sortedRipenessData.length" class="stat-card">
              <h4>成熟度分布</h4>
              <div v-for="item in sortedRipenessData" :key="`${item.fruit}-${item.ripeness}`" class="stat-item">
                <span>{{ item.fruit }} - {{ item.ripeness }}</span>
                <el-progress :percentage="getPercentage(item.count, getFruitTotal(item.fruit))" :stroke-width="8" />
                <span class="count">{{ item.count }} 次</span>
              </div>
            </div>
          </el-col>
        </el-row>
      </div>

      <!-- 状态指示器 -->
      <div class="status-bar">
        <el-tag :type="isStreaming ? 'success' : 'info'">摄像头: {{ isStreaming ? '运行中' : '未启动' }}</el-tag>
        <el-tag :type="isConnected ? 'success' : 'danger'">WebSocket: {{ isConnected ? '已连接' : '未连接' }}</el-tag>
        <el-tag :type="isProcessing ? 'warning' : 'info'">识别: {{ isProcessing ? '进行中' : '已停止' }}</el-tag>
        <el-tag v-if="statistics.total_targets > 0">已检测目标总数: {{ statistics.total_targets }}</el-tag>
      </div>

      <!-- 错误提示 -->
      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        :closable="true"
        @close="errorMessage = ''"
        show-icon
      />
    </div>
  </div>
</template>

<script>
import { Camera, Close, VideoCamera, Document } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'

export default {
  name: 'RealtimeDetectionView',
  components: { Camera, Close, VideoCamera, Document },
  data() {
    return {
      // 摄像头相关
      isStreaming: false,
      cameraLoading: false,
      videoStream: null,
      videoElement: null,
      canvasElement: null,
      canvasContext: null,

      // WebSocket
      websocket: null,
      isConnected: false,
      processingLoading: false,
      reconnectCount: 0,
      maxReconnect: 3,

      // 识别控制
      isProcessing: false,
      sendInterval: null,
      targetFPS: 5,              // 发送帧率
      imageQuality: 0.7,        // 图像质量

      // 识别结果
      currentResults: [],
      fps: 0,

      // 统计报告（符合视频报告格式）
      statistics: {
        total_targets: 0,        // 所有帧中检测到的目标总数
        fruit_counts: {},        // 水果名称 -> 出现次数
        ripeness_counts: {}      // 水果名称 -> { 成熟度名称 -> 次数 }
      },

      // 性能监控
      lastSendTime: 0,
      fpsCounter: 0,
      fpsUpdateTimer: null,

      // UI状态
      errorMessage: ''
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
      // 按水果名称排序，再按次数降序
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

    async startCamera() {
      this.cameraLoading = true
      this.errorMessage = ''
      this.reconnectCount = 0
      try {
        const stream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: 640 },
            height: { ideal: 480 },
            facingMode: 'environment'
          },
          audio: false
        })
        this.videoStream = stream
        this.videoElement.srcObject = stream
        await this.videoElement.play()
        this.isStreaming = true
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
          // 设置画布尺寸与视频实际尺寸一致
          if (this.canvasElement.width !== this.videoElement.videoWidth) {
            this.canvasElement.width = this.videoElement.videoWidth
            this.canvasElement.height = this.videoElement.videoHeight
          }
          // 绘制视频帧到画布
          this.canvasContext.drawImage(this.videoElement, 0, 0, this.canvasElement.width, this.canvasElement.height)

          // 如果有检测结果，绘制框和标签
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

      // 缩放因子（如果画布与视频尺寸一致则为1）
      const scaleX = this.canvasElement.width / this.videoElement.videoWidth
      const scaleY = this.canvasElement.height / this.videoElement.videoHeight

      predictions.forEach(pred => {
        const [x1, y1, x2, y2] = pred.bbox.map((v, i) => (i % 2 === 0 ? v * scaleX : v * scaleY))
        const width = x2 - x1
        const height = y2 - y1

        // 绘制边框
        ctx.strokeStyle = '#f00'
        ctx.lineWidth = 2
        ctx.strokeRect(x1, y1, width, height)

        // 标签文本
        let label = `${pred.fruit_class} ${(pred.fruit_confidence * 100).toFixed(1)}%`
        if (pred.ripeness) {
          label += ` | ${pred.ripeness.class}`
        }

        // 测量文本宽度
        ctx.font = 'bold 14px "Microsoft YaHei", Arial'
        const textWidth = ctx.measureText(label).width
        const textHeight = 20

        // 背景
        ctx.fillStyle = 'rgba(0,0,0,0.7)'
        ctx.fillRect(x1, y1 - textHeight - 4, textWidth + 8, textHeight + 4)

        // 文字
        ctx.fillStyle = '#fff'
        ctx.fillText(label, x1 + 4, y1 - 6)
      })
    },

    async connectWebSocket() {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const wsUrl = `${protocol}//${window.location.hostname}:8000/ws/fruit-recognition/`
      this.websocket = new WebSocket(wsUrl)

      this.websocket.onopen = () => {
        console.log('WebSocket 连接已建立')
        this.isConnected = true
        this.reconnectCount = 0
      }

      this.websocket.onmessage = (event) => {
        const data = JSON.parse(event.data)
        if (data.status === 'success') {
          this.currentResults = data.predictions
          this.fpsCounter++

          // 只有在识别状态下才更新统计
          if (this.isProcessing) {
            this.updateStatistics(data.predictions)
          }
        } else if (data.status === 'error') {
          console.error('识别错误:', data.error)
          this.errorMessage = data.error
        }
      }

      this.websocket.onclose = (event) => {
        console.log('WebSocket 连接已关闭', event)
        this.isConnected = false
        if (this.isProcessing) {
          this.stopProcessing()
          ElMessage.warning('WebSocket 断开，识别已停止')
        }

        // 自动重连（仅当摄像头开启且未达到最大重连次数）
        if (this.isStreaming && this.reconnectCount < this.maxReconnect) {
          this.reconnectCount++
          console.log(`尝试重连 WebSocket (${this.reconnectCount}/${this.maxReconnect})...`)
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
      // 累加目标总数（每个检测到的目标算一个）
      this.statistics.total_targets += predictions.length

      predictions.forEach(pred => {
        const fruit = pred.fruit_class
        // 水果计数
        this.statistics.fruit_counts[fruit] = (this.statistics.fruit_counts[fruit] || 0) + 1

        // 成熟度计数
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

    toggleProcessing() {
      if (this.isProcessing) {
        this.stopProcessing()
      } else {
        this.startProcessing()
      }
    },

    startProcessing() {
      if (!this.isConnected) {
        ElMessage.error('WebSocket 未连接，请检查服务器')
        return
      }
      // 重置统计数据，开始新一轮识别
      this.statistics = {
        total_targets: 0,
        fruit_counts: {},
        ripeness_counts: {}
      }
      this.currentResults = []
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
      ElMessage.info('识别已停止')
    },

    sendFrame() {
      if (!this.canvasElement) return
      // 将画布内容转为 base64 (JPEG 质量 0.7)
      const dataURL = this.canvasElement.toDataURL('image/jpeg', this.imageQuality)
      this.websocket.send(dataURL)
    },

    generateReport() {
      if (this.statistics.total_targets === 0) {
        ElMessage.warning('暂无识别数据，请先开始识别')
        return
      }

      // 构建与视频报告一致的 JSON 结构
      const reportData = {
        total_targets: this.statistics.total_targets,
        fruit_counts: this.statistics.fruit_counts,
        ripeness_counts: this.statistics.ripeness_counts,
        timestamp: new Date().toISOString(),
        duration: '实时检测会话'
      }

      // 下载为 JSON 文件
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

    stopCamera() {
      this.stopProcessing()
      if (this.videoStream) {
        this.videoStream.getTracks().forEach(track => track.stop())
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

      // 清空画布
      if (this.canvasContext) {
        this.canvasContext.clearRect(0, 0, this.canvasElement.width, this.canvasElement.height)
      }
      ElMessage.info('摄像头已关闭')
    },

    cleanup() {
      if (this.sendInterval) clearInterval(this.sendInterval)
      if (this.fpsUpdateTimer) clearInterval(this.fpsUpdateTimer)
      this.stopCamera()
    },

    getFruitIcon(fruit) {
      const iconMap = {
        '香蕉': '🍌',
        '芒果': '🥭',
        '草莓': '🍓',
        '苹果': '🍎',
        '橙子': '🍊',
        '葡萄': '🍇',
        '西瓜': '🍉',
        '菠萝': '🍍',
        '猕猴桃': '🥝',
        '柠檬': '🍋'
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
/* 样式与原有保持一致，仅作微调，此处省略重复部分，但必须包含完整样式 */
.realtime-detection {
  padding: 20px;
  font-family: 'Arial', 'Microsoft YaHei', sans-serif;
}

.container {
  max-width: 1200px;
  margin: 0 auto;
}

h1 {
  text-align: center;
  color: #2c3e50;
  margin-bottom: 30px;
}

.video-wrapper {
  position: relative;
  width: 100%;
  margin-bottom: 20px;
  border-radius: 12px;
  overflow: hidden;
  background: #000;
  box-shadow: 0 4px 12px rgba(0,0,0,0.2);
}

.video-preview {
  width: 100%;
  height: auto;
  display: block;
}

.overlay-canvas {
  position: absolute;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  pointer-events: none;
}

.controls {
  display: flex;
  gap: 12px;
  justify-content: center;
  margin-bottom: 24px;
  flex-wrap: wrap;
}

.results-panel {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  max-height: 300px;
  overflow-y: auto;
}

.results-panel h3 {
  margin-top: 0;
  margin-bottom: 15px;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.fps-badge {
  font-size: 14px;
  background: #409eff;
  color: white;
  padding: 2px 8px;
  border-radius: 20px;
}

.results-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.result-item {
  background: white;
  border-radius: 8px;
  padding: 12px;
  border-left: 4px solid #409eff;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.result-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 8px;
}

.fruit-name {
  font-weight: bold;
  font-size: 16px;
}

.fruit-icon {
  margin-right: 6px;
  font-size: 18px;
}

.confidence {
  color: #67c23a;
  font-weight: bold;
}

.ripeness {
  font-size: 13px;
  color: #e6a23c;
  margin-bottom: 6px;
}

.bbox-info {
  font-size: 12px;
  color: #909399;
  font-family: monospace;
}

.stats-panel {
  background: #fff;
  border-radius: 12px;
  padding: 20px;
  margin-bottom: 20px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.stats-panel h3 {
  margin-top: 0;
  margin-bottom: 20px;
  color: #2c3e50;
}

.stat-card {
  background: #f8f9fa;
  border-radius: 8px;
  padding: 16px;
  height: 100%;
}

.stat-card h4 {
  margin: 0 0 12px 0;
  color: #606266;
  font-size: 16px;
}

.stat-item {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 12px;
}

.stat-item span:first-child {
  width: 100px;
  font-weight: 500;
}

.stat-item .count {
  min-width: 60px;
  text-align: right;
  color: #409eff;
  font-weight: bold;
}

.status-bar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
  justify-content: center;
  margin-bottom: 20px;
}

@media (max-width: 768px) {
  .controls {
    flex-direction: column;
    align-items: center;
  }
  .controls .el-button {
    width: 200px;
  }
  .stat-item {
    flex-wrap: wrap;
  }
  .stat-item .el-progress {
    flex: 1;
  }
}
</style>