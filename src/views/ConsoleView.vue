<template>
  <div class="console-page">
    <section class="hero">
      <div>
        <p class="eyebrow">Control Console</p>
        <h1>控制台</h1>
        <p class="hero-text">
          展示当前用户的检测统计、果径分析、最近检测记录以及系统运行状态。
        </p>
        <div class="hero-notes">
          <span class="hero-note">统计时区：{{ filters.timezone }}</span>
          <span class="hero-note">最近更新：{{ lastUpdatedText }}</span>
        </div>
      </div>
      <div class="hero-actions">
        <el-button type="primary" :loading="loading" @click="fetchOverviewAndRecent">刷新统计</el-button>
        <el-button :loading="systemLoading" @click="fetchSystemStatus">刷新系统状态</el-button>
        <el-button @click="refreshAll">全部刷新</el-button>
      </div>
    </section>

    <section class="panel filters">
      <div class="filters-row">
        <div class="filter-block">
          <span class="filter-label">时间范围</span>
          <el-segmented v-model="filters.rangeType" :options="rangeOptions" @change="handleRangeTypeChange" />
        </div>

        <div class="filter-block filter-block--type">
          <span class="filter-label">检测类型</span>
          <el-select v-model="filters.detectionType" @change="handleDetectionTypeChange">
            <el-option v-for="item in detectionOptions" :key="item.value" :label="item.label" :value="item.value" />
          </el-select>
        </div>

        <div v-if="filters.rangeType === 'custom'" class="filter-block filter-block--date">
          <span class="filter-label">自定义日期</span>
          <el-date-picker
            v-model="filters.customDates"
            type="daterange"
            range-separator="至"
            start-placeholder="开始日期"
            end-placeholder="结束日期"
            value-format="YYYY-MM-DD"
            @change="handleCustomDateChange"
          />
        </div>
      </div>
    </section>

    <section class="summary-grid" v-loading="loading">
      <article v-for="item in summaryItems" :key="item.key" class="summary-card">
        <span class="summary-label">{{ item.label }}</span>
        <strong class="summary-value">{{ item.value }}</strong>
        <p class="summary-meta">{{ item.meta }}</p>
      </article>
    </section>

    <section class="content-grid">
      <article class="panel">
        <div class="panel-header">
          <div>
            <h2>检测类型分布</h2>
            <p>按当前筛选范围统计图片检测、实时检测和果径测量记录。</p>
          </div>
        </div>

        <div class="distribution-list">
          <div v-for="item in analysis.detection_type_distribution || []" :key="item.type" class="distribution-item">
            <div class="distribution-copy">
              <strong>{{ item.label }}</strong>
              <span>{{ item.count }} 次</span>
            </div>
            <div class="distribution-bar">
              <span class="distribution-fill" :style="{ width: `${item.percentage || 0}%`, backgroundColor: typeColors[item.type] }"></span>
            </div>
            <span class="distribution-percent">{{ formatPercent(item.percentage) }}</span>
          </div>
        </div>

        <div class="subsection">
          <div class="subsection-head">
            <h3>水果 Top 5</h3>
            <span>按识别数量排序</span>
          </div>
          <div v-if="fruitRankingTop.length" class="ranking-list">
            <div v-for="item in fruitRankingTop" :key="item.fruit" class="ranking-item">
              <div class="ranking-copy">
                <strong>{{ item.fruit }}</strong>
                <span>{{ item.count }} 个</span>
              </div>
              <div class="ranking-bar">
                <span class="ranking-fill" :style="{ width: `${fruitShare(item.count)}%` }"></span>
              </div>
            </div>
          </div>
          <el-empty v-else description="暂无水果识别数据" />
        </div>
      </article>

      <article class="panel">
        <div class="panel-header">
          <div>
            <h2>果径分析</h2>
            <p>汇总有效果径测量记录与平均果径。</p>
          </div>
        </div>

        <div class="metric-grid">
          <div class="metric-card">
            <span>测量次数</span>
            <strong>{{ diameterAnalysis.measure_count || 0 }}</strong>
          </div>
          <div class="metric-card">
            <span>有效测量率</span>
            <strong>{{ formatPercent(diameterAnalysis.success_rate) }}</strong>
          </div>
          <div class="metric-card">
            <span>横向平均果径</span>
            <strong>{{ formatMetric(diameterAnalysis.horizontal?.avg_diameter_mm, 'mm', 2) }}</strong>
          </div>
          <div class="metric-card">
            <span>竖向平均果径</span>
            <strong>{{ formatMetric(diameterAnalysis.vertical?.avg_diameter_mm, 'mm', 2) }}</strong>
          </div>
          <div class="metric-card">
            <span>横向最小 / 最大</span>
            <strong>{{ horizontalMinMaxDiameterText }}</strong>
          </div>
          <div class="metric-card">
            <span>竖向最小 / 最大</span>
            <strong>{{ verticalMinMaxDiameterText }}</strong>
          </div>
          <div class="metric-card">
            <span>横向 / 竖向有效数</span>
            <strong>{{ diameterAxisCountText }}</strong>
          </div>
        </div>
      </article>

      <article class="panel">
        <div class="panel-header">
          <div>
            <h2>最近活动</h2>
            <p>显示最近检测历史记录，并提供常用入口。</p>
          </div>
        </div>

        <div class="quick-actions">
          <button v-for="item in quickActions" :key="item.path" class="quick-action" @click="goTo(item.path)">
            <strong>{{ item.label }}</strong>
            <span>{{ item.desc }}</span>
          </button>
        </div>

        <div v-if="recentHistories.length" class="activity-list">
          <div v-for="item in recentHistories" :key="item.id" class="activity-item">
            <div class="activity-head">
              <div>
                <strong>{{ item.detection_type_display }}</strong>
                <span>{{ formatDateTime(item.created_at) }}</span>
              </div>
              <div class="activity-actions">
                <el-button size="small" @click="goTo('/history')">查看历史</el-button>
                <el-button v-if="item.report_file" type="primary" size="small" @click="downloadReport(item.report_file)">
                  下载报告
                </el-button>
              </div>
            </div>
            <p>{{ historySummaryText(item) }}</p>
          </div>
        </div>
        <el-empty v-else description="暂无最近活动" />
      </article>

      <article class="panel" :class="{ 'panel-loading': systemLoading }" v-loading="systemLoading">
        <div class="panel-header">
          <div>
            <h2>系统状态</h2>
            <p>聚合后端健康检查、相机状态、果径运行时与标定状态。</p>
          </div>
        </div>

        <div class="system-grid">
          <div class="system-card">
            <div class="system-head">
              <strong>后端服务</strong>
              <el-tag :type="systemBackendTagType">{{ systemBackendStatus }}</el-tag>
            </div>
            <p>{{ systemStatus.backend_health?.message || '无状态信息' }}</p>
          </div>

          <div class="system-card">
            <div class="system-head">
              <strong>相机状态</strong>
              <el-tag :type="cameraTagType">{{ cameraStatusText }}</el-tag>
            </div>
            <p>模式：{{ cameraModeText }}</p>
            <p>最近帧时间：{{ cameraLastFrameText }}</p>
            <p>连续失败次数：{{ systemStatus.camera_status?.consecutive_failures ?? 0 }}</p>
          </div>

          <div class="system-card">
            <div class="system-head">
              <strong>果径运行时</strong>
              <el-tag :type="runtimeTagType">{{ runtimeDeviceText }}</el-tag>
            </div>
            <p>CUDA：{{ booleanText(systemStatus.measure_runtime_status?.cuda_available) }}</p>
            <p>模型加载：{{ booleanText(systemStatus.measure_runtime_status?.model_loaded) }}</p>
            <p>设备设置：{{ systemStatus.measure_runtime_status?.device_setting || '-' }}</p>
          </div>

          <div class="system-card">
            <div class="system-head">
              <strong>标定状态</strong>
              <el-tag :type="calibrationTagType">{{ calibrationStatusText }}</el-tag>
            </div>
            <p>最近 Session：{{ systemStatus.calibration_status?.session_id || '暂无' }}</p>
            <p>已采集对数：{{ systemStatus.calibration_status?.pair_count ?? 0 }}</p>
            <p>标定结果：{{ calibrationResultText }}</p>
          </div>
        </div>
      </article>
    </section>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { getConsoleOverview, getConsoleRecent, getConsoleSystemStatus } from '@/api/console'
