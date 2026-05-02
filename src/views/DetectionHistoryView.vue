<template>
  <div class="history-container">
    <div class="container">
      <div class="page-head">
        <div>
          <h1>检测历史</h1>
          <p>查看图片、视频、实时检测和果径测量任务，支持详情回看和报告下载。</p>
        </div>
      </div>

      <div class="toolbar">
        <el-select v-model="detectionType" placeholder="按类型筛选" clearable style="width: 220px" @change="onFilterChange">
          <el-option label="全部" value="" />
          <el-option label="图片检测" value="image" />
          <el-option label="视频检测" value="video" />
          <el-option label="实时检测" value="realtime" />
          <el-option label="果径测量" value="diameter" />
        </el-select>
        <el-button @click="fetchHistory" :loading="loading">刷新</el-button>
      </div>

      <div v-if="loading" class="loading-wrapper">
        <el-skeleton :rows="6" animated />
      </div>

      <el-table v-else :data="historyList" stripe style="width: 100%">
        <el-table-column prop="detection_type_display" label="类型" width="120">
          <template #default="{ row }">
            <el-tag :type="tagType(row.detection_type)">{{ row.detection_type_display }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="title" label="任务标题" min-width="220">
          <template #default="{ row }">{{ row.title || `${row.detection_type_display} #${row.id}` }}</template>
        </el-table-column>

        <el-table-column prop="created_at" label="检测时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>

        <el-table-column prop="summary" label="摘要信息" min-width="260">
          <template #default="{ row }">
            <div class="summary-text">{{ historySummaryText(row) }}</div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="270">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetail(row)">查看详情</el-button>
            <el-button v-if="row.report_file || row.report_url" type="success" size="small" @click="downloadReport(row)">下载报告</el-button>
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
        @current-change="handlePageChange"
        style="margin-top: 20px; justify-content: center"
      />

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
            <el-button v-if="currentDetail.report_file || currentDetail.report_url" type="success" @click="downloadReport(currentDetail)">
              下载报告
            </el-button>
          </div>

          <div class="stat-section" v-if="currentDetail.summary?.fruit_counts && Object.keys(currentDetail.summary.fruit_counts).length">
            <h4>水果统计</h4>
            <el-table :data="sortedFruitCounts" border>
              <el-table-column prop="fruit" label="水果" />
              <el-table-column prop="count" label="数量" width="100" />
            </el-table>
          </div>

          <div class="stat-section" v-if="sortedRipenessData.length > 0">
            <h4>熟度统计</h4>
            <el-table :data="sortedRipenessData" border>
              <el-table-column prop="fruit" label="水果" />
              <el-table-column prop="ripeness" label="熟度" />
              <el-table-column prop="count" label="数量" width="100" />
            </el-table>
          </div>

          <div class="stat-section" v-if="diameterStatistics">
            <h4>果径统计</h4>
            <p>有效测量: {{ currentDetail.summary?.valid_measurements ?? 0 }}</p>
            <p>平均果径: {{ formatNumber(diameterStatistics.avg_diameter_mm) }} mm</p>
            <p>最小果径: {{ formatNumber(diameterStatistics.min_diameter_mm) }} mm</p>
            <p>最大果径: {{ formatNumber(diameterStatistics.max_diameter_mm) }} mm</p>
          </div>

          <div v-if="normalizedDetailItems.length" class="detail-items">
            <article v-for="(item, index) in normalizedDetailItems" :key="`${item.display_name}-${index}`" class="detail-item-card">
              <div class="item-head">
                <div>
                  <strong>{{ item.display_name }}</strong>
                  <span>{{ item.item_type === 'diameter_group' ? '果径图片组' : '普通图片' }}</span>
                </div>
              </div>

              <div class="detail-image-grid">
                <figure v-if="item.originalImageUrl" class="detail-figure">
                  <img :src="item.originalImageUrl" alt="original" class="detail-image" />
                  <figcaption>原图</figcaption>
                </figure>
                <figure v-if="item.rightImageUrl" class="detail-figure">
                  <img :src="item.rightImageUrl" alt="right original" class="detail-image" />
                  <figcaption>右图</figcaption>
                </figure>
                <figure v-if="item.annotatedImageUrl" class="detail-figure">
                  <img :src="item.annotatedImageUrl" alt="annotated" class="detail-image" />
                  <figcaption>检测结果</figcaption>
                </figure>
              </div>

              <el-table :data="item.targets || []" border>
                <el-table-column prop="target_index" label="目标序号" width="90" />
                <el-table-column label="边界框" min-width="150">
                  <template #default="{ row }">[{{ (row.bbox || []).join(', ') }}]</template>
                </el-table-column>
                <el-table-column label="种类" min-width="140">
                  <template #default="{ row }">{{ row.classification?.class || '-' }}</template>
                </el-table-column>
                <el-table-column label="熟度" min-width="180">
                  <template #default="{ row }">{{ row.ripeness?.predicted_class || '-' }}</template>
                </el-table-column>
                <el-table-column label="果径(mm)" width="110">
                  <template #default="{ row }">{{ formatNumber(row.diameter?.distance_mm) }}</template>
                </el-table-column>
                <el-table-column label="状态" min-width="120">
                  <template #default="{ row }">{{ row.diameter?.status || 'ok' }}</template>
                </el-table-column>
              </el-table>
            </article>
          </div>

          <div class="detail-footer">
            <el-button @click="detailVisible = false">关闭窗口</el-button>
          </div>
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import { deleteDetectionHistory, getDetectionHistoryDetail, getDetectionHistoryList } from '@/api/detection'

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

    const formatDateTime = (isoString) => (isoString ? new Date(isoString).toLocaleString('zh-CN') : '-')
    const formatNumber = (value) => (value === null || value === undefined ? '-' : Number(value).toFixed(2))
    const resolveMediaUrl = (path) => {
      if (!path) return ''
      if (path.startsWith('http://') || path.startsWith('https://') || path.startsWith('/media/')) return path
      return `/media/${String(path).replace(/^\/+/, '')}`
    }

    const tagType = (type) => {
      if (type === 'image') return 'primary'
      if (type === 'video') return 'success'
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
        console.error('获取历史记录失败', error)
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
        console.error('获取详情失败', error)
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
        if (historyList.value.length === 1 && currentPage.value > 1) currentPage.value -= 1
        fetchHistory()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除失败', error)
          ElMessage.error('删除失败，请稍后重试')
        }
      }
    }

    const handlePageChange = (page) => {
      currentPage.value = page
      fetchHistory()
    }

    const sortedFruitCounts = computed(() => {
      if (!currentDetail.value?.summary?.fruit_counts) return []
      return Object.entries(currentDetail.value.summary.fruit_counts)
        .map(([fruit, count]) => ({ fruit, count }))
        .sort((a, b) => b.count - a.count)
    })

    const sortedRipenessData = computed(() => {
      if (!currentDetail.value?.summary?.ripeness_counts) return []
      const result = []
      Object.entries(currentDetail.value.summary.ripeness_counts).forEach(([fruit, ripenessMap]) => {
        Object.entries(ripenessMap).forEach(([ripeness, count]) => {
          result.push({ fruit, ripeness, count })
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
      historySummaryText
    }
  }
}
</script>

<style scoped>
.history-container {
  padding: 20px;
  background: #f5f7fa;
  min-height: calc(100vh - 60px);
}

.container {
  max-width: 1320px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

.page-head h1 {
  margin: 0;
  font-size: 24px;
  color: #2c3e50;
}

.page-head p {
  margin: 8px 0 0;
  color: #606266;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin: 24px 0 16px;
}

.summary-text {
  font-size: 14px;
  color: #606266;
  line-height: 1.6;
}

.detail-content {
  display: grid;
  gap: 24px;
}

.detail-summary p,
.stat-section p {
  margin: 0 0 8px;
}

.dialog-actions {
  display: flex;
  justify-content: flex-end;
}

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
  .history-container {
    padding: 12px;
  }

  .toolbar {
    flex-direction: column;
  }
}
</style>
