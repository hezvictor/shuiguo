<template>
  <div class="console-page">
    <div class="page-shell">
      <section class="hero">
        <div class="hero-copy">
          <p class="eyebrow">Control Console</p>
          <h1>控制台</h1>
          <p class="hero-text">
            这里展示当前登录用户的检测总览、果径测量分析、视频任务概况以及后端与设备运行状态。
          </p>
          <div class="hero-notes">
            <span class="hero-note">统计时区：{{ filters.timezone }}</span>
            <span class="hero-note">已生成历史记录的检测才会进入统计</span>
            <span class="hero-note">最近更新：{{ lastUpdatedText }}</span>
          </div>
        </div>

        <div class="hero-actions">
          <el-button type="primary" :loading="loading" @click="fetchOverviewAndRecent">刷新统计</el-button>
          <el-button :loading="systemLoading" @click="fetchSystemStatus">刷新系统状态</el-button>
          <el-button @click="refreshAll">全部刷新</el-button>
        </div>
      </section>

      <section class="filter-card">
        <div class="filter-row">
          <div class="filter-block">
            <span class="filter-label">时间范围</span>
            <el-segmented
              v-model="filters.rangeType"
              :options="rangeOptions"
              @change="handleRangeTypeChange"
            />
          </div>

          <div class="filter-block filter-block--type">
            <span class="filter-label">检测类型</span>
            <el-select v-model="filters.detectionType" @change="handleDetectionTypeChange">
              <el-option
                v-for="item in detectionOptions"
                :key="item.value"
                :label="item.label"
                :value="item.value"
              />
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
        <article
          v-for="item in summaryItems"
          :key="item.key"
          class="summary-card"
        >
          <span class="summary-label">{{ item.label }}</span>
          <strong class="summary-value">{{ item.value }}</strong>
          <p class="summary-meta">{{ item.meta }}</p>
        </article>
      </section>

      <section class="content-grid">
        <article class="panel panel-wide" v-loading="loading">
          <div class="panel-header">
            <div>
              <h2>检测趋势</h2>
              <p>按当前筛选范围汇总检测次数、识别目标数、检测类型与平均果径。</p>
            </div>
          </div>

          <div class="trend-grid">
            <div class="chart-card">
              <div class="chart-head">
                <h3>检测次数趋势</h3>
                <span>{{ trendPeakText(detectionTrendChart.max, '次') }}</span>
              </div>
              <div v-if="detectionTrendChart.markers.length" class="line-chart">
                <svg viewBox="0 0 320 150" preserveAspectRatio="none">
                  <g class="grid-lines">
                    <line v-for="lineIndex in 4" :key="lineIndex" x1="0" :y1="lineIndex * 30" x2="320" :y2="lineIndex * 30" />
                  </g>
                  <path :d="detectionTrendChart.area" class="chart-area" />
                  <polyline :points="detectionTrendChart.points" class="chart-line chart-line--primary" />
                  <circle
                    v-for="marker in detectionTrendChart.markers"
                    :key="`detection-${marker.label}`"
                    :cx="marker.x"
                    :cy="marker.y"
                    r="4"
                    class="chart-point chart-point--primary"
                  />
                </svg>
                <div class="chart-labels">
                  <span v-for="item in trends.daily_detection_trend" :key="item.date">{{ formatDayLabel(item.date) }}</span>
                </div>
              </div>
              <el-empty v-else description="暂无趋势数据" />
            </div>

            <div class="chart-card">
              <div class="chart-head">
                <h3>识别目标数趋势</h3>
                <span>{{ trendPeakText(targetTrendChart.max, '个') }}</span>
              </div>
              <div v-if="targetTrendChart.markers.length" class="line-chart">
                <svg viewBox="0 0 320 150" preserveAspectRatio="none">
                  <g class="grid-lines">
                    <line v-for="lineIndex in 4" :key="lineIndex" x1="0" :y1="lineIndex * 30" x2="320" :y2="lineIndex * 30" />
                  </g>
                  <path :d="targetTrendChart.area" class="chart-area chart-area--warm" />
                  <polyline :points="targetTrendChart.points" class="chart-line chart-line--warm" />
                  <circle
                    v-for="marker in targetTrendChart.markers"
                    :key="`target-${marker.label}`"
                    :cx="marker.x"
                    :cy="marker.y"
                    r="4"
                    class="chart-point chart-point--warm"
                  />
                </svg>
                <div class="chart-labels">
                  <span v-for="item in trends.daily_target_trend" :key="item.date">{{ formatDayLabel(item.date) }}</span>
                </div>
              </div>
              <el-empty v-else description="暂无趋势数据" />
            </div>
          </div>

          <div class="trend-grid trend-grid--secondary">
            <div class="chart-card">
              <div class="chart-head">
                <h3>检测类型趋势</h3>
                <span>堆叠柱状图</span>
              </div>
              <div v-if="trends.daily_type_trend.length" class="stack-chart">
                <div
                  v-for="item in trends.daily_type_trend"
                  :key="item.date"
                  class="stack-column"
                >
                  <div class="stack-value">{{ dayTypeTotal(item) }}</div>
                  <div class="stack-track">
                    <div
                      class="stack-fill"
                      :style="{ height: `${stackedColumnHeight(item)}%` }"
                    >
                      <span
                        v-for="typeKey in typeKeys"
                        :key="`${item.date}-${typeKey}`"
                        class="stack-segment"
                        :style="stackSegmentStyle(item, typeKey)"
                      ></span>
                    </div>
                  </div>
                  <div class="stack-label">{{ formatDayLabel(item.date) }}</div>
                </div>
              </div>
              <el-empty v-else description="暂无趋势数据" />
            </div>

            <div class="chart-card">
              <div class="chart-head">
                <h3>平均果径趋势</h3>
                <span>{{ trendPeakText(diameterTrendChart.max, 'mm') }}</span>
              </div>
              <div v-if="diameterTrendChart.markers.length" class="line-chart">
                <svg viewBox="0 0 320 150" preserveAspectRatio="none">
                  <g class="grid-lines">
                    <line v-for="lineIndex in 4" :key="lineIndex" x1="0" :y1="lineIndex * 30" x2="320" :y2="lineIndex * 30" />
                  </g>
                  <path :d="diameterTrendChart.area" class="chart-area chart-area--accent" />
                  <polyline :points="diameterTrendChart.points" class="chart-line chart-line--accent" />
                  <circle
                    v-for="marker in diameterTrendChart.markers"
                    :key="`diameter-${marker.label}`"
                    :cx="marker.x"
                    :cy="marker.y"
                    r="4"
                    class="chart-point chart-point--accent"
                  />
                </svg>
                <div class="chart-labels">
                  <span v-for="item in trends.daily_avg_diameter_trend" :key="item.date">{{ formatDayLabel(item.date) }}</span>
                </div>
              </div>
              <el-empty v-else description="当前范围内没有有效果径数据" />
            </div>
          </div>
        </article>

        <article class="panel" v-loading="loading">
          <div class="panel-header">
            <div>
              <h2>识别分析</h2>
              <p>展示水果排名、检测类型占比与熟度分布。</p>
            </div>
          </div>

          <div class="type-distribution">
            <div class="type-donut" :style="typeDonutStyle">
              <div class="type-donut__center">
                <strong>{{ summaryCards.detection_count || 0 }}</strong>
                <span>检测记录</span>
              </div>
            </div>

            <div class="type-legend">
              <div v-for="item in analysis.detection_type_distribution" :key="item.type" class="legend-item">
                <span class="legend-dot" :style="{ backgroundColor: typeColors[item.type] }"></span>
                <div class="legend-copy">
                  <strong>{{ item.label }}</strong>
                  <span>{{ item.count }} 次 · {{ formatPercent(item.percentage) }}</span>
                </div>
              </div>
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
                  <span
                    class="ranking-bar__fill"
                    :style="{ width: `${fruitShare(item.count)}%` }"
                  ></span>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无水果识别数据" />
          </div>

          <div class="subsection">
            <div class="subsection-head">
              <h3>熟度分布</h3>
              <span>按水果展开</span>
            </div>
            <div v-if="ripenessGroups.length" class="ripeness-groups">
              <div v-for="group in ripenessGroups" :key="group.fruit" class="ripeness-card">
                <div class="ripeness-card__head">
                  <strong>{{ group.fruit }}</strong>
                  <span>{{ group.total }} 个</span>
                </div>
                <div v-for="item in group.items" :key="`${group.fruit}-${item.ripeness}`" class="ripeness-row">
                  <span>{{ item.ripeness }}</span>
                  <span>{{ item.count }}</span>
                </div>
              </div>
            </div>
            <el-empty v-else description="暂无熟度数据" />
          </div>
        </article>

        <article class="panel" v-loading="loading">
          <div class="panel-header">
            <div>
              <h2>果径分析</h2>
              <p>控制台第一版按历史记录加权统计有效测量率与平均果径。</p>
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
              <span>平均果径</span>
              <strong>{{ formatMetric(diameterAnalysis.avg_diameter_mm, 'mm', 2) }}</strong>
            </div>
            <div class="metric-card">
              <span>最小 / 最大</span>
              <strong>{{ minMaxDiameterText }}</strong>
            </div>
          </div>

          <div class="diameter-summary">
            <div class="diameter-row">
              <span>果径目标总数</span>
              <strong>{{ diameterAnalysis.total_targets || 0 }}</strong>
            </div>
            <div class="diameter-row">
              <span>有效测量目标数</span>
              <strong>{{ diameterAnalysis.valid_measurements || 0 }}</strong>
            </div>
            <div class="diameter-row">
              <span>平均每次检测目标数</span>
              <strong>{{ formatMetric(summaryCards.avg_targets_per_record, '', 2, '0') }}</strong>
            </div>
          </div>

          <p class="panel-note">
            平均果径按每条记录的平均果径 × 有效测量数量做加权平均，避免单条少量样本对整体统计产生过大偏移。
          </p>
        </article>

        <article class="panel" v-loading="loading">
          <div class="panel-header">
            <div>
              <h2>视频任务概况</h2>
              <p>这里汇总当前时间范围内的视频处理任务状态，并展示最近任务。</p>
            </div>
          </div>

          <div class="metric-grid metric-grid--compact">
            <div class="metric-card">
              <span>总任务数</span>
              <strong>{{ videoTaskSummary.total || 0 }}</strong>
            </div>
            <div class="metric-card">
              <span>处理中</span>
              <strong>{{ videoTaskSummary.processing || 0 }}</strong>
            </div>
            <div class="metric-card">
              <span>已完成</span>
              <strong>{{ videoTaskSummary.completed || 0 }}</strong>
            </div>
            <div class="metric-card">
              <span>失败</span>
              <strong>{{ videoTaskSummary.error || 0 }}</strong>
            </div>
          </div>

          <div v-if="recentVideoTasks.length" class="task-list">
            <div v-for="task in recentVideoTasks" :key="task.task_id" class="task-item">
              <div class="task-item__head">
                <strong>{{ task.original_file_name }}</strong>
                <el-tag :type="videoTaskTagType(task.status)">{{ videoTaskStatusText(task.status) }}</el-tag>
              </div>
              <div class="task-meta">
                <span>进度 {{ task.progress }}%</span>
                <span>更新时间 {{ formatDateTime(task.updated_at) }}</span>
              </div>
              <el-progress :percentage="task.progress || 0" :stroke-width="8" />
            </div>
          </div>
          <el-empty v-else description="暂无视频任务" />
        </article>

        <article class="panel" :class="{ 'panel-loading': systemLoading }" v-loading="systemLoading">
          <div class="panel-header">
            <div>
              <h2>系统状态</h2>
              <p>聚合后端健康检查、双目相机、果径运行时与标定状态。</p>
            </div>
          </div>

          <div class="system-grid">
            <div class="system-card">
              <div class="system-card__head">
                <strong>后端服务</strong>
                <el-tag :type="systemBackendTagType">{{ systemBackendStatus }}</el-tag>
              </div>
              <p>{{ systemStatus.backend_health?.message || '无状态信息' }}</p>
            </div>

            <div class="system-card">
              <div class="system-card__head">
                <strong>相机状态</strong>
                <el-tag :type="cameraTagType">{{ cameraStatusText }}</el-tag>
              </div>
              <p>模式：{{ cameraModeText }}</p>
              <p>最近帧时间：{{ cameraLastFrameText }}</p>
              <p>连续失败次数：{{ systemStatus.camera_status?.consecutive_failures ?? 0 }}</p>
              <p v-if="systemStatus.camera_status?.last_open_error">最近错误：{{ systemStatus.camera_status.last_open_error }}</p>
            </div>

            <div class="system-card">
              <div class="system-card__head">
                <strong>果径运行时</strong>
                <el-tag :type="runtimeTagType">{{ runtimeDeviceText }}</el-tag>
              </div>
              <p>CUDA：{{ booleanText(systemStatus.measure_runtime_status?.cuda_available) }}</p>
              <p>模型加载：{{ booleanText(systemStatus.measure_runtime_status?.model_loaded) }}</p>
              <p>设备设置：{{ systemStatus.measure_runtime_status?.device_setting || '-' }}</p>
            </div>

            <div class="system-card">
              <div class="system-card__head">
                <strong>标定状态</strong>
                <el-tag :type="calibrationTagType">{{ calibrationStatusText }}</el-tag>
              </div>
              <p>最近 Session：{{ systemStatus.calibration_status?.session_id || '暂无' }}</p>
              <p>已采集对数：{{ systemStatus.calibration_status?.pair_count ?? 0 }}</p>
              <p>标定结果：{{ calibrationResultText }}</p>
            </div>
          </div>
        </article>

        <article class="panel">
          <div class="panel-header">
            <div>
              <h2>最近活动</h2>
              <p>显示最近检测历史，并提供常用入口。</p>
            </div>
          </div>

          <div class="quick-actions">
            <button
              v-for="item in quickActions"
              :key="item.path"
              class="quick-action"
              @click="goTo(item.path)"
            >
              <strong>{{ item.label }}</strong>
              <span>{{ item.desc }}</span>
            </button>
          </div>

          <div v-if="recentHistories.length" class="activity-list">
            <div v-for="item in recentHistories" :key="item.id" class="activity-item">
              <div class="activity-item__head">
                <div>
                  <strong>{{ item.detection_type_display }}</strong>
                  <span>{{ formatDateTime(item.created_at) }}</span>
                </div>
                <div class="activity-actions">
                  <el-button size="small" @click="goTo('/history')">查看历史</el-button>
                  <el-button
                    v-if="item.report_file"
                    size="small"
                    type="primary"
                    @click="downloadReport(item.report_file)"
                  >
                    下载报告
                  </el-button>
                </div>
              </div>
              <p>{{ historySummaryText(item) }}</p>
            </div>
          </div>
          <el-empty v-else description="暂无最近活动" />
        </article>
      </section>
    </div>
  </div>