import { translateFruitLabel } from '@/utils/labelMap'

const TYPE_COLORS = {
  image: '#2f6c59',
  realtime: '#f4a340',
  diameter: '#2c6bed'
}

export default {
  name: 'ConsoleView',
  data() {
    return {
      loading: false,
      systemLoading: false,
      lastUpdatedAt: null,
      filters: {
        rangeType: 'last30days',
        detectionType: 'all',
        timezone: this.getBrowserTimezone(),
        customDates: []
      },
      rangeOptions: [
        { label: '今天', value: 'today' },
        { label: '近 7 天', value: 'last7days' },
        { label: '近 30 天', value: 'last30days' },
        { label: '自定义', value: 'custom' }
      ],
      detectionOptions: [
        { label: '全部', value: 'all' },
        { label: '图片检测', value: 'image' },
        { label: '实时检测', value: 'realtime' },
        { label: '果径测量', value: 'diameter' }
      ],
      quickActions: [
        { path: '/detection/image', label: '图片检测', desc: '上传图片并生成识别结果' },
        { path: '/detection/realtime', label: '实时检测', desc: '使用默认相机配置进行实时识别' },
        { path: '/camera/config', label: '摄像头拍照与配置', desc: '扫描摄像头、设置左右机位并进行拍照测试' },
        { path: '/history', label: '检测历史', desc: '查看详情、下载报告并删除记录' }
      ],
      typeColors: TYPE_COLORS,
      overview: this.createEmptyOverview(),
      recent: this.createEmptyRecent(),
      systemStatus: this.createEmptySystemStatus()
    }
  },
  computed: {
    summaryCards() {
      return this.overview.summary_cards || {}
    },
    analysis() {
      return this.overview.analysis || this.createEmptyOverview().analysis
    },
    diameterAnalysis() {
      return this.overview.diameter_analysis || {}
    },
    recentHistories() {
      return this.recent.recent_histories || []
    },
    summaryItems() {
      return [
        {
          key: 'detection_count',
          label: '检测记录总数',
          value: this.formatMetric(this.summaryCards.detection_count, '', 0, '0'),
          meta: '当前筛选范围内写入历史表的记录数'
        },
        {
          key: 'total_targets',
          label: '识别目标总数',
          value: this.formatMetric(this.summaryCards.total_targets, '', 0, '0'),
          meta: '所有历史记录 total_targets 汇总'
        },
        {
          key: 'image_detection_count',
          label: '图片检测次数',
          value: this.formatMetric(this.summaryCards.image_detection_count, '', 0, '0'),
          meta: '生成图片检测报告后计入'
        },
        {
          key: 'realtime_detection_count',
          label: '实时检测次数',
          value: this.formatMetric(this.summaryCards.realtime_detection_count, '', 0, '0'),
          meta: '保存实时检测报告后计入'
        },
        {
          key: 'diameter_detection_count',
          label: '果径测量次数',
          value: this.formatMetric(this.summaryCards.diameter_detection_count, '', 0, '0'),
          meta: '包含双目果径测量历史记录'
        },
        {
          key: 'valid_diameter_measurements',
          label: '有效果径测量数',
          value: this.formatMetric(this.summaryCards.valid_diameter_measurements, '', 0, '0'),
          meta: '仅统计果径记录中的有效测量目标'
        }
      ]
    },
    fruitRankingTop() {
      return (this.analysis.fruit_ranking || []).slice(0, 5).map((item) => ({
        ...item,
        fruit: translateFruitLabel(item.fruit)
      }))
    },
    horizontalMinMaxDiameterText() {
      const min = this.formatMetric(this.diameterAnalysis.horizontal?.min_diameter_mm, 'mm', 2)
      const max = this.formatMetric(this.diameterAnalysis.horizontal?.max_diameter_mm, 'mm', 2)
      return `${min} / ${max}`
    },
    verticalMinMaxDiameterText() {
      const min = this.formatMetric(this.diameterAnalysis.vertical?.min_diameter_mm, 'mm', 2)
      const max = this.formatMetric(this.diameterAnalysis.vertical?.max_diameter_mm, 'mm', 2)
      return `${min} / ${max}`
    },
    diameterAxisCountText() {
      const counts = this.diameterAnalysis.valid_measurements_by_axis || {}
      return `${counts.horizontal || 0} / ${counts.vertical || 0}`
    },
    lastUpdatedText() {
      return this.lastUpdatedAt ? this.lastUpdatedAt.toLocaleString('zh-CN') : '尚未加载'
    },
    systemBackendStatus() {
      return this.systemStatus.backend_health?.status === 'ok' ? '正常' : '异常'
    },
    systemBackendTagType() {
      return this.systemStatus.backend_health?.status === 'ok' ? 'success' : 'danger'
    },
    cameraTagType() {
      if (this.systemStatus.camera_status?.status === 'error') return 'danger'
      return this.systemStatus.camera_status?.active ? 'success' : 'info'
    },
    cameraStatusText() {
      if (this.systemStatus.camera_status?.status === 'error') return '异常'
      return this.systemStatus.camera_status?.active ? '运行中' : '未启动'
    },
    cameraModeText() {
      const config = this.systemStatus.camera_status?.config || {}
      if (!Object.keys(config).length) return '-'
      return `${config.source_mode || 'unknown'} / ${config.split_mode || 'left_right'}`
    },
    cameraLastFrameText() {
      const raw = this.systemStatus.camera_status?.last_frame_ts
      if (!raw) return '暂无'
      const date = new Date(Number(raw) * 1000)
      return Number.isNaN(date.getTime()) ? '暂无' : date.toLocaleString('zh-CN')
    },
    runtimeTagType() {
      if (this.systemStatus.measure_runtime_status?.status === 'error') return 'danger'
      return this.systemStatus.measure_runtime_status?.device_type === 'cuda' ? 'success' : 'warning'
    },
    runtimeDeviceText() {
      if (this.systemStatus.measure_runtime_status?.status === 'error') return '异常'
      return (this.systemStatus.measure_runtime_status?.device_type || 'unknown').toUpperCase()
    },
    calibrationTagType() {
      if (this.systemStatus.calibration_status?.status === 'error') return 'danger'
      return this.systemStatus.calibration_status?.result ? 'success' : 'warning'
    },
    calibrationStatusText() {
      if (this.systemStatus.calibration_status?.status === 'error') return '异常'
      return this.systemStatus.calibration_status?.result ? '已完成标定' : '待标定'
    },
    calibrationResultText() {
      return this.systemStatus.calibration_status?.result ? '已有可用结果' : '暂无结果'
    }
  },
  mounted() {
    this.refreshAll()
  },
  methods: {
    createEmptyOverview() {
      return {
        summary_cards: {},
        analysis: {
          fruit_ranking: [],
          fruit_distribution: [],
          ripeness_distribution: [],
          detection_type_distribution: []
        },
        diameter_analysis: {}
      }
    },
    createEmptyRecent() {
      return {
        recent_histories: []
      }
    },
    createEmptySystemStatus() {
      return {
        backend_health: {},
        camera_status: {},
        measure_runtime_status: {},
        calibration_status: {}
      }
    },
    getBrowserTimezone() {
      try {
        return Intl.DateTimeFormat().resolvedOptions().timeZone || 'Asia/Shanghai'
      } catch (_error) {
        return 'Asia/Shanghai'
      }
    },
    buildQueryParams() {
      const params = {
        range_type: this.filters.rangeType,
        detection_type: this.filters.detectionType,
        timezone: this.filters.timezone
      }
      if (this.filters.rangeType === 'custom' && this.filters.customDates.length === 2) {
        params.start_date = this.filters.customDates[0]
        params.end_date = this.filters.customDates[1]
      }
      return params
    },
    canQuery() {
      return this.filters.rangeType !== 'custom' || this.filters.customDates.length === 2
    },
    async fetchOverviewAndRecent() {
      if (!this.canQuery()) {
        return
      }

      this.loading = true
      try {
        const params = this.buildQueryParams()
        const [overview, recent] = await Promise.all([
          getConsoleOverview(params),
          getConsoleRecent(params)
        ])
        this.overview = overview
        this.recent = recent
        this.lastUpdatedAt = new Date()
      } catch (error) {
        ElMessage.error(error?.response?.data?.error || '获取控制台统计失败')
      } finally {
        this.loading = false
      }
    },
    async fetchSystemStatus() {
      this.systemLoading = true
      try {
        this.systemStatus = await getConsoleSystemStatus()
      } catch (error) {
        ElMessage.error(error?.response?.data?.error || '获取系统状态失败')
      } finally {
        this.systemLoading = false
      }
    },
    async refreshAll() {
      await Promise.all([this.fetchOverviewAndRecent(), this.fetchSystemStatus()])
    },
    handleRangeTypeChange() {
      if (this.filters.rangeType !== 'custom') {
        this.filters.customDates = []
        this.fetchOverviewAndRecent()
      }
    },
    handleCustomDateChange() {
      if (this.filters.rangeType === 'custom' && this.filters.customDates.length === 2) {
        this.fetchOverviewAndRecent()
      }
    },
    handleDetectionTypeChange() {
      this.fetchOverviewAndRecent()
    },
    formatMetric(value, suffix = '', digits = 0, empty = '-') {
      if (value === null || value === undefined || value === '') {
        return empty
      }
      const numericValue = Number(value)
      if (!Number.isFinite(numericValue)) {
        return empty
      }
      return `${numericValue.toFixed(digits)}${suffix ? ` ${suffix}` : ''}`
    },
    formatPercent(value) {
      return this.formatMetric(value, '%', 2, '0%')
    },
    formatDateTime(value) {
      if (!value) return '-'
      const date = new Date(value)
      return Number.isNaN(date.getTime()) ? '-' : date.toLocaleString('zh-CN')
    },
    booleanText(value) {
      return value ? '是' : '否'
    },
    fruitShare(count) {
      const maxCount = Math.max(...this.fruitRankingTop.map((item) => Number(item.count || 0)), 1)
      return (Number(count || 0) / maxCount) * 100
    },
    historySummaryText(item) {
      const summary = item.summary || {}
      if (item.detection_type === 'diameter') {
        return `目标 ${summary.total_targets || 0} 个，成功测量 ${summary.valid_measurements || 0} 个`
      }
      const fruitCount = summary.fruit_counts ? Object.keys(summary.fruit_counts).length : 0
      return `识别目标 ${summary.total_targets || 0} 个，水果类别 ${fruitCount} 种`
    },
    goTo(path) {
      this.$router.push(path)
    },
    downloadReport(reportFile) {
      if (!reportFile) {
        ElMessage.warning('当前记录没有可下载报告')
        return
      }

      const link = document.createElement('a')
      link.href = `/media/${reportFile}`
      link.download = reportFile.split('/').pop()
      document.body.appendChild(link)
      link.click()
      document.body.removeChild(link)
    }
  }
}
</script>

