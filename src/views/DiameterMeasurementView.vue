<template>
  <div class="diameter-page">
    <div class="page-shell">
      <section class="hero">
        <div>
          <p class="eyebrow">Stereo Diameter Measurement</p>
          <h1>双 USB 摄像头果径测量</h1>
          <p class="hero-text">
            先确认双摄索引，再采集棋盘格完成当前设备标定，最后执行 YOLO + MonSter 果径测量。
          </p>
        </div>
        <div class="hero-actions">
          <el-button plain :loading="statusLoading" @click="loadStatus">刷新相机状态</el-button>
          <el-button plain type="warning" :loading="probing" @click="probeCameras">扫描索引</el-button>
          <el-button plain type="info" :loading="runtimeLoading" @click="loadRuntimeStatus">刷新运行时</el-button>
          <el-button plain type="primary" @click="usageDialogVisible = true">使用说明</el-button>
        </div>
      </section>

      <section class="layout-grid">
        <div class="left-column">
          <el-card shadow="never" class="control-card">
            <template #header>
              <div class="card-header">
                <span>摄像头配置</span>
                <el-tag :type="cameraStatus.active ? 'success' : 'info'">
                  {{ cameraStatus.active ? '运行中' : '未启动' }}
                </el-tag>
              </div>
            </template>

            <el-form label-position="top" class="camera-form">
              <el-form-item label="输入模式">
                <el-select v-model="form.source_mode">
                  <el-option label="单设备双目（左右拼接）" value="single" />
                  <el-option label="双设备双目" value="dual" />
                </el-select>
              </el-form-item>

              <el-form-item v-if="form.source_mode === 'single'" label="camera_index">
                <el-input-number v-model="form.camera_index" :min="0" :step="1" />
              </el-form-item>

              <template v-else>
                <el-form-item label="left_camera_index">
                  <el-input-number v-model="form.left_camera_index" :min="0" :step="1" />
                </el-form-item>
                <el-form-item label="right_camera_index">
                  <el-input-number v-model="form.right_camera_index" :min="0" :step="1" />
                </el-form-item>
              </template>

              <el-form-item label="split_mode">
                <el-select v-model="form.split_mode">
                  <el-option label="left_right" value="left_right" />
                  <el-option label="top_bottom" value="top_bottom" />
                </el-select>
              </el-form-item>

              <div class="inline-grid">
                <el-form-item label="宽度">
                  <el-input-number v-model="form.frame_width" :min="1" :step="1" />
                </el-form-item>
                <el-form-item label="高度">
                  <el-input-number v-model="form.frame_height" :min="1" :step="1" />
                </el-form-item>
              </div>

              <div class="inline-grid">
                <el-form-item label="FPS">
                  <el-input-number v-model="form.fps" :min="1" :max="120" :step="1" />
                </el-form-item>
                <el-form-item label="YOLO 置信度">
                  <el-input-number v-model="form.conf" :min="0.01" :max="1" :step="0.01" :precision="2" />
                </el-form-item>
              </div>

              <div class="switch-row">
                <span>预览时叠加 YOLO 检测框</span>
                <el-switch v-model="detectPreview" @change="refreshPreview" />
              </div>

              <div class="switch-row">
                <span>测量后保存可视化结果</span>
                <el-switch v-model="form.save_vis" />
              </div>

              <div class="button-group">
                <el-button type="primary" :loading="starting" @click="startCamera">启动摄像头</el-button>
                <el-button type="danger" :disabled="!cameraStatus.active" @click="stopCamera">停止摄像头</el-button>
                <el-button
                  type="success"
                  :loading="measuring"
                  :disabled="!cameraStatus.active"
                  @click="measureCurrentFrame"
                >
                  测量当前帧
                </el-button>
                <el-button plain type="info" @click="usageDialogVisible = true">
                  查看使用说明
                </el-button>
              </div>
            </el-form>

            <div class="status-panel">
              <div class="status-line">
                <span>最后取流时间</span>
                <strong>{{ lastFrameTime }}</strong>
              </div>
              <div class="status-line">
                <span>最近错误</span>
                <strong>{{ cameraStatus.last_open_error || '无' }}</strong>
              </div>
              <div class="status-line">
                <span>当前配置</span>
                <strong>{{ configSummary }}</strong>
              </div>
            </div>
          </el-card>

          <el-card shadow="never" class="control-card">
            <template #header>
              <div class="card-header">
                <span>MonSter 运行时</span>
                <el-tag :type="runtimeTagType">{{ runtimeDeviceLabel }}</el-tag>
              </div>
            </template>

            <div v-if="runtimeStatus" class="runtime-grid">
              <div class="status-line">
                <span>设备偏好</span>
                <strong>{{ runtimeStatus.device_setting || runtimeStatus.preferred_device || 'auto' }}</strong>
              </div>
              <div class="status-line">
                <span>当前设备</span>
                <strong>{{ runtimeStatus.device_type || '-' }}</strong>
              </div>
              <div class="status-line">
                <span>PyTorch</span>
                <strong>{{ runtimeStatus.torch_version || '-' }}</strong>
              </div>
              <div class="status-line">
                <span>CUDA</span>
                <strong>{{ runtimeStatus.torch_cuda_version || '未启用' }}</strong>
              </div>
              <div class="status-line">
                <span>GPU 数量</span>
                <strong>{{ runtimeStatus.device_count ?? 0 }}</strong>
              </div>
              <div class="status-line">
                <span>标定文件</span>
                <strong class="path-text">{{ runtimeStatus.calib_path || '-' }}</strong>
              </div>
            </div>

            <el-alert
              v-if="runtimeStatus && runtimeStatus.device_type !== 'cuda'"
              title="当前 MonSter 仍运行在 CPU。你机器有 NVIDIA GPU，但 shuiguo 环境里的 PyTorch 目前是 CPU 版，需要安装 CUDA 版 PyTorch 才能真正切到 GPU。"
              type="warning"
              :closable="false"
              show-icon
            />
          </el-card>

          <el-card shadow="never" class="control-card">
            <template #header>
              <div class="card-header">
                <span>双摄探测</span>
                <el-tag type="warning">推荐 {{ recommendedPairText }}</el-tag>
              </div>
            </template>

            <div v-if="probeResults.length" class="probe-panel">
              <div
                v-for="item in probeResults"
                :key="item.camera_index"
                class="probe-item"
                :class="{ success: item.opened }"
              >
                <div>
                  <strong>索引 {{ item.camera_index }}</strong>
                  <span>{{ item.opened ? '可打开' : '不可打开' }}</span>
                </div>
                <small v-if="item.opened">
                  {{ item.frame_width || '-' }} x {{ item.frame_height || '-' }}
                  <span v-if="item.fps"> | {{ item.fps }} fps</span>
                </small>
              </div>

              <div v-if="pairProbeResults.length" class="pair-list">
                <div class="pair-title">双摄组合</div>
                <div
                  v-for="pair in pairProbeResults"
                  :key="`${pair.left_camera_index}-${pair.right_camera_index}`"
                  class="probe-item"
                  :class="{ success: pair.simultaneous_ok }"
                >
                  <div>
                    <strong>{{ pair.left_camera_index }} / {{ pair.right_camera_index }}</strong>
                    <span>{{ pair.simultaneous_ok ? '可同时打开' : '不可同时打开' }}</span>
                  </div>
                  <small>L={{ pair.left_read_ok ? 'ok' : 'fail' }} | R={{ pair.right_read_ok ? 'ok' : 'fail' }}</small>
                </div>
              </div>
            </div>
            <div v-else class="empty-hint">先点击“扫描索引”，确认当前双摄组合。</div>
          </el-card>
        </div>

        <div class="right-column">
          <el-card shadow="never" class="preview-card">
            <template #header>
              <div class="card-header">
                <span>双目预览</span>
                <el-tag :type="previewUrl ? 'success' : 'info'">
                  {{ previewUrl ? '已连接' : '等待启动' }}
                </el-tag>
              </div>
            </template>

            <div class="preview-stage">
              <img v-if="previewUrl" :src="previewUrl" alt="stereo preview" class="preview-image" @error="handlePreviewError" />
              <div v-if="previewError" class="preview-error">{{ previewError }}</div>
              <div v-if="!previewUrl" class="preview-placeholder">
                启动摄像头后，这里会显示左右拼接的双目画面。
              </div>
            </div>
          </el-card>

          <el-card shadow="never" class="control-card">
            <template #header>
              <div class="card-header">
                <span>当前设备标定</span>
                <el-tag :type="calibrationPairCount >= calibrationForm.min_pairs ? 'success' : 'info'">
                  已采集 {{ calibrationPairCount }} 组
                </el-tag>
              </div>
            </template>

            <el-form label-position="top" class="camera-form">
              <div class="inline-grid">
                <el-form-item label="棋盘列数">
                  <el-input-number v-model="calibrationForm.cols" :min="3" :max="32" />
                </el-form-item>
                <el-form-item label="棋盘行数">
                  <el-input-number v-model="calibrationForm.rows" :min="3" :max="32" />
                </el-form-item>
              </div>

              <div class="inline-grid">
                <el-form-item label="方格边长(mm)">
                  <el-input-number v-model="calibrationForm.square_mm" :min="0.1" :step="0.1" :precision="1" />
                </el-form-item>
                <el-form-item label="最少有效组数">
                  <el-input-number v-model="calibrationForm.min_pairs" :min="4" :max="64" />
                </el-form-item>
              </div>

              <div class="switch-row">
                <span>标定成功后立即激活到测量服务</span>
                <el-switch v-model="calibrationForm.activate" />
              </div>

              <div class="button-group">
                <el-button
                  type="primary"
                  :loading="capturingCalibration"
                  :disabled="!cameraStatus.active"
                  @click="captureCalibrationPair"
                >
                  采集当前棋盘格
                </el-button>
                <el-button
                  type="warning"
                  :loading="calibrating"
                  :disabled="!calibrationSessionId || calibrationPairCount < calibrationForm.min_pairs"
                  @click="runCalibration"
                >
                  执行双目标定
                </el-button>
              </div>
            </el-form>

            <div class="status-panel">
              <div class="status-line">
                <span>会话 ID</span>
                <strong class="path-text">{{ calibrationSessionId || '未开始' }}</strong>
              </div>
              <div class="status-line">
                <span>有效建议</span>
                <strong>建议至少采集 {{ calibrationForm.min_pairs }} 组，并覆盖近/中/远、左/中/右多个角度</strong>
              </div>
            </div>

            <el-alert
              v-if="calibrationResult"
              title="标定已完成并已生成新的立体标定文件。"
              type="success"
              :closable="false"
              show-icon
            />

            <div v-if="calibrationResult" class="runtime-grid">
              <div class="status-line">
                <span>Stereo RMS</span>
                <strong>{{ calibrationResult.stereo_rms }}</strong>
              </div>
              <div class="status-line">
                <span>Baseline</span>
                <strong>{{ calibrationResult.baseline_mm }} mm</strong>
              </div>
              <div class="status-line">
                <span>新标定文件</span>
                <strong class="path-text">{{ calibrationResult.activated_calib_path || calibrationResult.output_calib_path }}</strong>
              </div>
            </div>
          </el-card>

          <el-alert
            v-if="errorMessage"
            :title="errorMessage"
            type="error"
            show-icon
            :closable="true"
            @close="errorMessage = ''"
          />

          <el-card v-if="measuring" shadow="never" class="result-card">
            <template #header>
              <div class="card-header">
                <span>测量进行中</span>
                <el-tag type="warning">{{ measureElapsedSeconds }}s</el-tag>
              </div>
            </template>

            <div class="loading-copy">
              <p>正在执行 YOLO 检测、双目矫正和 MonSter 深度推理。</p>
              <p v-if="runtimeStatus && runtimeStatus.device_type !== 'cuda'">当前是 CPU 路径，等待 30-90 秒是正常现象。</p>
              <p v-else>当前是 GPU 路径，通常会明显更快。</p>
            </div>
            <el-progress :percentage="measureProgressPercent" status="warning" />
          </el-card>

          <el-card v-if="measurementResult" shadow="never" class="result-card">
            <template #header>
              <div class="card-header">
                <span>测量结果</span>
                <el-tag type="warning">
                  有效目标 {{ measurementResult.valid_measurements || 0 }}/{{ measurementResult.total_targets || 0 }}
                </el-tag>
              </div>
            </template>

            <el-alert
              v-if="measurementResult.total_targets === 0"
              title="本次没有检测到水果。请把水果完整放到左相机画面里，并确保目标足够大、清晰、光照稳定，然后重新测量。"
              type="warning"
              :closable="false"
              show-icon
            />

            <div class="result-meta">
              <div class="metric-box">
                <span>平均果径</span>
                <strong>{{ formatDistance(statistics.avg_distance_mm) }}</strong>
              </div>
              <div class="metric-box">
                <span>最小果径</span>
                <strong>{{ formatDistance(statistics.min_distance_mm) }}</strong>
              </div>
              <div class="metric-box">
                <span>最大果径</span>
                <strong>{{ formatDistance(statistics.max_distance_mm) }}</strong>
              </div>
            </div>

            <el-table :data="measurementTargets" stripe border size="small" class="target-table">
              <el-table-column prop="index" label="#" width="60">
                <template #default="scope">
                  {{ scope.row.index !== null && scope.row.index !== undefined ? scope.row.index + 1 : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="label" label="目标" min-width="120" />
              <el-table-column label="置信度" width="110">
                <template #default="scope">
                  {{ scope.row.confidence !== null && scope.row.confidence !== undefined ? scope.row.confidence.toFixed(3) : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="bbox" label="YOLO 框" min-width="180">
                <template #default="scope">
                  {{ formatBbox(scope.row.bbox) }}
                </template>
              </el-table-column>
              <el-table-column label="果径(mm)" width="120">
                <template #default="scope">
                  {{ scope.row.distance_mm !== undefined && scope.row.distance_mm !== null ? scope.row.distance_mm.toFixed(2) : '-' }}
                </template>
              </el-table-column>
              <el-table-column prop="status" label="状态" min-width="180" />
            </el-table>

            <div v-if="resultImageUrl" class="result-image-wrap">
              <img :src="resultImageUrl" alt="measurement visualization" class="result-image" />
            </div>
          </el-card>
        </div>
      </section>
    </div>

    <el-dialog
      v-model="usageDialogVisible"
      title="果径测量使用说明"
      width="720px"
      class="usage-dialog"
      destroy-on-close
    >
      <div class="usage-dialog__body">
        <p>
          这个页面用于用双目相机抓取当前画面，并自动估计水果的横向直径。第一次使用时，按下面的顺序操作即可。
        </p>

        <section class="usage-block">
          <h3>怎么用</h3>
          <ol>
            <li>先把双目摄像头接好，确认左右画面都正常，水果能同时出现在两个镜头里。</li>
            <li>根据你的设备选择输入模式：如果是一台相机输出左右拼接画面，选“单设备双目”；如果是两台相机分别拍摄，选“双设备双目”。</li>
            <li>点击“启动摄像头”，先看实时预览，确认画面清晰、没有明显卡顿，水果没有被裁掉。</li>
            <li>把水果放在镜头前，尽量让水果位于画面中间，避免离镜头太近或太远。</li>
            <li>如果当前设备还没有完成标定，先采集棋盘格并执行双目标定；已经标定过则可直接测量。</li>
            <li>保持水果和相机短暂稳定，然后点击“测量当前帧”。</li>
            <li>等待结果返回后，在“测量结果”区域查看每个水果的果径数值。通常单位是毫米，数值越大表示果径越大。</li>
          </ol>
        </section>

        <section class="usage-block">
          <h3>结果怎么看</h3>
          <ul>
            <li>如果画面里检测到多个水果，系统会分别给出每个目标的测量结果。</li>
            <li>如果提示没有检测到水果，通常是水果没有完整进入画面，或者当前角度、光照不适合识别。</li>
            <li>如果结果波动较大，先检查相机是否晃动、左右画面是否对齐，以及水果边缘是否清晰。</li>
          </ul>
        </section>

        <section class="usage-block">
          <h3>简短原理</h3>
          <p>
            系统会先利用双目图像恢复水果与相机之间的空间深度，再识别出水果在图像中的位置，最后在水果左右边缘之间计算真实空间距离，把这个距离作为果径估计值。
          </p>
          <p>
            可以简单理解为：先看出“水果在哪里、离相机多远”，再把图像里的宽度换算成现实中的宽度。
          </p>
        </section>

        <div class="usage-tip">
          为了更容易测准：尽量使用稳定光照、保持镜头清洁、让水果正对镜头，并优先把水果放在画面中央区域。
        </div>
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import {
  captureCalibrationFrame,
  getCalibrationStatus,
  getCameraStatus,
  getMeasureRuntimeStatus,
  measureCurrentStereoFrame,
  probeCameraIndices,
  runStereoCalibration,
  startStereoCamera,
  stopStereoCamera
} from '@/api/detection'

const BACKEND_ORIGIN = (import.meta.env.VITE_BACKEND_ORIGIN || '').trim()
const DEFAULT_PREVIEW_WS_PATH = '/ws/camera/preview/'
const DEFAULT_PREVIEW_FPS = 8

export default {
  name: 'DiameterMeasurementView',
  data() {
    return {
      statusLoading: false,
      runtimeLoading: false,
      starting: false,
      measuring: false,
      probing: false,
      capturingCalibration: false,
      calibrating: false,
      detectPreview: true,
      previewSocket: null,
      previewWsPath: DEFAULT_PREVIEW_WS_PATH,
      previewUrl: '',
      previewConnected: false,
      previewStatus: null,
      previewError: '',
      previewManualClose: false,
      previewReconnectTimer: null,
      usageDialogVisible: false,
      errorMessage: '',
      measurementResult: null,
      resultImageUrl: '',
      runtimeStatus: null,
      probeResults: [],
      pairProbeResults: [],
      recommendedPair: null,
      calibrationSessionId: '',
      calibrationPairCount: 0,
      calibrationResult: null,
      measureElapsedSeconds: 0,
      measureTimer: null,
      cameraStatus: {
        active: false,
        config: {},
        last_open_error: null,
        last_frame_ts: null,
        consecutive_failures: 0
      },
      form: {
        source_mode: 'dual',
        camera_index: 0,
        left_camera_index: 0,
        right_camera_index: 1,
        split_mode: 'left_right',
        frame_width: null,
        frame_height: null,
        fps: null,
        conf: 0.25,
        save_vis: true
      },
      calibrationForm: {
        cols: 9,
        rows: 6,
        square_mm: 25.0,
        min_pairs: 8,
        activate: true
      }
    }
  },
  computed: {
    lastFrameTime() {
      if (!this.cameraStatus.last_frame_ts) {
        return '暂无'
      }
      return new Date(this.cameraStatus.last_frame_ts * 1000).toLocaleString()
    },
    configSummary() {
      const config = this.cameraStatus.config || {}
      const mode = config.source_mode || this.form.source_mode
      if (mode === 'dual') {
        return `dual | left=${config.left_camera_index ?? this.form.left_camera_index}, right=${config.right_camera_index ?? this.form.right_camera_index}, split=${config.split_mode ?? this.form.split_mode}`
      }
      return `single | camera=${config.camera_index ?? this.form.camera_index}, split=${config.split_mode ?? this.form.split_mode}`
    },
    statistics() {
      return this.measurementResult?.statistics || {}
    },
    measurementTargets() {
      return this.measurementResult?.targets || []
    },
    recommendedPairText() {
      if (!Array.isArray(this.recommendedPair) || this.recommendedPair.length !== 2) {
        return '未找到'
      }
      return `${this.recommendedPair[0]} / ${this.recommendedPair[1]}`
    },
    runtimeDeviceLabel() {
      if (!this.runtimeStatus) {
        return '未知'
      }
      return this.runtimeStatus.device_type === 'cuda' ? 'GPU' : 'CPU'
    },
    runtimeTagType() {
      return this.runtimeStatus?.device_type === 'cuda' ? 'success' : 'warning'
    },
    measureProgressPercent() {
      return Math.min(95, Math.max(10, this.measureElapsedSeconds * 2))
    }
  },
  watch: {
    'form.conf'() {
      this.refreshPreview()
    }
  },
  mounted() {
    this.loadStatus()
    this.loadRuntimeStatus()
    this.loadCalibrationStatus()
  },
  beforeUnmount() {
    this.stopMeasureTimer()
    this.closePreviewSocket({ manual: true, clearImage: true })
  },
  methods: {
    toPayload() {
      const payload = {
        source_mode: this.form.source_mode,
        camera_index: this.form.camera_index,
        left_camera_index: this.form.left_camera_index,
        right_camera_index: this.form.right_camera_index,
        split_mode: this.form.split_mode
      }
      for (const key of ['frame_width', 'frame_height', 'fps']) {
        if (this.form[key]) {
          payload[key] = this.form[key]
        }
      }
      return payload
    },
    getPreviewStreamFps() {
      return DEFAULT_PREVIEW_FPS
    },
    buildPreviewSocketUrl(path = this.previewWsPath || DEFAULT_PREVIEW_WS_PATH) {
      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
      const normalizedPath = path.startsWith('/') ? path : `/${path}`
      return `${protocol}//${window.location.host}${normalizedPath}`
    },
    connectPreviewSocket(path = this.previewWsPath || DEFAULT_PREVIEW_WS_PATH) {
      if (this.previewSocket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(this.previewSocket.readyState)) {
        return
      }

      if (this.previewReconnectTimer) {
        window.clearTimeout(this.previewReconnectTimer)
        this.previewReconnectTimer = null
      }

      this.previewWsPath = path || DEFAULT_PREVIEW_WS_PATH
      this.previewManualClose = false
      this.previewError = ''

      const socket = new WebSocket(this.buildPreviewSocketUrl(this.previewWsPath))
      socket.binaryType = 'arraybuffer'

      socket.onopen = () => {
        this.previewConnected = true
        this.previewError = ''
        this.sendPreviewMessage({
          type: 'preview.subscribe',
          detect: this.detectPreview,
          conf: Number(this.form.conf || 0.25),
          fps: this.getPreviewStreamFps()
        })
      }

      socket.onmessage = async (event) => {
        if (typeof event.data === 'string') {
          this.handlePreviewControlMessage(event.data)
          return
        }
        if (event.data instanceof ArrayBuffer) {
          this.updatePreviewFrame(event.data)
          return
        }
        if (event.data instanceof Blob) {
          this.updatePreviewFrame(await event.data.arrayBuffer())
        }
      }

      socket.onerror = () => {
        this.previewError = '双目预览 WebSocket 连接异常。'
      }

      socket.onclose = () => {
        this.previewConnected = false
        this.previewSocket = null
        if (!this.cameraStatus.active) {
          this.clearPreviewFrame()
          return
        }
        if (this.previewManualClose) {
          return
        }
        this.previewError = '双目预览连接已断开，正在尝试重连。'
        this.clearPreviewFrame()
        this.schedulePreviewReconnect()
      }

      this.previewSocket = socket
    },
    closePreviewSocket({ manual = true, clearImage = false } = {}) {
      if (this.previewReconnectTimer) {
        window.clearTimeout(this.previewReconnectTimer)
        this.previewReconnectTimer = null
      }

      this.previewManualClose = manual
      const socket = this.previewSocket
      this.previewSocket = null
      this.previewConnected = false

      if (socket) {
        if (manual && socket.readyState === WebSocket.OPEN) {
          try {
            socket.send(JSON.stringify({ type: 'preview.unsubscribe' }))
          } catch (error) {
            console.warn('preview unsubscribe failed', error)
          }
        }
        if ([WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) {
          socket.close()
        }
      }

      if (clearImage) {
        this.clearPreviewFrame()
      }
    },
    schedulePreviewReconnect() {
      if (this.previewReconnectTimer || !this.cameraStatus.active) {
        return
      }
      this.previewReconnectTimer = window.setTimeout(() => {
        this.previewReconnectTimer = null
        this.connectPreviewSocket()
      }, 1500)
    },
    sendPreviewMessage(payload) {
      if (!this.previewSocket || this.previewSocket.readyState !== WebSocket.OPEN) {
        return
      }
      this.previewSocket.send(JSON.stringify(payload))
    },
    handlePreviewControlMessage(rawMessage) {
      try {
        const payload = JSON.parse(rawMessage)
        if (payload.type === 'preview.ready') {
          this.previewStatus = payload
          this.cameraStatus.active = !!payload.camera_active
          this.cameraStatus.config = payload.config || this.cameraStatus.config
          return
        }
        if (payload.type === 'preview.status') {
          this.previewStatus = payload
          this.cameraStatus.active = !!payload.camera_active
          this.cameraStatus.last_frame_ts = payload.last_frame_ts || null
          this.cameraStatus.consecutive_failures = payload.consecutive_failures || 0
          if (!payload.camera_active) {
            this.clearPreviewFrame()
          }
          return
        }
        if (payload.type === 'preview.error') {
          this.previewError = payload.message || '双目预览推流失败。'
          this.cameraStatus.last_open_error = payload.message || null
          if (['camera_not_active', 'camera_stopped'].includes(payload.code)) {
            this.cameraStatus.active = false
            this.clearPreviewFrame()
          }
        }
      } catch (error) {
        console.warn('preview message parse failed', error)
      }
    },
    updatePreviewFrame(buffer) {
      const blob = new Blob([buffer], { type: 'image/jpeg' })
      const nextUrl = URL.createObjectURL(blob)
      if (this.previewUrl) {
        URL.revokeObjectURL(this.previewUrl)
      }
      this.previewUrl = nextUrl
      this.previewError = ''
    },
    clearPreviewFrame() {
      if (this.previewUrl) {
        URL.revokeObjectURL(this.previewUrl)
      }
      this.previewUrl = ''
    },
    refreshPreview() {
      if (!this.cameraStatus.active || !this.previewSocket || this.previewSocket.readyState !== WebSocket.OPEN) {
        return
      }
      this.previewError = ''
      this.sendPreviewMessage({
        type: 'preview.update',
        detect: this.detectPreview,
        conf: Number(this.form.conf || 0.25),
        fps: this.getPreviewStreamFps()
      })
    },
    async loadStatus() {
      this.statusLoading = true
      try {
        const data = await getCameraStatus()
        this.applyStatus(data, { connectPreview: false })
      } catch (error) {
        this.errorMessage = this.extractError(error, '读取摄像头状态失败')
      } finally {
        this.statusLoading = false
      }
    },
    async loadRuntimeStatus() {
      this.runtimeLoading = true
      try {
        this.runtimeStatus = await getMeasureRuntimeStatus()
      } catch (error) {
        this.errorMessage = this.extractError(error, '读取 MonSter 运行时状态失败')
      } finally {
        this.runtimeLoading = false
      }
    },
    async loadCalibrationStatus(sessionId = this.calibrationSessionId) {
      try {
        const data = await getCalibrationStatus(sessionId)
        this.calibrationSessionId = data.session_id || this.calibrationSessionId
        this.calibrationPairCount = data.pair_count || 0
        this.calibrationResult = data.result || null
      } catch (error) {
        this.errorMessage = this.extractError(error, '读取标定状态失败')
      }
    },
    async probeCameras() {
      this.probing = true
      this.errorMessage = ''
      try {
        const data = await probeCameraIndices(4)
        this.probeResults = data.results || []
        this.pairProbeResults = data.pair_results || []
        this.recommendedPair = data.recommended_dual_pair || null
        if (Array.isArray(this.recommendedPair) && this.recommendedPair.length === 2) {
          this.form.source_mode = 'dual'
          this.form.left_camera_index = this.recommendedPair[0]
          this.form.right_camera_index = this.recommendedPair[1]
          ElMessage.success(`推荐双摄组合 ${this.recommendedPair[0]} / ${this.recommendedPair[1]}`)
        } else {
          ElMessage.warning('没有检测到可同时打开的双摄组合')
        }
      } catch (error) {
        this.errorMessage = this.extractError(error, '扫描摄像头索引失败')
      } finally {
        this.probing = false
      }
    },
    applyStatus(data, { connectPreview = false } = {}) {
      this.previewWsPath = data.preview_ws_path || this.previewWsPath || DEFAULT_PREVIEW_WS_PATH
      this.cameraStatus = {
        active: !!data.active,
        config: data.config || {},
        last_open_error: data.last_open_error || null,
        last_frame_ts: data.last_frame_ts || null,
        consecutive_failures: data.consecutive_failures || 0
      }

      if (!this.cameraStatus.active) {
        this.previewError = ''
        this.closePreviewSocket({ manual: true, clearImage: true })
        return
      }

      if (connectPreview) {
        this.connectPreviewSocket(this.previewWsPath)
      }
    },
    async startCamera() {
      this.starting = true
      this.errorMessage = ''
      try {
        const data = await startStereoCamera(this.toPayload())
        this.applyStatus(data, { connectPreview: true })
        ElMessage.success('摄像头已启动')
      } catch (error) {
        this.errorMessage = this.extractError(error, '启动摄像头失败')
      } finally {
        this.starting = false
      }
    },
    async stopCamera() {
      this.errorMessage = ''
      this.closePreviewSocket({ manual: true, clearImage: true })
      try {
        await stopStereoCamera()
        this.cameraStatus = {
          active: false,
          config: {},
          last_open_error: null,
          last_frame_ts: null,
          consecutive_failures: 0
        }
        this.previewError = ''
        ElMessage.success('摄像头已停止')
      } catch (error) {
        this.errorMessage = this.extractError(error, '停止摄像头失败')
        if (this.cameraStatus.active) {
          this.connectPreviewSocket(this.previewWsPath)
        }
      }
    },
    startMeasureTimer() {
      this.stopMeasureTimer()
      this.measureElapsedSeconds = 0
      this.measureTimer = window.setInterval(() => {
        this.measureElapsedSeconds += 1
      }, 1000)
    },
    stopMeasureTimer() {
      if (this.measureTimer) {
        window.clearInterval(this.measureTimer)
        this.measureTimer = null
      }
    },
    async measureCurrentFrame() {
      this.measuring = true
      this.errorMessage = ''
      this.startMeasureTimer()
      try {
        const data = await measureCurrentStereoFrame({
          conf: this.form.conf,
          save_vis: this.form.save_vis
        })
        this.measurementResult = data
        this.resultImageUrl = this.resolveMediaUrl(
          data.visualization_url || data.measurement?.annotated_image_url || ''
        )
        if ((data.total_targets || 0) === 0) {
          ElMessage.warning('本次未检测到水果，请调整水果位置后重试')
        } else {
          ElMessage.success('当前帧测量完成')
        }
      } catch (error) {
        this.errorMessage = this.extractError(error, '当前帧测量失败')
      } finally {
        this.measuring = false
        this.stopMeasureTimer()
      }
    },
    async captureCalibrationPair() {
      this.capturingCalibration = true
      this.errorMessage = ''
      try {
        const data = await captureCalibrationFrame({
          session_id: this.calibrationSessionId || undefined
        })
        this.calibrationSessionId = data.session_id
        this.calibrationPairCount = data.pair_count || 0
        ElMessage.success(`已采集第 ${data.captured_index} 组标定图`)
      } catch (error) {
        this.errorMessage = this.extractError(error, '采集标定图失败')
      } finally {
        this.capturingCalibration = false
      }
    },
    async runCalibration() {
      this.calibrating = true
      this.errorMessage = ''
      try {
        const data = await runStereoCalibration({
          session_id: this.calibrationSessionId,
          cols: this.calibrationForm.cols,
          rows: this.calibrationForm.rows,
          square_mm: this.calibrationForm.square_mm,
          min_pairs: this.calibrationForm.min_pairs,
          activate: this.calibrationForm.activate
        })
        this.calibrationResult = data
        this.runtimeStatus = data.runtime_status || this.runtimeStatus
        ElMessage.success('双目标定完成，已更新当前测量标定文件')
      } catch (error) {
        this.errorMessage = this.extractError(error, '执行双目标定失败')
      } finally {
        this.calibrating = false
      }
    },
    resolveMediaUrl(url) {
      if (!url) {
        return ''
      }
      const base = BACKEND_ORIGIN || window.location.origin
      const absoluteUrl = /^https?:\/\//i.test(url) ? url : `${base}${url}`
      return `${absoluteUrl}${absoluteUrl.includes('?') ? '&' : '?'}_ts=${Date.now()}`
    },
    handlePreviewError() {
      this.previewError = '双目预览图像渲染失败，请检查 WebSocket 预览连接。'
    },
    formatDistance(value) {
      if (value === null || value === undefined) {
        return '-'
      }
      return `${Number(value).toFixed(2)} mm`
    },
    formatBbox(bbox) {
      if (!Array.isArray(bbox) || bbox.length !== 4) {
        return '-'
      }
      return `[${bbox.join(', ')}]`
    },
    extractError(error, fallback) {
      return error?.response?.data?.error || error?.message || fallback
    }
  }
}
</script>

<style scoped>
.diameter-page {
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(15, 118, 110, 0.16), transparent 28%),
    linear-gradient(180deg, #f7faf8 0%, #eef5f1 100%);
  min-height: 100%;
}

.page-shell {
  max-width: 1440px;
  margin: 0 auto;
  display: grid;
  gap: 20px;
}

.hero {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  align-items: flex-start;
  padding: 28px 32px;
  border-radius: 24px;
  background: linear-gradient(135deg, #173b32 0%, #245446 55%, #3d7a67 100%);
  color: #f4fbf8;
  box-shadow: 0 20px 40px rgba(23, 59, 50, 0.18);
}

.eyebrow {
  margin: 0 0 10px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(244, 251, 248, 0.72);
}

.hero h1 {
  margin: 0;
  font-size: 34px;
  line-height: 1.15;
}

.hero-text {
  margin: 12px 0 0;
  max-width: 720px;
  color: rgba(244, 251, 248, 0.84);
  line-height: 1.7;
}

.hero-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.layout-grid {
  display: grid;
  grid-template-columns: 380px minmax(0, 1fr);
  gap: 20px;
  align-items: start;
}

.left-column,
.right-column {
  display: grid;
  gap: 20px;
}

.control-card,
.preview-card,
.result-card {
  border: none;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.92);
  box-shadow: 0 18px 40px rgba(43, 66, 59, 0.08);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  font-weight: 700;
}

.camera-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.inline-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.switch-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  margin-bottom: 12px;
  border-radius: 16px;
  background: #f6fbf8;
  color: #21443a;
}

.button-group {
  display: grid;
  gap: 12px;
  margin-top: 8px;
}

.button-group .el-button {
  width: 100%;
}

.status-panel,
.runtime-grid,
.probe-panel {
  display: grid;
  gap: 10px;
  margin-top: 16px;
  padding: 16px;
  border-radius: 18px;
  background: #f7faf8;
}

.probe-panel {
  background: #fff8eb;
}

.status-line {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 13px;
  color: #4e635b;
}

.status-line strong {
  text-align: right;
  color: #1d2b25;
}

.path-text {
  word-break: break-all;
}

.probe-item {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  align-items: center;
  padding: 10px 12px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.72);
  color: #7c5a13;
}

.probe-item.success {
  background: #eef9f3;
  color: #18533a;
}

.probe-item div {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.pair-list {
  display: grid;
  gap: 10px;
}

.pair-title {
  font-weight: 700;
  color: #5f4710;
}

.preview-stage {
  min-height: 460px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 20px;
  overflow: hidden;
  background: linear-gradient(135deg, #0f172a 0%, #18283c 100%);
  border: 1px solid rgba(148, 163, 184, 0.2);
}

.preview-image,
.result-image {
  display: block;
  width: 100%;
  height: auto;
}

.preview-placeholder,
.empty-hint {
  max-width: 360px;
  text-align: center;
  line-height: 1.8;
  color: rgba(226, 232, 240, 0.8);
}

.preview-error {
  margin-top: 12px;
  color: #b42318;
  line-height: 1.7;
}

.empty-hint {
  color: #4e635b;
}

.loading-copy {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
  color: #35594d;
  line-height: 1.7;
}

.result-meta {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 12px;
  margin: 18px 0;
}

.metric-box {
  padding: 16px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbfa 0%, #eef5f1 100%);
  border: 1px solid rgba(36, 84, 70, 0.08);
}

.metric-box span {
  display: block;
  font-size: 13px;
  color: #5b746a;
  margin-bottom: 8px;
}

.metric-box strong {
  font-size: 24px;
  color: #183028;
}

.target-table {
  margin-top: 16px;
}

.result-image-wrap {
  margin-top: 18px;
  border-radius: 20px;
  overflow: hidden;
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.usage-dialog__body {
  color: #26453b;
  line-height: 1.8;
}

.usage-dialog__body p {
  margin: 0 0 14px;
}

.usage-block {
  margin-top: 16px;
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbfa 0%, #eef5f1 100%);
  border: 1px solid rgba(36, 84, 70, 0.08);
}

.usage-block h3 {
  margin: 0 0 10px;
  font-size: 16px;
  color: #173b32;
}

.usage-block ol,
.usage-block ul {
  margin: 0;
  padding-left: 22px;
}

.usage-block li {
  margin-bottom: 8px;
}

.usage-tip {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.18);
  color: #7c4a03;
}

@media (max-width: 1180px) {
  .layout-grid {
    grid-template-columns: 1fr;
  }

  .hero {
    flex-direction: column;
  }
}

@media (max-width: 768px) {
  .diameter-page {
    padding: 12px;
  }

  .hero {
    padding: 22px 20px;
  }

  .hero h1 {
    font-size: 28px;
  }

  .inline-grid,
  .result-meta {
    grid-template-columns: 1fr;
  }

  .preview-stage {
    min-height: 280px;
  }
}
</style>

