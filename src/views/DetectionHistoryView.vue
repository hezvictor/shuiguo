<template>
  <div class="history-page">
    <section class="panel page-head">
      <div>
        <h1>检测历史</h1>
        <p>查看图片检测、实时检测和果径测量结果，支持详情查看、报告下载和记录删除。</p>
      </div>
      <div class="toolbar">
        <el-select v-model="detectionType" clearable placeholder="按类型筛选" style="width: 180px" @change="onFilterChange">
          <el-option label="全部" value="" />
          <el-option label="图片检测" value="image" />
          <el-option label="实时检测" value="realtime" />
          <el-option label="果径测量" value="diameter" />
        </el-select>
        <el-button :loading="loading" @click="fetchHistory">刷新</el-button>
      </div>
    </section>

    <section class="panel">
      <div v-if="loading" class="loading-wrapper">
        <el-skeleton :rows="6" animated />
      </div>

      <el-table v-else :data="historyList" stripe>
        <el-table-column prop="detection_type_display" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="tagType(row.detection_type)">{{ row.detection_type_display }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="title" label="任务标题" min-width="220">
          <template #default="{ row }">
            {{ row.title || `${row.detection_type_display} #${row.id}` }}
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="检测时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>

        <el-table-column prop="summary" label="摘要" min-width="260">
          <template #default="{ row }">
            <div class="summary-text">{{ historySummaryText(row) }}</div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="270">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetail(row)">查看详情</el-button>
            <el-button
              v-if="row.report_file || row.report_url"
              type="success"
              size="small"
              @click="downloadReport(row)"
            >
              下载报告
            </el-button>
            <el-button type="danger" size="small" @click="deleteHistory(row)">删除</el-button>
          </template>
        </el-table-column>
      </el-table>

      <el-pagination
        v-if="total > 0"
        background
        layout="prev, pager, next"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        class="pagination"
        @current-change="handlePageChange"
      />
    </section>

    <el-dialog v-model="detailVisible" title="检测详情" width="88%" :close-on-click-modal="false">
      <div v-if="currentDetail" class="detail-content">
        <div class="detail-summary">
          <p><strong>检测类型：</strong>{{ currentDetail.detection_type_display }}</p>
          <p><strong>任务标题：</strong>{{ currentDetail.title || `${currentDetail.detection_type_display} #${currentDetail.id}` }}</p>
          <p><strong>检测时间：</strong>{{ formatDateTime(currentDetail.created_at) }}</p>
          <p><strong>状态：</strong>{{ currentDetail.status_display || currentDetail.status || 'completed' }}</p>
          <p><strong>目标总数：</strong>{{ currentDetail.summary?.total_targets ?? 0 }}</p>
        </div>

        <div class="dialog-actions">
          <el-button
            v-if="currentDetail.report_file || currentDetail.report_url"
            type="success"
            @click="downloadReport(currentDetail)"
          >
            下载报告
          </el-button>
        </div>

        <div v-if="sortedFruitCounts.length" class="stat-section">
          <h4>水果统计</h4>
          <el-table :data="sortedFruitCounts" border>
            <el-table-column prop="fruit" label="水果" />
            <el-table-column prop="count" label="数量" width="100" />
          </el-table>
        </div>

        <div v-if="sortedRipenessData.length" class="stat-section">
          <h4>熟度统计</h4>
          <el-table :data="sortedRipenessData" border>
            <el-table-column prop="fruit" label="水果" />
            <el-table-column prop="ripeness" label="熟度" />
            <el-table-column prop="count" label="数量" width="100" />
          </el-table>
        </div>

        <div v-if="diameterStatistics" class="stat-section">
          <h4>果径统计</h4>
          <p>有效测量：{{ currentDetail.summary?.valid_measurements ?? 0 }}</p>
          <p>横向有效数：{{ validMeasurementsByAxis.horizontal }}</p>
          <p>竖向有效数：{{ validMeasurementsByAxis.vertical }}</p>
          <p>横向平均果径：{{ formatNumber(diameterStatistics.horizontal?.avg_diameter_mm) }} mm</p>
          <p>横向最小果径：{{ formatNumber(diameterStatistics.horizontal?.min_diameter_mm) }} mm</p>
          <p>横向最大果径：{{ formatNumber(diameterStatistics.horizontal?.max_diameter_mm) }} mm</p>
          <p>竖向平均果径：{{ formatNumber(diameterStatistics.vertical?.avg_diameter_mm) }} mm</p>
          <p>竖向最小果径：{{ formatNumber(diameterStatistics.vertical?.min_diameter_mm) }} mm</p>
          <p>竖向最大果径：{{ formatNumber(diameterStatistics.vertical?.max_diameter_mm) }} mm</p>
        </div>

        <div v-if="detailOperations.length" class="stat-section">
          <h4>执行参数</h4>
          <p v-for="entry in detailOperations" :key="`op-${entry.key}`">
            <strong>{{ entry.label }}：</strong>{{ entry.value }}
          </p>
        </div>

        <div v-if="detailContextRows.length" class="stat-section">
          <h4>会话信息</h4>
          <p v-for="entry in detailContextRows" :key="`ctx-${entry.key}`">
            <strong>{{ entry.label }}：</strong>{{ entry.value }}
          </p>
        </div>

        <div v-if="normalizedDetailItems.length" class="detail-items">
          <article
            v-for="(item, index) in normalizedDetailItems"
            :key="`${item.display_name}-${index}`"
            class="detail-item-card"
          >
            <div class="item-head">
              <div>
                <strong>{{ item.display_name }}</strong>
                <span>{{ itemTypeText(item) }}</span>
              </div>
            </div>

            <p class="summary-text">{{ itemSummaryText(item) }}</p>

            <div class="detail-image-grid">
              <figure v-if="item.originalImageUrl" class="detail-figure">
                <img :src="item.originalImageUrl" alt="original" class="detail-image" @click="openImagePreview(item.originalImageUrl, '原图')" />
                <figcaption>原图</figcaption>
              </figure>
              <figure v-if="item.rightImageUrl" class="detail-figure">
                <img :src="item.rightImageUrl" alt="right original" class="detail-image" @click="openImagePreview(item.rightImageUrl, '右图')" />
                <figcaption>右图</figcaption>
              </figure>
              <figure v-if="item.annotatedImageUrl" class="detail-figure">
                <img :src="item.annotatedImageUrl" alt="annotated" class="detail-image" @click="openImagePreview(item.annotatedImageUrl, '检测结果图')" />
                <figcaption>检测结果</figcaption>
              </figure>
            </div>

            <el-table v-if="itemHasTargets(item)" :data="item.targets || []" border>
              <el-table-column prop="target_index" label="目标序号" width="90" />
              <el-table-column label="边界框" min-width="150">
                <template #default="{ row }">[{{ (row.bbox || []).join(', ') }}]</template>
              </el-table-column>
              <el-table-column label="种类" min-width="140">
                <template #default="{ row }">{{ translateFruitLabel(row.classification?.class) }}</template>
              </el-table-column>
              <el-table-column label="熟度" min-width="180">
                <template #default="{ row }">{{ translateRipenessLabel(row.ripeness?.predicted_class) }}</template>
              </el-table-column>
              <el-table-column label="横向果径(mm)" width="130">
                <template #default="{ row }">{{ formatNumber(getAxisDistance(row, 'horizontal')) }}</template>
              </el-table-column>
              <el-table-column label="横向状态" min-width="120">
                <template #default="{ row }">{{ getAxisStatus(row, 'horizontal') }}</template>
              </el-table-column>
              <el-table-column label="竖向果径(mm)" width="130">
                <template #default="{ row }">{{ formatNumber(getAxisDistance(row, 'vertical')) }}</template>
              </el-table-column>
              <el-table-column label="竖向状态" min-width="120">
                <template #default="{ row }">{{ getAxisStatus(row, 'vertical') }}</template>
              </el-table-column>
            </el-table>
          </article>
        </div>

        <div class="detail-footer">
          <el-button @click="detailVisible = false">关闭窗口</el-button>
        </div>
      </div>
    </el-dialog>

    <el-dialog
      v-model="imagePreviewVisible"
      :title="previewImageTitle"
      width="90%"
      top="5vh"
      append-to-body
      destroy-on-close
      class="image-preview-dialog"
    >
      <div class="image-preview-wrapper">
        <img v-if="previewImageUrl" :src="previewImageUrl" :alt="previewImageTitle" class="image-preview-full" />
      </div>
    </el-dialog>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteDetectionHistory, getDetectionHistoryDetail, getDetectionHistoryList } from '@/api/detection'