<style scoped>
.console-page {
  display: grid;
  gap: 18px;
  padding: 20px;
  background:
    radial-gradient(circle at top left, rgba(39, 112, 89, 0.18), transparent 24%),
    radial-gradient(circle at top right, rgba(244, 163, 64, 0.12), transparent 22%),
    linear-gradient(180deg, #f3f6f4 0%, #ecf2ee 100%);
}

.hero,
.panel,
.summary-card {
  border-radius: 24px;
  border: none;
  background: rgba(255, 255, 255, 0.96);
  box-shadow: 0 20px 42px rgba(28, 52, 42, 0.08);
}

.hero {
  display: grid;
  grid-template-columns: minmax(0, 1.4fr) auto;
  gap: 18px;
  padding: 28px 30px;
  background: linear-gradient(135deg, #12372d 0%, #225244 55%, #326a57 100%);
  color: #f4fbf7;
}

.eyebrow {
  margin: 0 0 8px;
  font-size: 12px;
  letter-spacing: 0.18em;
  text-transform: uppercase;
  color: rgba(244, 251, 247, 0.72);
}

.hero h1,
.panel-header h2,
.subsection-head h3 {
  margin: 0;
}

.hero h1 {
  font-size: 38px;
  line-height: 1.1;
}

.hero-text {
  margin: 14px 0 0;
  max-width: 760px;
  line-height: 1.8;
  color: rgba(244, 251, 247, 0.88);
}

.hero-notes,
.hero-actions,
.filters-row,
.quick-actions {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.hero-notes {
  margin-top: 18px;
}

.hero-note {
  padding: 8px 12px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.12);
  font-size: 13px;
}

.hero-actions {
  justify-content: flex-end;
  align-items: flex-start;
}

.panel {
  padding: 22px;
}

.filter-block {
  display: grid;
  gap: 8px;
}

.filter-block--type {
  min-width: 220px;
}

.filter-block--date {
  min-width: 340px;
}

.filter-label,
.summary-label,
.summary-meta,
.panel-header p,
.subsection-head span,
.distribution-copy span,
.distribution-percent,
.system-card p,
.activity-item p {
  color: #5c766c;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 16px;
}

.summary-card {
  padding: 20px;
}

.summary-label {
  display: block;
  margin-bottom: 10px;
  font-size: 13px;
}

.summary-value {
  display: block;
  font-size: 28px;
  color: #17372d;
  line-height: 1.1;
}

.summary-meta {
  margin: 12px 0 0;
  min-height: 38px;
  line-height: 1.6;
  font-size: 13px;
}

.content-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 18px;
}

.panel-header {
  margin-bottom: 18px;
}

.panel-header p {
  margin: 6px 0 0;
  line-height: 1.7;
}

.distribution-list,
.ranking-list,
.activity-list {
  display: grid;
  gap: 12px;
}

.distribution-item,
.metric-card,
.system-card,
.activity-item,
.quick-action {
  border-radius: 18px;
  background: #f7faf8;
  border: 1px solid rgba(29, 62, 50, 0.06);
}

.distribution-item,
.system-card,
.activity-item {
  padding: 16px;
}

.distribution-copy,
.activity-head,
.system-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.distribution-bar,
.ranking-bar {
  height: 10px;
  margin-top: 10px;
  border-radius: 999px;
  background: #e7efea;
  overflow: hidden;
}

.distribution-fill,
.ranking-fill {
  height: 100%;
  display: block;
  border-radius: 999px;
}

.ranking-fill {
  background: linear-gradient(90deg, #2f6c59 0%, #5d9e86 100%);
}

.subsection {
  margin-top: 18px;
}

.subsection-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  margin-bottom: 12px;
}

.ranking-item {
  display: grid;
  gap: 8px;
}

.ranking-copy {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.metric-grid,
.system-grid,
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 12px;
}

.metric-card {
  padding: 16px;
  display: grid;
  gap: 8px;
}

.metric-card span {
  font-size: 13px;
  color: #60796d;
}

.metric-card strong {
  font-size: 24px;
  color: #17362d;
}

.quick-action {
  padding: 18px;
  text-align: left;
  cursor: pointer;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.quick-action:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(31, 67, 54, 0.08);
}

.quick-action strong {
  display: block;
  margin-bottom: 8px;
  color: #16352b;
}

.quick-action span {
  color: #5c766c;
  line-height: 1.7;
}

.activity-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.activity-item p {
  margin: 12px 0 0;
  line-height: 1.8;
}

.panel-loading {
  min-height: 320px;
}

@media (max-width: 1200px) {
  .content-grid,
  .summary-grid,
  .metric-grid,
  .system-grid,
  .quick-actions {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 768px) {
  .console-page {
    padding: 12px;
  }

  .hero {
    grid-template-columns: 1fr;
    padding: 24px 22px;
  }

  .hero-actions,
  .filters-row,
  .activity-head,
  .system-head {
    flex-direction: column;
    align-items: flex-start;
  }
}
</style>

