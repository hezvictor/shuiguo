<template>
  <div class="history-container">
    <div class="container">
      <h1>检测历史</h1>

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
        <el-skeleton :rows="5" animated />
      </div>

      <el-table v-else :data="historyList" stripe style="width: 100%" v-loading="loading">
        <el-table-column prop="detection_type_display" label="检测类型" width="130">
          <template #default="{ row }">
            <el-tag :type="tagType(row.detection_type)">{{ row.detection_type_display }}</el-tag>
          </template>
        </el-table-column>

        <el-table-column prop="created_at" label="检测时间" width="180">
          <template #default="{ row }">{{ formatDateTime(row.created_at) }}</template>
        </el-table-column>

        <el-table-column prop="summary" label="摘要信息">
          <template #default="{ row }">
            <div class="summary-text">
              <template v-if="row.detection_type === 'diameter'">
                目标: {{ row.summary?.total_targets ?? 0 }}
                | 有效测量: {{ row.summary?.valid_measurements ?? 0 }}
                | 平均果径: {{ formatNumber(row.summary?.statistics?.avg_diameter_mm) }} mm
              </template>
              <template v-else>
                目标总数: {{ row.summary?.total_targets ?? 0 }}
                <span v-if="row.summary?.fruit_counts"> | 水果种类: {{ Object.keys(row.summary.fruit_counts).length }}</span>
              </template>
            </div>
          </template>
        </el-table-column>

        <el-table-column label="操作" width="260">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetail(row)">查看详情</el-button>
            <el-button v-if="row.report_file" type="success" size="small" @click="downloadReport(row.report_file)">下载报告</el-button>
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

      <el-dialog v-model="detailVisible" title="检测报告详情" width="80%" :close-on-click-modal="false">
        <div v-if="currentDetail" class="detail-content">
          <div class="detail-summary">
            <p><strong>检测类型：</strong>{{ currentDetail.detection_type_display }}</p>
            <p><strong>检测时间：</strong>{{ formatDateTime(currentDetail.created_at) }}</p>
            <p><strong>目标总数：</strong>{{ currentDetail.summary?.total_targets ?? 0 }}</p>
          </div>

          <div class="stat-section" v-if="currentDetail.detection_type === 'diameter' && currentDetail.summary?.statistics">
            <h4>果径统计</h4>
            <p>有效测量: {{ currentDetail.summary?.valid_measurements ?? 0 }}</p>
            <p>平均果径: {{ formatNumber(currentDetail.summary.statistics.avg_diameter_mm) }} mm</p>
            <p>最小果径: {{ formatNumber(currentDetail.summary.statistics.min_diameter_mm) }} mm</p>
            <p>最大果径: {{ formatNumber(currentDetail.summary.statistics.max_diameter_mm) }} mm</p>
          </div>

          <div class="stat-section" v-if="sortedFruitCounts.length > 0">
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
        </div>
      </el-dialog>
    </div>
  </div>
</template>

<script>
import { computed, onMounted, ref } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'
import request from '@/utils/request'

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

    const formatDateTime = (isoString) => {
      if (!isoString) return ''
      return new Date(isoString).toLocaleString('zh-CN')
    }

    const formatNumber = (v) => (v === null || v === undefined ? '-' : Number(v).toFixed(2))

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

        const res = await request({
          url: '/api/detection/history/',
          method: 'get',
          params
        })
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
      if (row.summary && row.report_file) {
        currentDetail.value = row
        detailVisible.value = true
        return
      }
      try {
        const res = await request({
          url: `/api/detection/history/${row.id}/`,
          method: 'get'
        })
        currentDetail.value = res
        detailVisible.value = true
      } catch (error) {
        console.error('获取详情失败', error)
        ElMessage.error('获取详情失败')
      }
    }

    const downloadReport = (filePath) => {
      if (!filePath) {
        ElMessage.warning('该记录没有关联的报告文件')
        return
      }
      const url = `/media/${filePath}`
      const a = document.createElement('a')
      a.href = url
      a.download = filePath.split('/').pop()
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

        await request({
          url: `/api/detection/history/${row.id}/`,
          method: 'delete'
        })

        ElMessage.success('删除成功')
        if (historyList.value.length === 1 && currentPage.value > 1) currentPage.value--
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
      const counts = currentDetail.value.summary.fruit_counts
      return Object.entries(counts)
        .map(([fruit, count]) => ({ fruit, count }))
        .sort((a, b) => b.count - a.count)
    })

    const sortedRipenessData = computed(() => {
      if (!currentDetail.value?.summary?.ripeness_counts) return []
      const result = []
      const ripeness = currentDetail.value.summary.ripeness_counts
      Object.entries(ripeness).forEach(([fruit, ripes]) => {
        Object.entries(ripes).forEach(([ripenessName, count]) => {
          result.push({ fruit, ripeness: ripenessName, count })
        })
      })
      return result.sort((a, b) => {
        if (a.fruit !== b.fruit) return a.fruit.localeCompare(b.fruit)
        return b.count - a.count
      })
    })

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
      sortedRipenessData
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
  max-width: 1200px;
  margin: 0 auto;
  background: white;
  border-radius: 16px;
  padding: 24px;
  box-shadow: 0 2px 12px rgba(0, 0, 0, 0.08);
}

h1 {
  margin-top: 0;
  margin-bottom: 24px;
  font-size: 24px;
  color: #2c3e50;
}

.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
}

.summary-text {
  font-size: 14px;
  color: #606266;
}

.detail-content {
  padding: 8px;
}

.detail-summary {
  margin-bottom: 24px;
}

.stat-section {
  margin-top: 24px;
}

.stat-section h4 {
  margin-bottom: 12px;
  font-size: 16px;
  color: #2c3e50;
}

.loading-wrapper {
  padding: 40px 0;
}
</style>