import { translateFruitLabel, translateRipenessLabel } from '@/utils/labelMap'

export default {
  name: 'DetectionHistoryView',
  setup() {
    const loading = ref(false)
    const historyList = ref([])
    const total = ref(0)
    const currentPage = ref(1)
    const pageSize = ref(10)
    const detailVisible = ref(false)
    const currentDetail = ref(null)
    const detectionType = ref('')
    const imagePreviewVisible = ref(false)
    const previewImageUrl = ref('')
    const previewImageTitle = ref('')

    const formatDateTime = (isoString) => (isoString ? new Date(isoString).toLocaleString('zh-CN') : '-')
    const formatNumber = (value) => (value === null || value === undefined ? '-' : Number(value).toFixed(2))
    const resolveMediaUrl = (path) => {
      if (!path) return ''
      if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/media/')) return path
      return `/media/${String(path).replace(/^\/+/, '')}`
    }

    const tagType = (type) => {
      if (type === 'image') return 'primary'
      if (type === 'realtime') return 'warning'
      if (type === 'diameter') return 'info'
      return ''
    }

    const fetchHistory = async () => {
      loading.value = true
      try {
        const params = {
          page: currentPage.value,
          page_size: pageSize.value
        }
        if (detectionType.value) params.detection_type = detectionType.value
        const res = await getDetectionHistoryList(params)
        historyList.value = res.results || res
        total.value = res.count || historyList.value.length
      } catch (error) {
        console.error('fetch history failed', error)
        ElMessage.error('获取历史记录失败')
      } finally {
        loading.value = false
      }
    }

    const onFilterChange = () => {
      currentPage.value = 1
      fetchHistory()
    }

    const viewDetail = async (row) => {
      try {
        currentDetail.value = await getDetectionHistoryDetail(row.id)
        detailVisible.value = true
      } catch (error) {
        console.error('fetch detail failed', error)
        ElMessage.error('获取详情失败')
      }
    }

    const downloadReport = (row) => {
      const url = row.report_url || resolveMediaUrl(row.report_file)
      if (!url) {
        ElMessage.warning('该记录没有关联的报告文件')
        return
      }
      const a = document.createElement('a')
      a.href = url
      a.download = (row.report_file || 'report').split('/').pop()
      document.body.appendChild(a)
      a.click()
      document.body.removeChild(a)
    }

    const deleteHistory = async (row) => {
      try {
        await ElMessageBox.confirm(`确定要删除 ${row.detection_type_display} 记录吗？`, '删除确认', {
          confirmButtonText: '确定',
          cancelButtonText: '取消',
          type: 'warning'
        })
        await deleteDetectionHistory(row.id)
        ElMessage.success('删除成功')
        if (historyList.value.length === 1 && currentPage.value > 1) {
          currentPage.value -= 1
        }
        fetchHistory()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('delete history failed', error)
          ElMessage.error('删除失败，请稍后重试')
        }
      }
    }

    const handlePageChange = (page) => {
      currentPage.value = page
      fetchHistory()
    }

    const openImagePreview = (url, title = '图片预览') => {
      if (!url) return
      previewImageUrl.value = url
      previewImageTitle.value = title
      imagePreviewVisible.value = true
    }

    const sortedFruitCounts = computed(() => {
      if (!currentDetail.value?.summary?.fruit_counts) return []
      return Object.entries(currentDetail.value.summary.fruit_counts)
        .map(([fruit, count]) => ({ fruit: translateFruitLabel(fruit), count }))
        .sort((a, b) => b.count - a.count)
    })

    const sortedRipenessData = computed(() => {
      if (!currentDetail.value?.summary?.ripeness_counts) return []
      const result = []
      Object.entries(currentDetail.value.summary.ripeness_counts).forEach(([fruit, ripenessMap]) => {
        Object.entries(ripenessMap).forEach(([ripeness, count]) => {
          result.push({ fruit: translateFruitLabel(fruit), ripeness: translateRipenessLabel(ripeness), count })
        })
      })
      return result
    })

    const normalizedDetailItems = computed(() => {
      const items = currentDetail.value?.detail_data?.items || []
      return items.map((item) => ({
        ...item,
        originalImageUrl: resolveMediaUrl(item.original_image),
        rightImageUrl: resolveMediaUrl(item.right_image),
        annotatedImageUrl: resolveMediaUrl(item.annotated_image)
      }))
    })

    const diameterStatistics = computed(() => {
      const summary = currentDetail.value?.summary || {}
      return summary.diameter_statistics || summary.statistics || null
    })

    const validMeasurementsByAxis = computed(() => {
      const summary = currentDetail.value?.summary || {}
      return summary.valid_measurements_by_axis || { horizontal: 0, vertical: 0 }
    })

    const getAxis = (row, axisName) => row?.diameter?.diameter_axes?.[axisName] || null
    const getAxisDistance = (row, axisName) => {
      const axis = getAxis(row, axisName)
      if (!axis || axis.distance_mm === null || axis.distance_mm === undefined) return null
      return Number(axis.distance_mm)
    }
    const getAxisStatus = (row, axisName) => {
      const axis = getAxis(row, axisName)
      if (!axis) return '-'
      return axis.status || 'ok'
    }

    const detailOperations = computed(() => {
      const operations = currentDetail.value?.detail_data?.operations || {}
      return Object.entries(operations)
        .filter(([, value]) => value !== null && value !== undefined && value !== '')
        .map(([key, value]) => ({
          key,
          label: key,
          value: typeof value === 'object' ? JSON.stringify(value) : String(value)
        }))
    })

    const detailContextRows = computed(() => {
      const context = currentDetail.value?.detail_data?.context || {}
      return Object.entries(context)
        .filter(([, value]) => value !== null && value !== undefined && value !== '')
        .map(([key, value]) => ({
          key,
          label: key,
          value: typeof value === 'object' ? JSON.stringify(value) : String(value)
        }))
    })

    const itemTypeText = (item) => {
      const type = item?.item_type || ''
      if (type === 'diameter_group' || type === 'camera_diameter' || type === 'realtime_dual') return '果径结果'
      if (type === 'realtime_single') return '实时单摄结果'
      if (type === 'image') return '图片检测结果'
      return '检测结果'
    }

    const itemHasTargets = (item) => Array.isArray(item?.targets) && item.targets.length > 0

    const itemSummaryText = (item) => {
      const summary = item?.summary || {}
      if (summary.valid_measurements) {
        return `目标 ${summary.total_targets || 0} 个，有效测量 ${summary.valid_measurements || 0} 个`
      }
      return `目标 ${summary.total_targets || 0} 个`
    }

    const historySummaryText = (item) => {
      const summary = item.summary || {}
      if (item.detection_type === 'diameter') {
        return `目标 ${summary.total_targets || 0} 个，有效测量 ${summary.valid_measurements || 0} 个`
      }
      if (summary.valid_measurements) {
        return `输入 ${summary.input_count || item.input_count || 0} 项，目标 ${summary.total_targets || 0} 个，有效果径 ${summary.valid_measurements} 个`
      }
      return `输入 ${summary.input_count || item.input_count || 0} 项，目标 ${summary.total_targets || 0} 个`
    }

    onMounted(fetchHistory)

    return {
      loading,
      historyList,
      total,
      currentPage,
      pageSize,
      detailVisible,
      currentDetail,
      detectionType,
      imagePreviewVisible,
      previewImageUrl,
      previewImageTitle,
      formatDateTime,
      formatNumber,
      tagType,
      fetchHistory,
      onFilterChange,
      viewDetail,
      downloadReport,
      deleteHistory,
      handlePageChange,
      sortedFruitCounts,
      sortedRipenessData,
      normalizedDetailItems,
      diameterStatistics,
      validMeasurementsByAxis,
      detailOperations,
      detailContextRows,
      itemTypeText,
      itemHasTargets,
      itemSummaryText,
      historySummaryText,
      getAxisDistance,
      getAxisStatus,
      openImagePreview,
      translateFruitLabel,
      translateRipenessLabel
    }
  }
}
</script>

