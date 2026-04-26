<template>
  <div class="diameter-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Fruit Diameter Workspace</p>
          <h1>果径测量</h1>
          <p class="hero-text">
            普通用户按这个顺序操作即可：先扫描并选择相机，点击“启动画面”，确认水果完整出现在预览里，再点击“立即测量”。
            第一次使用或更换相机时，再做一次“相机校准”。
          </p>
        </div>

        <div class="hero-actions">
          <div class="primary-actions">
            <el-button type="primary" size="large" :loading="starting" @click="startCamera">启动画面</el-button>
            <el-button
              type="success"
              size="large"
              :loading="measuring"
              :disabled="!cameraStatus.active"
              @click="measureCurrentFrame"
            >
              立即测量
            </el-button>
            <el-button size="large" :disabled="!cameraStatus.active" @click="stopCamera">停止画面</el-button>
          </div>

          <div class="secondary-actions">
            <el-button plain type="warning" :loading="probing" @click="probeCameras">扫描相机</el-button>
            <el-button plain :loading="statusLoading" @click="loadStatus">刷新状态</el-button>
            <el-button plain type="info" :loading="runtimeLoading" @click="loadRuntimeStatus">刷新引擎</el-button>
            <el-button plain @click="usageDialogVisible = true">查看说明</el-button>
          </div>

          <div class="hero-badges">
            <span class="hero-badge">{{ cameraStatus.active ? '画面已启动' : '画面未启动' }}</span>
            <span class="hero-badge">{{ runtimeModeCopy }}</span>
            <span class="hero-badge">{{ calibrationReady ? '已具备校准条件' : '首次使用建议先校准' }}</span>
          </div>
        </div>
      </section>

      <section class="guide-strip">
        <article class="guide-step">
          <span class="guide-index">1</span>
          <div>
            <h3>先选相机</h3>
            <p>点击“扫描相机”后，从设备名称里直接选择左相机和右相机，不再手动记索引。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">2</span>
          <div>
            <h3>再看画面</h3>
            <p>启动画面后，确认左右相机都正常，水果完整出现在中间区域。</p>
          </div>
        </article>
        <article class="guide-step">
          <span class="guide-index">3</span>
          <div>
            <h3>最后测量</h3>
            <p>保持水果和相机短暂稳定，点击“立即测量”，结果会直接显示在下方。</p>
          </div>
        </article>
      </section>

      <section class="overview-grid">
        <article class="overview-card">
          <span class="overview-label">画面状态</span>
          <strong class="overview-value">{{ cameraStatus.active ? '已启动' : '待启动' }}</strong>
          <p class="overview-meta">最近取帧：{{ lastFrameTime }}</p>
          <div class="overview-actions">
            <el-button link type="primary" @click="loadStatus">刷新</el-button>
            <el-button link type="danger" :disabled="!cameraStatus.active" @click="stopCamera">停止</el-button>
          </div>
        </article>

        <article class="overview-card">
          <span class="overview-label">当前相机组合</span>
          <strong class="overview-value">{{ cameraIndexText }}</strong>
          <p class="overview-meta">{{ selectedCameraSummary }}</p>
          <div class="overview-actions">
            <el-button link type="warning" :loading="probing" @click="probeCameras">重新扫描</el-button>
            <el-button link :disabled="!hasRecommendedPair" @click="useRecommendedPair">使用推荐</el-button>
          </div>
        </article>

        <article class="overview-card">
          <span class="overview-label">测量引擎</span>
          <strong class="overview-value">{{ runtimeModeCopy }}</strong>
          <p class="overview-meta">{{ runtimeSummaryText }}</p>
          <div class="overview-actions">
            <el-button link type="info" :loading="runtimeLoading" @click="loadRuntimeStatus">刷新引擎</el-button>
          </div>
        </article>

        <article class="overview-card">
          <span class="overview-label">相机校准</span>
          <strong class="overview-value">{{ calibrationReady ? '可直接测量' : '建议先校准' }}</strong>
          <p class="overview-meta">已采集 {{ calibrationPairCount }} / {{ calibrationForm.min_pairs }} 组</p>
          <div class="overview-actions">
            <el-button link @click="loadCalibrationStatus">刷新</el-button>
            <el-button link type="primary" @click="scrollToCalibration">去校准</el-button>
          </div>
        </article>
      </section>

      <el-alert
        v-if="runtimeStatus && runtimeStatus.device_type !== 'cuda'"
        title="当前测量引擎运行在 CPU，上一次测量等待时间偏长是正常现象。如果后续需要更快速度，再考虑切换到 GPU 环境。"
        type="warning"
        :closable="false"
        show-icon
      />

      <el-alert
        v-if="errorMessage"
        :title="errorMessage"
        type="error"
        show-icon
        :closable="true"
        @close="errorMessage = ''"
      />

      <section class="workspace-grid">
        <div class="workspace-main">
          <el-card shadow="never" class="preview-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span>实时画面</span>
                  <p class="card-subtitle">这里会显示左右相机拼接后的预览画面。</p>
                </div>
                <el-tag :type="previewUrl ? 'success' : 'info'">
                  {{ previewUrl ? '已连接' : '等待启动' }}
                </el-tag>
              </div>
            </template>

            <div class="preview-toolbar">
              <div class="toggle-pill">
                <span>预览中显示识别框</span>
                <el-switch v-model="detectPreview" @change="refreshPreview" />
              </div>
              <div class="preview-toolbar__actions">
                <el-button plain :loading="statusLoading" @click="loadStatus">刷新画面状态</el-button>
                <el-button plain type="primary" :disabled="!cameraStatus.active" @click="measureCurrentFrame">
                  用当前画面测量
                </el-button>
              </div>
            </div>

            <div class="preview-stage">
              <img
                v-if="previewUrl"
                :src="previewUrl"
                alt="stereo preview"
                class="preview-image"
                @error="handlePreviewError"
              />
              <div v-else class="preview-placeholder">
                <h3>等待画面接入</h3>
                <p>点击顶部“启动画面”后，这里会显示测量预览。</p>
              </div>
            </div>

            <p v-if="previewError" class="preview-error">{{ previewError }}</p>
          </el-card>

          <el-card v-if="measuring" shadow="never" class="result-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span>正在测量</span>
                  <p class="card-subtitle">系统正在识别水果并计算果径。</p>
                </div>
                <el-tag type="warning">{{ measureElapsedSeconds }}s</el-tag>
              </div>
            </template>

            <div class="loading-copy">
              <p>请保持相机与水果稳定，等待本次测量完成。</p>
              <p>{{ runtimeStatus && runtimeStatus.device_type !== 'cuda' ? '当前为 CPU 模式，等待时间可能更长。' : '当前为 GPU 模式，速度通常更快。' }}</p>
            </div>
            <el-progress :percentage="measureProgressPercent" status="warning" />
          </el-card>

          <el-card shadow="never" class="result-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span>测量结果</span>
                  <p class="card-subtitle">每个识别到的水果都会显示对应果径。</p>
                </div>
                <el-tag v-if="measurementResult" type="warning">
                  有效 {{ measurementResult.valid_measurements || 0 }} / {{ measurementResult.total_targets || 0 }}
                </el-tag>
                <el-tag v-else type="info">等待测量</el-tag>
              </div>
            </template>

            <template v-if="measurementResult">
              <el-alert
                v-if="measurementResult.total_targets === 0"
                title="这次没有检测到水果。请让水果完整进入画面，尽量放在中间区域并保持清晰。"
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
                <el-table-column prop="label" label="水果" min-width="120" />
                <el-table-column label="识别置信度" width="120">
                  <template #default="scope">
                    {{ scope.row.confidence !== null && scope.row.confidence !== undefined ? scope.row.confidence.toFixed(3) : '-' }}
                  </template>
                </el-table-column>
                <el-table-column prop="bbox" label="识别区域" min-width="180">
                  <template #default="scope">
                    {{ formatBbox(scope.row.bbox) }}
                  </template>
                </el-table-column>
                <el-table-column label="果径(mm)" width="120">
                  <template #default="scope">
                    {{ scope.row.distance_mm !== undefined && scope.row.distance_mm !== null ? scope.row.distance_mm.toFixed(2) : '-' }}
                  </template>
                </el-table-column>
                <el-table-column prop="status" label="说明" min-width="180" />
              </el-table>

              <div v-if="resultImageUrl" class="result-image-wrap">
                <img :src="resultImageUrl" alt="measurement visualization" class="result-image" />
              </div>
            </template>

            <div v-else class="empty-state">
              <h3>结果会显示在这里</h3>
              <p>启动画面并点击“立即测量”后，系统会展示果径统计和每个水果的详细结果。</p>
            </div>
          </el-card>
        </div>

        <div class="workspace-side">
          <el-card shadow="never" class="control-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span>相机与测量设置</span>
                  <p class="card-subtitle">先扫描相机，再直接从设备名称中选择当前使用的相机组合。</p>
                </div>
                <el-button plain size="small" @click="configEditing = !configEditing">
                  {{ configEditing ? '收起高级设置' : '展开高级设置' }}
                </el-button>
              </div>
            </template>

            <div class="camera-picker-card">
              <div class="picker-toolbar">
                <el-button plain type="warning" :loading="probing" @click="probeCameras">扫描相机</el-button>
                <span class="picker-hint">扫描后可直接按设备名称选择左/右相机</span>
              </div>

              <el-form label-position="top" class="camera-form">
                <el-form-item label="相机连接方式">
                  <el-segmented
                    v-model="form.source_mode"
                    :options="sourceModeOptions"
                    block
                  />
                </el-form-item>

                <template v-if="cameraOptions.length">
                  <el-form-item v-if="form.source_mode === 'single'" label="当前相机">
                    <el-select v-model="form.camera_index" placeholder="请选择相机" filterable>
                      <el-option
                        v-for="item in cameraOptions"
                        :key="`single-${item.camera_index}`"
                        :label="item.optionLabel"
                        :value="item.camera_index"
                      />
                    </el-select>
                  </el-form-item>

                  <div v-else class="inline-grid">
                    <el-form-item label="左相机">
                      <el-select v-model="form.left_camera_index" placeholder="请选择左相机" filterable>
                        <el-option
                          v-for="item in cameraOptions"
                          :key="`left-${item.camera_index}`"
                          :label="item.optionLabel"
                          :value="item.camera_index"
                        />
                      </el-select>
                    </el-form-item>
                    <el-form-item label="右相机">
                      <el-select v-model="form.right_camera_index" placeholder="请选择右相机" filterable>
                        <el-option
                          v-for="item in cameraOptions"
                          :key="`right-${item.camera_index}`"
                          :label="item.optionLabel"
                          :value="item.camera_index"
                        />
                      </el-select>
                    </el-form-item>
                  </div>
                </template>

                <div v-else class="empty-inline-tip">
                  还没有扫描结果。点击上方“扫描相机”后，这里会列出可用设备名称。
                </div>
              </el-form>
            </div>

            <div class="summary-list">
              <div v-for="item in configSummaryItems" :key="item.label" class="summary-row">
                <span>{{ item.label }}</span>
                <strong>{{ item.value }}</strong>
              </div>
            </div>

            <div class="inline-actions">
              <el-button :disabled="!hasRecommendedPair" @click="useRecommendedPair">使用推荐相机组合</el-button>
              <el-button plain type="primary" @click="startCamera">按当前配置启动</el-button>
            </div>

            <div v-if="configEditing" class="edit-panel">
              <el-form label-position="top" class="camera-form">
                <el-form-item label="拼接方式">
                  <el-select v-model="form.split_mode">
                    <el-option label="左右拼接" value="left_right" />
                    <el-option label="上下拼接" value="top_bottom" />
                  </el-select>
                </el-form-item>

                <div class="inline-grid">
                  <el-form-item label="画面宽度">
                    <el-input-number v-model="form.frame_width" :min="1" :step="1" />
                  </el-form-item>
                  <el-form-item label="画面高度">
                    <el-input-number v-model="form.frame_height" :min="1" :step="1" />
                  </el-form-item>
                </div>

                <div class="inline-grid">
                  <el-form-item label="采集帧率">
                    <el-input-number v-model="form.fps" :min="1" :max="120" :step="1" />
                  </el-form-item>
                  <el-form-item label="识别灵敏度">
                    <el-input-number
                      v-model="form.conf"
                      :min="0.01"
                      :max="1"
                      :step="0.01"
                      :precision="2"
                    />
                  </el-form-item>
                </div>

                <div class="toggle-list">
                  <div class="toggle-pill">
                    <span>预览中显示识别框</span>
                    <el-switch v-model="detectPreview" @change="refreshPreview" />
                  </div>
                  <div class="toggle-pill">
                    <span>测量后保存结果图</span>
                    <el-switch v-model="form.save_vis" />
                  </div>
                </div>
              </el-form>
            </div>
          </el-card>

          <el-card id="calibration-card" shadow="never" class="control-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span>相机校准</span>
                  <p class="card-subtitle">只在第一次使用、换相机或测量误差明显变大时需要。</p>
                </div>
                <el-button plain size="small" @click="calibrationEditing = !calibrationEditing">
                  {{ calibrationEditing ? '收起参数' : '修改校准参数' }}
                </el-button>
              </div>
            </template>

            <div class="summary-list">
              <div v-for="item in calibrationSummaryItems" :key="item.label" class="summary-row">
                <span>{{ item.label }}</span>
                <strong :class="{ 'path-text': item.isPath }">{{ item.value }}</strong>
              </div>
            </div>

            <div class="calibration-note">
              建议拍摄近、中、远不同距离的棋盘格，并让棋盘格尽量覆盖左、中、右多个位置。
            </div>

            <div class="button-group">
              <el-button
                type="primary"
                :loading="capturingCalibration"
                :disabled="!cameraStatus.active"
                @click="captureCalibrationPair"
              >
                采集一组校准图片
              </el-button>
              <el-button
                type="warning"
                :loading="calibrating"
                :disabled="!calibrationSessionId || calibrationPairCount < calibrationForm.min_pairs"
                @click="runCalibration"
              >
                开始校准并应用
              </el-button>
            </div>

            <div v-if="calibrationEditing" class="edit-panel">
              <el-form label-position="top" class="camera-form">
                <div class="inline-grid">
                  <el-form-item label="棋盘格列数">
                    <el-input-number v-model="calibrationForm.cols" :min="3" :max="32" />
                  </el-form-item>
                  <el-form-item label="棋盘格行数">
                    <el-input-number v-model="calibrationForm.rows" :min="3" :max="32" />
                  </el-form-item>
                </div>

                <div class="inline-grid">
                  <el-form-item label="方格边长(mm)">
                    <el-input-number
                      v-model="calibrationForm.square_mm"
                      :min="0.1"
                      :step="0.1"
                      :precision="1"
                    />
                  </el-form-item>
                  <el-form-item label="最少采集组数">
                    <el-input-number v-model="calibrationForm.min_pairs" :min="4" :max="64" />
                  </el-form-item>
                </div>

                <div class="toggle-pill">
                  <span>校准成功后立即应用到测量服务</span>
                  <el-switch v-model="calibrationForm.activate" />
                </div>
              </el-form>
            </div>

            <div v-if="calibrationResult" class="success-panel">
              <el-alert
                title="校准已完成，新的标定文件已经可以用于后续测量。"
                type="success"
                :closable="false"
                show-icon
              />
              <div class="summary-list compact">
                <div class="summary-row">
                  <span>校准误差 RMS</span>
                  <strong>{{ calibrationResult.stereo_rms }}</strong>
                </div>
                <div class="summary-row">
                  <span>双相机基线</span>
                  <strong>{{ calibrationResult.baseline_mm }} mm</strong>
                </div>
              </div>
            </div>
          </el-card>

          <el-card shadow="never" class="control-card">
            <template #header>
              <div class="card-header">
                <div>
                  <span>更多设备信息</span>
                  <p class="card-subtitle">技术细节和扫描结果统一收在这里，避免主界面过长。</p>
                </div>
              </div>
            </template>

            <el-collapse v-model="openInfoPanels" class="info-collapse">
              <el-collapse-item name="runtime" title="测量引擎详情">
                <div class="summary-list compact">
                  <div v-for="item in runtimeDetailItems" :key="item.label" class="summary-row">
                    <span>{{ item.label }}</span>
                    <strong :class="{ 'path-text': item.isPath }">{{ item.value }}</strong>
                  </div>
                </div>
              </el-collapse-item>

              <el-collapse-item name="probe" title="相机扫描结果">
                <div class="probe-section">
                  <div class="summary-list compact">
                    <div class="summary-row">
                      <span>推荐组合</span>
                      <strong>{{ recommendedPairText }}</strong>
                    </div>
                  </div>

                  <div v-if="probeResults.length" class="probe-list">
                    <div
                      v-for="item in probeResults"
                      :key="item.camera_index"
                      class="probe-item"
                      :class="{ success: item.opened }"
                    >
                      <div>
                        <strong>{{ item.device_name || `相机 ${item.camera_index}` }}</strong>
                        <span>索引 {{ item.camera_index }} | {{ item.opened ? '可打开' : '不可打开' }}</span>
                      </div>
                      <small v-if="item.opened">
                        {{ item.frame_width || '-' }} x {{ item.frame_height || '-' }}
                        <span v-if="item.fps"> | {{ item.fps }} fps</span>
                      </small>
                    </div>
                  </div>

                  <div v-else class="empty-state compact-empty">
                    <p>还没有扫描结果。点击顶部或配置卡片中的“扫描相机”即可查看。</p>
                  </div>

                  <div v-if="pairProbeResults.length" class="probe-list">
                    <div
                      v-for="pair in pairProbeResults"
                      :key="`${pair.left_camera_index}-${pair.right_camera_index}`"
                      class="probe-item"
                      :class="{ success: pair.simultaneous_ok }"
                    >
                      <div>
                        <strong>{{ formatPairLabel(pair.left_camera_index, pair.right_camera_index) }}</strong>
                        <span>{{ pair.simultaneous_ok ? '可同时打开' : '不可同时打开' }}</span>
                      </div>
                      <small>L={{ pair.left_read_ok ? 'ok' : 'fail' }} | R={{ pair.right_read_ok ? 'ok' : 'fail' }}</small>
                    </div>
                  </div>
                </div>
              </el-collapse-item>

              <el-collapse-item name="status" title="当前运行状态">
                <div class="summary-list compact">
                  <div v-for="item in cameraStatusItems" :key="item.label" class="summary-row">
                    <span>{{ item.label }}</span>
                    <strong>{{ item.value }}</strong>
                  </div>
                </div>
              </el-collapse-item>
            </el-collapse>
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
        <section class="usage-block">
          <h3>最短操作路径</h3>
          <ol>
            <li>点击“扫描相机”，从设备名称中选好左/右相机。</li>
            <li>点击“启动画面”，确认水果完整进入预览。</li>
            <li>第一次使用或换相机时，先执行一次“相机校准”。</li>
            <li>点击“立即测量”，在结果区查看果径。</li>
          </ol>
        </section>

        <section class="usage-block">
          <h3>什么时候需要改高级设置</h3>
          <ul>
            <li>大多数情况下只要扫描相机并选择设备即可，不需要改其他参数。</li>
            <li>只有在画面尺寸、帧率、拼接方式变化时，再展开“高级设置”。</li>
            <li>如果不确定相机组合，先扫描，再优先使用系统推荐组合。</li>
          </ul>
        </section>

        <section class="usage-block">
          <h3>结果怎么看</h3>
          <ul>
            <li>平均、最小、最大果径显示的是本次识别到的水果统计值。</li>
            <li>表格里会列出每个水果的果径和识别说明。</li>
            <li>如果没有检测到水果，通常是水果没有完整入镜、距离不合适或画面不清晰。</li>
          </ul>
        </section>
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
      configEditing: false,
      calibrationEditing: false,
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
      openInfoPanels: ['runtime'],
      lastProbeMaxIndex: 8,
      sourceModeOptions: [
        { label: '左右各一台相机', value: 'dual' },
        { label: '一台相机输出左右拼接画面', value: 'single' }
      ],
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
    statistics() {
      return this.measurementResult?.statistics || {}
    },
    measurementTargets() {
      return this.measurementResult?.targets || []
    },
    cameraOptions() {
      const optionMap = new Map()
      for (const item of this.probeResults) {
        if (!item.opened) {
          continue
        }
        optionMap.set(item.camera_index, {
          ...item,
          optionLabel: this.buildCameraOptionLabel(item.camera_index, item.device_name)
        })
      }

      const currentIndexes = [this.form.camera_index, this.form.left_camera_index, this.form.right_camera_index]
      for (const cameraIndex of currentIndexes) {
        if (cameraIndex === null || cameraIndex === undefined || optionMap.has(cameraIndex)) {
          continue
        }
        optionMap.set(cameraIndex, {
          camera_index: cameraIndex,
          opened: false,
          device_name: '',
          optionLabel: this.buildCameraOptionLabel(cameraIndex, '')
        })
      }

      return Array.from(optionMap.values()).sort((a, b) => a.camera_index - b.camera_index)
    },
    recommendedPairText() {
      if (!this.hasRecommendedPair) {
        return '未找到'
      }
      return this.formatPairLabel(this.recommendedPair[0], this.recommendedPair[1])
    },
    hasRecommendedPair() {
      return Array.isArray(this.recommendedPair) && this.recommendedPair.length === 2
    },
    cameraIndexText() {
      if (this.form.source_mode === 'single') {
        return this.formatCameraLabel(this.form.camera_index)
      }
      return `${this.formatCameraLabel(this.form.left_camera_index)} / ${this.formatCameraLabel(this.form.right_camera_index)}`
    },
    selectedCameraSummary() {
      if (this.form.source_mode === 'single') {
        return `当前相机：${this.formatCameraLabel(this.form.camera_index)}`
      }
      return `左：${this.formatCameraLabel(this.form.left_camera_index)}，右：${this.formatCameraLabel(this.form.right_camera_index)}`
    },
    sourceModeLabel() {
      return this.form.source_mode === 'single' ? '一台相机输出左右拼接画面' : '左右各一台相机'
    },
    splitModeLabel() {
      return this.form.split_mode === 'top_bottom' ? '上下拼接' : '左右拼接'
    },
    frameSizeText() {
      if (this.form.frame_width && this.form.frame_height) {
        return `${this.form.frame_width} x ${this.form.frame_height}`
      }
      return '跟随相机默认值'
    },
    fpsText() {
      return this.form.fps ? `${this.form.fps} fps` : '跟随相机默认值'
    },
    runtimeModeCopy() {
      if (!this.runtimeStatus) {
        return '引擎状态未读取'
      }
      return this.runtimeStatus.device_type === 'cuda' ? 'GPU 加速' : 'CPU 模式'
    },
    runtimeSummaryText() {
      if (!this.runtimeStatus) {
        return '点击“刷新引擎”查看当前设备信息'
      }
      const device = this.runtimeStatus.device_type || '-'
      const torch = this.runtimeStatus.torch_version || '-'
      return `当前设备：${device}，PyTorch：${torch}`
    },
    calibrationReady() {
      return this.calibrationPairCount >= this.calibrationForm.min_pairs
    },
    configSummaryItems() {
      return [
        { label: '相机连接方式', value: this.sourceModeLabel },
        { label: '当前相机组合', value: this.selectedCameraSummary },
        { label: '推荐组合', value: this.recommendedPairText },
        { label: '拼接方式', value: this.splitModeLabel },
        { label: '画面尺寸', value: this.frameSizeText },
        { label: '采集帧率', value: this.fpsText },
        { label: '识别灵敏度', value: Number(this.form.conf || 0).toFixed(2) },
        { label: '预览识别框', value: this.detectPreview ? '显示' : '隐藏' },
        { label: '测量结果图', value: this.form.save_vis ? '保存' : '不保存' }
      ]
    },
    calibrationSummaryItems() {
      return [
        { label: '当前会话', value: this.calibrationSessionId || '未开始' },
        { label: '已采集图片组数', value: `${this.calibrationPairCount} / ${this.calibrationForm.min_pairs}` },
        { label: '自动应用校准', value: this.calibrationForm.activate ? '是' : '否' },
        {
          label: '当前标定文件',
          value:
            this.calibrationResult?.activated_calib_path ||
            this.calibrationResult?.output_calib_path ||
            this.runtimeStatus?.calib_path ||
            '暂无',
          isPath: true
        }
      ]
    },
    runtimeDetailItems() {
      if (!this.runtimeStatus) {
        return [{ label: '状态', value: '尚未读取运行时信息' }]
      }
      return [
        {
          label: '设备偏好',
          value: this.runtimeStatus.device_setting || this.runtimeStatus.preferred_device || 'auto'
        },
        { label: '当前设备', value: this.runtimeStatus.device_type || '-' },
        { label: 'PyTorch', value: this.runtimeStatus.torch_version || '-' },
        { label: 'CUDA', value: this.runtimeStatus.torch_cuda_version || '未启用' },
        { label: 'GPU 数量', value: String(this.runtimeStatus.device_count ?? 0) },
        { label: '标定文件', value: this.runtimeStatus.calib_path || '-', isPath: true }
      ]
    },
    cameraStatusItems() {
      return [
        { label: '画面运行状态', value: this.cameraStatus.active ? '运行中' : '未启动' },
        { label: '最后取帧时间', value: this.lastFrameTime },
        { label: '连续失败次数', value: String(this.cameraStatus.consecutive_failures ?? 0) },
        { label: '最近错误', value: this.cameraStatus.last_open_error || '无' }
      ]
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
    patchFormFromConfig(config = {}) {
      const keys = [
        'source_mode',
        'camera_index',
        'left_camera_index',
        'right_camera_index',
        'split_mode',
        'frame_width',
        'frame_height',
        'fps'
      ]
      for (const key of keys) {
        if (config[key] !== undefined && config[key] !== null) {
          this.form[key] = config[key]
        }
      }
    },
    buildCameraOptionLabel(cameraIndex, deviceName) {
      if (deviceName) {
        return `${deviceName}（索引 ${cameraIndex}）`
      }
      return `相机 ${cameraIndex}`
    },
    getCameraOption(cameraIndex) {
      return this.cameraOptions.find((item) => item.camera_index === cameraIndex) || null
    },
    getCameraName(cameraIndex) {
      return this.getCameraOption(cameraIndex)?.device_name || ''
    },
    formatCameraLabel(cameraIndex) {
      const deviceName = this.getCameraName(cameraIndex)
      return deviceName ? `${deviceName}（${cameraIndex}）` : `相机 ${cameraIndex}`
    },
    formatPairLabel(leftIndex, rightIndex) {
      return `${this.formatCameraLabel(leftIndex)} / ${this.formatCameraLabel(rightIndex)}`
    },
    useRecommendedPair() {
      if (!this.hasRecommendedPair) {
        return
      }
      this.form.source_mode = 'dual'
      this.form.left_camera_index = this.recommendedPair[0]
      this.form.right_camera_index = this.recommendedPair[1]
      ElMessage.success(`已切换为推荐组合：${this.recommendedPairText}`)
    },
    currentCameraSelectionInvalid() {
      if (!this.cameraOptions.length) {
        return true
      }
      if (this.form.source_mode === 'single') {
        return !this.getCameraOption(this.form.camera_index)
      }
      return !this.getCameraOption(this.form.left_camera_index) || !this.getCameraOption(this.form.right_camera_index)
    },
    scrollToCalibration() {
      const target = document.getElementById('calibration-card')
      if (target) {
        target.scrollIntoView({ behavior: 'smooth', block: 'start' })
      }
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
          this.patchFormFromConfig(payload.config || {})
          return
        }
        if (payload.type === 'preview.status') {
          this.previewStatus = payload
          this.cameraStatus.active = !!payload.camera_active
          this.cameraStatus.last_frame_ts = payload.last_frame_ts || null
          this.cameraStatus.consecutive_failures = payload.consecutive_failures || 0
          if (payload.config) {
            this.cameraStatus.config = payload.config
            this.patchFormFromConfig(payload.config)
          }
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
        this.applyStatus(data, { connectPreview: !!data.active })
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
        this.errorMessage = this.extractError(error, '读取测量引擎状态失败')
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
        this.errorMessage = this.extractError(error, '读取校准状态失败')
      }
    },
    async probeCameras() {
      this.probing = true
      this.errorMessage = ''
      try {
        const data = await probeCameraIndices(this.lastProbeMaxIndex)
        this.probeResults = data.results || []
        this.pairProbeResults = data.pair_results || []
        this.recommendedPair = data.recommended_dual_pair || null
        this.openInfoPanels = Array.from(new Set([...this.openInfoPanels, 'probe']))

        if (this.currentCameraSelectionInvalid() && this.hasRecommendedPair) {
          this.useRecommendedPair()
        } else if (this.hasRecommendedPair) {
          ElMessage.success(`扫描完成，推荐组合为：${this.recommendedPairText}`)
        } else if ((data.opened_count || 0) > 0) {
          ElMessage.warning('已扫描到相机，但没有找到可同时打开的推荐双摄组合')
        } else {
          ElMessage.warning('没有扫描到可用相机')
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
      this.patchFormFromConfig(this.cameraStatus.config)

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
      if (this.form.source_mode === 'dual' && this.form.left_camera_index === this.form.right_camera_index) {
        this.errorMessage = '双摄模式下，左相机和右相机不能选择同一个设备'
        return
      }
      this.starting = true
      this.errorMessage = ''
      try {
        const data = await startStereoCamera(this.toPayload())
        this.applyStatus(data, { connectPreview: true })
        this.configEditing = false
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
        ElMessage.success(`已采集第 ${data.captured_index} 组校准图`)
      } catch (error) {
        this.errorMessage = this.extractError(error, '采集校准图失败')
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
        this.calibrationEditing = false
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
.overview-card,
.control-card,
.preview-card,
.result-card {
  border: none;
  border-radius: 24px;
  background: rgba(255, 255, 255, 0.94);
  box-shadow: 0 20px 42px rgba(27, 51, 40, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) minmax(340px, 0.9fr);
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
  max-width: 780px;
  line-height: 1.8;
  color: rgba(246, 251, 248, 0.86);
}

.hero-actions {
  display: grid;
  gap: 14px;
  align-content: start;
}

.primary-actions,
.secondary-actions,
.hero-badges,
.overview-actions,
.preview-toolbar__actions,
.inline-actions,
.picker-toolbar {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.hero-badge {
  display: inline-flex;
  align-items: center;
  min-height: 36px;
  padding: 0 14px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  color: #eff8f4;
  font-size: 13px;
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
.empty-state h3,
.preview-placeholder h3 {
  margin: 0 0 6px;
  font-size: 18px;
  color: #18352b;
}

.guide-step p,
.empty-state p,
.preview-placeholder p {
  margin: 0;
  line-height: 1.7;
  color: #557064;
}

.overview-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 16px;
}

.overview-card {
  padding: 20px;
}

.overview-label {
  display: block;
  margin-bottom: 10px;
  font-size: 13px;
  color: #60796d;
}

.overview-value {
  display: block;
  font-size: 24px;
  line-height: 1.2;
  color: #19362c;
}

.overview-meta {
  margin: 10px 0 14px;
  min-height: 42px;
  line-height: 1.6;
  color: #587166;
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

.card-header {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 14px;
  font-weight: 700;
}

.card-subtitle {
  margin: 6px 0 0;
  font-weight: 400;
  font-size: 13px;
  line-height: 1.6;
  color: #678075;
}

.preview-toolbar,
.toggle-list,
.button-group {
  display: grid;
  gap: 12px;
}

.preview-toolbar {
  margin-bottom: 18px;
}

.toggle-pill {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  background: #f4f8f5;
  color: #224438;
}

.preview-stage {
  min-height: 500px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: 24px;
  overflow: hidden;
  background: linear-gradient(140deg, #0f172a 0%, #1a2c43 100%);
  border: 1px solid rgba(148, 163, 184, 0.18);
}

.preview-image,
.result-image {
  display: block;
  width: 100%;
  height: auto;
}

.preview-placeholder {
  max-width: 380px;
  text-align: center;
  padding: 28px;
}

.preview-placeholder h3,
.preview-placeholder p {
  color: rgba(236, 244, 241, 0.92);
}

.preview-error {
  margin: 14px 0 0;
  color: #b42318;
  line-height: 1.7;
}

.camera-picker-card {
  margin-bottom: 16px;
  padding: 16px;
  border-radius: 18px;
  background: #f6faf7;
}

.picker-hint {
  color: #587166;
  font-size: 13px;
  line-height: 32px;
}

.summary-list {
  display: grid;
  gap: 10px;
  padding: 16px;
  border-radius: 18px;
  background: #f6faf7;
}

.summary-list.compact {
  padding: 0;
  background: transparent;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  font-size: 13px;
  color: #587166;
}

.summary-row strong {
  text-align: right;
  color: #1b2f28;
}

.inline-actions {
  margin-top: 14px;
}

.edit-panel,
.success-panel,
.probe-section {
  margin-top: 16px;
}

.camera-form :deep(.el-form-item) {
  margin-bottom: 16px;
}

.inline-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.empty-inline-tip {
  padding: 14px 16px;
  border-radius: 14px;
  background: rgba(255, 255, 255, 0.8);
  border: 1px dashed rgba(36, 84, 70, 0.16);
  color: #587166;
  line-height: 1.7;
}

.calibration-note {
  margin-top: 16px;
  padding: 14px 16px;
  border-radius: 16px;
  background: rgba(245, 158, 11, 0.12);
  border: 1px solid rgba(245, 158, 11, 0.18);
  color: #7c4a03;
  line-height: 1.7;
}

.button-group {
  margin-top: 16px;
}

.button-group .el-button {
  width: 100%;
}

.loading-copy {
  display: grid;
  gap: 8px;
  margin-bottom: 16px;
  line-height: 1.7;
  color: #35594d;
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
  margin-bottom: 8px;
  font-size: 13px;
  color: #5b746a;
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

.empty-state {
  padding: 18px 6px 4px;
}

.compact-empty {
  padding: 8px 0 0;
}

.path-text {
  word-break: break-all;
}

.info-collapse :deep(.el-collapse-item__header) {
  font-weight: 600;
  color: #204337;
}

.info-collapse :deep(.el-collapse-item__wrap) {
  border-bottom: none;
}

.probe-list {
  display: grid;
  gap: 10px;
  margin-top: 14px;
}

.probe-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  padding: 12px 14px;
  border-radius: 16px;
  background: #fff8eb;
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

.usage-dialog__body {
  color: #26453b;
  line-height: 1.8;
}

.usage-block {
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, #f8fbfa 0%, #eef5f1 100%);
  border: 1px solid rgba(36, 84, 70, 0.08);
}

.usage-block + .usage-block {
  margin-top: 16px;
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

.usage-block li + li {
  margin-top: 8px;
}

@media (max-width: 1320px) {
  .overview-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

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
  .diameter-page {
    padding: 12px;
  }

  .hero {
    padding: 22px 20px;
  }

  .hero h1 {
    font-size: 30px;
  }

  .overview-grid,
  .inline-grid,
  .result-meta {
    grid-template-columns: 1fr;
  }

  .preview-stage {
    min-height: 300px;
  }

  .summary-row {
    flex-direction: column;
  }

  .summary-row strong {
    text-align: left;
  }
}
</style>