</template>

<script>
import { ElMessage } from 'element-plus'
import { getConsoleOverview, getConsoleRecent, getConsoleSystemStatus } from '@/api/console'

const TYPE_COLORS = {
  image: '#2f6c59',
  video: '#3f8f7b',
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
        rangeType: 'today',
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
        { label: '视频检测', value: 'video' },
        { label: '实时检测', value: 'realtime' },
        { label: '果径测量', value: 'diameter' }
      ],
      quickActions: [
        { path: '/detection/image', label: '图片检测', desc: '上传单张图片并生成结果报告' },
        { path: '/detection/video', label: '视频检测', desc: '提交视频任务并查看处理进度' },
        { path: '/detection/realtime', label: '实时检测', desc: '保存实时识别结果到检测历史' },
        { path: '/camera/config', label: '摄像头配置', desc: '扫描相机、设置单摄/双摄方案并测试拍照下载' },
        { path: '/history', label: '检测历史', desc: '查看详细报告、筛选并下载结果' }
      ],
      typeColors: TYPE_COLORS,
      overview: this.createEmptyOverview(),
      recent: this.createEmptyRecent(),
      systemStatus: this.createEmptySystemStatus()
    }
  },
  computed: {
    typeKeys() {
      return ['image', 'video', 'realtime', 'diameter']
    },
    summaryCards() {
      return this.overview.summary_cards || {}
    },
    trends() {
      return this.overview.trends || this.createEmptyOverview().trends
    },
    analysis() {
      return this.overview.analysis || this.createEmptyOverview().analysis
    },
    diameterAnalysis() {
      return this.overview.diameter_analysis || {}
    },
    videoTaskSummary() {
      return this.overview.video_task_summary || {}
    },
    recentHistories() {
      return this.recent.recent_histories || []
    },
    recentVideoTasks() {
      return this.recent.recent_video_tasks || []
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
          meta: '所有历史记录 summary.total_targets 求和'
        },
        {
          key: 'image_detection_count',
          label: '图片检测次数',
          value: this.formatMetric(this.summaryCards.image_detection_count, '', 0, '0'),
          meta: '生成图片检测报告后计入'
        },
        {
          key: 'video_detection_count',
          label: '视频检测次数',
          value: this.formatMetric(this.summaryCards.video_detection_count, '', 0, '0'),
          meta: '视频任务完成并落库后计入'
        },
        {
          key: 'realtime_detection_count',
          label: '实时检测次数',
          value: this.formatMetric(this.summaryCards.realtime_detection_count, '', 0, '0'),
          meta: '保存实时报告后计入'
        },
        {
          key: 'diameter_detection_count',
          label: '果径测量次数',
          value: this.formatMetric(this.summaryCards.diameter_detection_count, '', 0, '0'),
          meta: '含双目果径测量历史记录'
        },
        {
          key: 'valid_diameter_measurements',
          label: '有效果径测量数',
          value: this.formatMetric(this.summaryCards.valid_diameter_measurements, '', 0, '0'),
          meta: '仅统计果径记录中的有效测量目标'
        },
        {
          key: 'avg_targets_per_record',
          label: '单次平均目标数',
          value: this.formatMetric(this.summaryCards.avg_targets_per_record, '', 2, '0'),
          meta: '总目标数 / 总记录数'
        }
      ]
    },
    fruitRankingTop() {
      return (this.analysis.fruit_ranking || []).slice(0, 5)
    },
    ripenessGroups() {
      const grouped = new Map()
      ;(this.analysis.ripeness_distribution || []).forEach((item) => {
        if (!grouped.has(item.fruit)) {
          grouped.set(item.fruit, {
            fruit: item.fruit,
            total: 0,
            items: []
          })
        }
        const bucket = grouped.get(item.fruit)
        bucket.total += Number(item.count || 0)
        bucket.items.push(item)
      })
      return Array.from(grouped.values())
    },
    detectionTrendChart() {
      return this.buildLineGeometry(this.trends.daily_detection_trend || [], 'count', 0)
    },
    targetTrendChart() {
      return this.buildLineGeometry(this.trends.daily_target_trend || [], 'count', 0)
    },
    diameterTrendChart() {
      return this.buildLineGeometry(this.trends.daily_avg_diameter_trend || [], 'avg_diameter_mm', null)
    },
    typeDonutStyle() {
      const items = (this.analysis.detection_type_distribution || []).filter((item) => Number(item.count) > 0)
      if (!items.length) {
        return { background: 'conic-gradient(#e5ebf3 0 100%)' }
      }

      let current = 0
      const segments = items.map((item) => {
        const next = current + Number(item.percentage || 0)
        const segment = `${this.typeColors[item.type]} ${current}% ${next}%`
        current = next
        return segment
      })

      if (current < 100) {
        segments.push(`#e5ebf3 ${current}% 100%`)
      }

      return {
        background: `conic-gradient(${segments.join(', ')})`
      }
    },
    minMaxDiameterText() {
      const min = this.formatMetric(this.diameterAnalysis.min_diameter_mm, 'mm', 2)
      const max = this.formatMetric(this.diameterAnalysis.max_diameter_mm, 'mm', 2)
      return `${min} / ${max}`
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
        trends: {
          daily_detection_trend: [],
          daily_target_trend: [],
          daily_type_trend: [],
          daily_avg_diameter_trend: []
        },
        analysis: {
          fruit_ranking: [],
          fruit_distribution: [],
          ripeness_distribution: [],
          detection_type_distribution: []
        },
        diameter_analysis: {},
        video_task_summary: {}
      }
    },
    createEmptyRecent() {
      return {
        recent_histories: [],
        recent_video_tasks: []
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
    formatDayLabel(value) {
      if (!value) return ''
      const parts = String(value).split('-')
      return parts.length === 3 ? `${parts[1]}-${parts[2]}` : value
    },
    booleanText(value) {
      return value ? '是' : '否'
    },
    buildLineGeometry(series, key, minOverride = 0) {
      const width = 320
      const height = 150
      const paddingX = 18
      const paddingY = 14
      const numericPoints = series
        .map((item, index) => {
          const numericValue = item[key] === null || item[key] === undefined ? null : Number(item[key])
          return {
            index,
            label: item.date,
            value: Number.isFinite(numericValue) ? numericValue : null
          }
        })
        .filter((item) => item.value !== null)

      if (!numericPoints.length) {
        return {
          max: 0,
          points: '',
          area: '',
          markers: []
        }
      }

      const values = numericPoints.map((item) => item.value)
      const min = minOverride === null ? Math.min(...values) : minOverride
      const max = Math.max(...values, min === 0 ? 1 : min)
      const range = max - min || 1
      const innerWidth = width - paddingX * 2
      const innerHeight = height - paddingY * 2
      const xAt = (index) => (series.length === 1 ? width / 2 : paddingX + (innerWidth * index) / (series.length - 1))
      const yAt = (value) => paddingY + ((max - value) / range) * innerHeight

      const markers = numericPoints.map((item) => ({
        ...item,
        x: xAt(item.index),
        y: yAt(item.value)
      }))

      const points = markers.map((item) => `${item.x},${item.y}`).join(' ')
      const first = markers[0]
      const last = markers[markers.length - 1]
      const area = [
        `M ${first.x} ${height - paddingY}`,
        ...markers.map((item) => `L ${item.x} ${item.y}`),
        `L ${last.x} ${height - paddingY}`,
        'Z'
      ].join(' ')

      return { max, points, area, markers }
    },
    trendPeakText(value, suffix) {
      return value ? `峰值 ${this.formatMetric(value, suffix, suffix === '次' || suffix === '个' ? 0 : 2, '0')}` : '暂无峰值'
    },
    dayTypeTotal(item) {
      return this.typeKeys.reduce((sum, key) => sum + Number(item[key] || 0), 0)
    },
    maxDayTypeTotal() {
      const totals = (this.trends.daily_type_trend || []).map((item) => this.dayTypeTotal(item))
      return Math.max(...totals, 1)
    },
    stackedColumnHeight(item) {
      return (this.dayTypeTotal(item) / this.maxDayTypeTotal()) * 100
    },
    stackSegmentStyle(item, typeKey) {
      const total = this.dayTypeTotal(item)
      const value = Number(item[typeKey] || 0)
      return {
        height: total ? `${(value / total) * 100}%` : '0%',
        backgroundColor: this.typeColors[typeKey]
      }
    },
    fruitShare(count) {
      const maxCount = Math.max(...this.fruitRankingTop.map((item) => Number(item.count || 0)), 1)
      return (Number(count || 0) / maxCount) * 100
    },
    historySummaryText(item) {
      const summary = item.summary || {}
      if (item.detection_type === 'diameter') {
        return `目标 ${summary.total_targets || 0} 个，成功测量 ${summary.valid_measurements || 0} 个，平均果径 ${this.formatMetric(summary.statistics?.avg_diameter_mm ?? summary.statistics?.avg_distance_mm, 'mm', 2)}。`
      }
      const fruitCount = summary.fruit_counts ? Object.keys(summary.fruit_counts).length : 0
      return `识别目标 ${summary.total_targets || 0} 个，水果类别 ${fruitCount} 种。`
    },
    videoTaskTagType(status) {
      if (status === 'completed') return 'success'
      if (status === 'processing') return 'warning'
      if (status === 'error') return 'danger'
      return 'info'
    },
    videoTaskStatusText(status) {
      if (status === 'completed') return '已完成'
      if (status === 'processing') return '处理中'
      if (status === 'error') return '失败'
      return status || '未知'
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
  padding: 20px;
  min-height: 100%;
  background:
    radial-gradient(circle at top left, rgba(39, 112, 89, 0.18), transparent 24%),
    radial-gradient(circle at top right, rgba(244, 163, 64, 0.12), transparent 22%),
    linear-gradient(180deg, #f3f6f4 0%, #ecf2ee 100%);
}

.page-shell {
  max-width: 1460px;
  margin: 0 auto;
  display: grid;
  gap: 18px;
}

.hero,
.filter-card,
.summary-card,
.panel {
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
.subsection-head h3,
.chart-head h3 {
  margin: 0;
}

.hero h1 {
  font-size: 38px;
  line-height: 1.1;
}

.hero-text {
  margin: 14px 0 0;
  max-width: 780px;
  line-height: 1.8;
  color: rgba(244, 251, 247, 0.88);
}

.hero-notes,
.hero-actions,
.filter-row,
.trend-grid,
.type-distribution,
.metric-grid,
.system-grid,
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

.filter-card,
.panel {
  padding: 22px;
}

.filter-row {
  align-items: flex-end;
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
.chart-head span,
.legend-copy span,
.task-meta,
.activity-item p,
.system-card p,
.panel-note {
  color: #5c766c;
}

.filter-label {
  font-size: 13px;
  font-weight: 600;
}

.summary-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
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
  grid-template-columns: minmax(0, 1.45fr) minmax(360px, 0.9fr);
  gap: 18px;
}

.panel-wide {
  grid-column: 1 / -1;
}

.panel-header,
.chart-head,
.subsection-head,
.task-item__head,
.system-card__head,
.activity-item__head,
.ripeness-card__head,
.ranking-copy,
.diameter-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.panel-header {
  margin-bottom: 18px;
  align-items: flex-start;
}

.panel-header p {
  margin: 6px 0 0;
  line-height: 1.7;
}

.trend-grid {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 16px;
}

.trend-grid--secondary {
  margin-top: 16px;
}

.chart-card,
.system-card,
.metric-card,
.quick-action,
.activity-item,
.task-item,
.ripeness-card {
  border-radius: 20px;
  background: #f7faf8;
  border: 1px solid rgba(29, 62, 50, 0.06);
}

.chart-card,
.system-card,
.metric-card,
.activity-item,
.task-item,
.ripeness-card {
  padding: 16px;
}

.chart-head,
.subsection-head {
  margin-bottom: 12px;
}

.line-chart svg {
  width: 100%;
  height: 150px;
}

.grid-lines line {
  stroke: rgba(51, 87, 72, 0.12);
  stroke-width: 1;
}

.chart-line {
  fill: none;
  stroke-width: 3;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.chart-line--primary,
.chart-point--primary {
  stroke: #2f6c59;
  fill: #2f6c59;
}

.chart-line--warm,
.chart-point--warm {
  stroke: #f4a340;
  fill: #f4a340;
}

.chart-line--accent,
.chart-point--accent {
  stroke: #2c6bed;
  fill: #2c6bed;
}

.chart-area {
  fill: rgba(47, 108, 89, 0.1);
}

.chart-area--warm {
  fill: rgba(244, 163, 64, 0.14);
}

.chart-area--accent {
  fill: rgba(44, 107, 237, 0.12);
}

.chart-labels {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(36px, 1fr));
  gap: 8px;
  margin-top: 8px;
  font-size: 12px;
  color: #6a857a;
  text-align: center;
}

.stack-chart {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(52px, 1fr));
  gap: 12px;
  align-items: end;
}

.stack-column {
  display: grid;
  gap: 8px;
  justify-items: center;
}

.stack-value,
.stack-label {
  font-size: 12px;
  color: #6a857a;
}

.stack-track {
  width: 100%;
  height: 180px;
  display: flex;
  align-items: flex-end;
  justify-content: center;
}

.stack-fill {
  width: 28px;
  display: flex;
  flex-direction: column-reverse;
  overflow: hidden;
  border-radius: 999px 999px 10px 10px;
  background: #eaf0ec;
}

.stack-segment {
  width: 100%;
  display: block;
}

.type-distribution {
  align-items: center;
  justify-content: space-between;
}

.type-donut {
  width: 180px;
  height: 180px;
  border-radius: 50%;
  padding: 22px;
  display: grid;
  place-items: center;
}

.type-donut__center {
  width: 100%;
  height: 100%;
  border-radius: 50%;
  background: #ffffff;
  display: grid;
  place-items: center;
  color: #16352b;
  text-align: center;
}

.type-donut__center strong {
  font-size: 30px;
}

.type-donut__center span {
  font-size: 13px;
  color: #678075;
}

.type-legend {
  flex: 1;
  display: grid;
  gap: 10px;
}

.legend-item {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 10px 12px;
  border-radius: 16px;
  background: rgba(255, 255, 255, 0.82);
}

.legend-dot {
  width: 12px;
  height: 12px;
  border-radius: 50%;
}

.legend-copy {
  display: grid;
  gap: 4px;
}

.subsection + .subsection {
  margin-top: 18px;
}

.ranking-list,
.ripeness-groups,
.task-list,
.activity-list {
  display: grid;
  gap: 12px;
}

.ranking-item {
  display: grid;
  gap: 8px;
}

.ranking-bar {
  height: 10px;
  border-radius: 999px;
  background: #e7efea;
  overflow: hidden;
}

.ranking-bar__fill {
  height: 100%;
  display: block;
  border-radius: 999px;
  background: linear-gradient(90deg, #2f6c59 0%, #5d9e86 100%);
}

.ripeness-row,
.task-meta {
  display: flex;
  justify-content: space-between;
  gap: 12px;
}

.metric-grid {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  gap: 12px;
}

.metric-grid--compact {
  margin-bottom: 18px;
}

.metric-card {
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

.diameter-summary {
  display: grid;
  gap: 10px;
  margin-top: 18px;
  padding: 16px;
  border-radius: 18px;
  background: #f7faf8;
}

.diameter-row strong {
  color: #17362d;
}

.panel-note {
  margin: 16px 0 0;
  line-height: 1.8;
}

.system-grid,
.quick-actions {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
}

.system-card p {
  margin: 10px 0 0;
  line-height: 1.7;
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

.activity-item p {
  margin: 12px 0 0;
  line-height: 1.8;
}

.activity-actions {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.panel-loading {
  min-height: 320px;
}

@media (max-width: 1320px) {
  .summary-grid,
  .metric-grid {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .content-grid,
  .system-grid,
  .quick-actions {
    grid-template-columns: 1fr;
  }
}

@media (max-width: 980px) {
  .hero,
  .trend-grid,
  .summary-grid,
  .metric-grid,
  .system-grid,
  .quick-actions {
    grid-template-columns: 1fr;
  }

  .hero {
    padding: 24px 22px;
  }

  .hero-actions {
    justify-content: flex-start;
  }
}

@media (max-width: 768px) {
  .console-page {
    padding: 12px;
  }

  .filter-row,
  .type-distribution,
  .panel-header,
  .activity-item__head,
  .task-item__head,
  .system-card__head {
    flex-direction: column;
    align-items: flex-start;
  }

  .type-donut {
    width: 150px;
    height: 150px;
  }
}
</style>