<style scoped>
.history-page {
  display: grid;
  gap: 18px;
  padding: 20px;
}

.panel {
  background: #fff;
  border-radius: 18px;
  box-shadow: 0 12px 30px rgba(24, 53, 43, 0.08);
  padding: 22px;
}

.page-head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  align-items: flex-start;
}

.page-head h1 {
  margin: 0;
  font-size: 24px;
  color: #1d4032;
}

.page-head p {
  margin: 8px 0 0;
  color: #60796d;
}

.toolbar {
  display: flex;
  gap: 12px;
  flex-wrap: wrap;
}

.summary-text {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.pagination {
  margin-top: 20px;
  justify-content: center;
}

.detail-content {
  display: grid;
  gap: 24px;
}

.detail-summary p,
.stat-section p {
  margin: 0 0 8px;
}

.dialog-actions,
.detail-footer {
  display: flex;
  justify-content: flex-end;
}

.stat-section h4 {
  margin: 0 0 12px;
  font-size: 16px;
  color: #2c3e50;
}

.detail-items {
  display: grid;
  gap: 20px;
}

.detail-item-card {
  padding: 18px;
  border-radius: 16px;
  background: #f8fbf9;
  border: 1px solid #e6efeb;
}

.item-head {
  margin-bottom: 14px;
}

.item-head strong {
  display: block;
  color: #18352b;
}

.item-head span {
  color: #6b8579;
  font-size: 13px;
}

.detail-image-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
  gap: 14px;
  margin-bottom: 18px;
}

.detail-figure {
  margin: 0;
}

.detail-image {
  width: 100%;
  aspect-ratio: 4 / 3;
  object-fit: cover;
  border-radius: 12px;
  cursor: zoom-in;
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.detail-image:hover {
  transform: translateY(-2px);
  box-shadow: 0 12px 24px rgba(24, 53, 43, 0.16);
}

.image-preview-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  max-height: 78vh;
  overflow: auto;
}

.image-preview-full {
  display: block;
  max-width: 100%;
  max-height: 78vh;
  width: auto;
  height: auto;
  border-radius: 12px;
  object-fit: contain;
}

.detail-figure figcaption {
  margin-top: 8px;
  text-align: center;
  color: #557064;
}

.loading-wrapper {
  padding: 40px 0;
}

@media (max-width: 768px) {
  .history-page {
    padding: 12px;
  }

  .page-head {
    flex-direction: column;
  }

  .toolbar {
    width: 100%;
  }
}
</style>
