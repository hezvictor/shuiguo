<template>
  <div class="history-container">
    <div class="container">
      <h1>检测历史</h1>

      <!-- 加载状态 -->
      <div v-if="loading" class="loading-wrapper">
        <el-skeleton :rows="5" animated />
      </div>

      <!-- 历史记录表格 -->
      <el-table
        v-else
        :data="historyList"
        stripe
        style="width: 100%"
        v-loading="loading"
      >
        <el-table-column prop="detection_type_display" label="检测类型" width="100">
          <template #default="{ row }">
            <el-tag :type="row.detection_type === 'image' ? 'primary' : 'success'">
              {{ row.detection_type_display }}
            </el-tag>
          </template>
        </el-table-column>
        <el-table-column prop="created_at" label="检测时间" width="180">
          <template #default="{ row }">
            {{ formatDateTime(row.created_at) }}
          </template>
        </el-table-column>
        <el-table-column prop="summary" label="摘要信息">
          <template #default="{ row }">
            <div class="summary-text">
              目标总数: {{ row.summary.total_targets || 0 }}
              <span v-if="row.summary.fruit_counts">
                | 水果种类: {{ Object.keys(row.summary.fruit_counts).length }}
              </span>
            </div>
          </template>
        </el-table-column>
        <el-table-column label="操作" width="250">
          <template #default="{ row }">
            <el-button type="primary" size="small" @click="viewDetail(row)">
              查看详情
            </el-button>
            <el-button
              v-if="row.report_file"
              type="success"
              size="small"
              @click="downloadReport(row.report_file)"
            >
              下载报告
            </el-button>
            <el-button
              type="danger"
              size="small"
              @click="deleteHistory(row)"
            >
              删除
            </el-button>
          </template>
        </el-table-column>
      </el-table>

      <!-- 分页 -->
      <el-pagination
        v-if="total > 0"
        background
        layout="prev, pager, next"
        :total="total"
        :current-page="currentPage"
        :page-size="pageSize"
        @current-change="handlePageChange"
        style="margin-top: 20px; justify-content: center;"
      />

      <!-- 详情弹窗（保持不变） -->
      <el-dialog
        v-model="detailVisible"
        title="检测报告详情"
        width="80%"
        :close-on-click-modal="false"
      >
        <!-- 详情内容保持不变 -->
      </el-dialog>
    </div>
  </div>
</template>

<script>
import { ref, onMounted, computed } from 'vue'
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

    // 格式化时间
    const formatDateTime = (isoString) => {
      if (!isoString) return ''
      const date = new Date(isoString)
      return date.toLocaleString('zh-CN')
    }

    // 获取历史列表
    const fetchHistory = async () => {
      loading.value = true
      try {
        const res = await request({
          url: '/api/detection/history/',
          method: 'get',
          params: {
            page: currentPage.value,
            page_size: pageSize.value
          }
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

    // 查看详情
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

    // 下载报告文件
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

    // 删除历史记录
    const deleteHistory = async (row) => {
      try {
        await ElMessageBox.confirm(
          `确定要删除 ${row.detection_type_display} 记录吗？`,
          '删除确认',
          {
            confirmButtonText: '确定',
            cancelButtonText: '取消',
            type: 'warning',
          }
        )
        await request({
          url: `/api/detection/history/${row.id}/`,
          method: 'delete'
        })
        ElMessage.success('删除成功')
        // 如果删除后当前页没有数据且不是第一页，则跳转到上一页
        if (historyList.value.length === 1 && currentPage.value > 1) {
          currentPage.value--
        }
        fetchHistory()
      } catch (error) {
        if (error !== 'cancel') {
          console.error('删除失败', error)
          ElMessage.error('删除失败，请稍后重试')
        }
      }
    }

    // 分页切换
    const handlePageChange = (page) => {
      currentPage.value = page
      fetchHistory()
    }

    // 计算水果统计表格数据
    const sortedFruitCounts = computed(() => {
      if (!currentDetail.value?.summary?.fruit_counts) return []
      const counts = currentDetail.value.summary.fruit_counts
      return Object.entries(counts)
        .map(([fruit, count]) => ({ fruit, count }))
        .sort((a, b) => b.count - a.count)
    })

    // 计算成熟度统计数据
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

    onMounted(() => {
      fetchHistory()
    })

    return {
      loading,
      historyList,
      total,
      currentPage,
      pageSize,
      detailVisible,
      currentDetail,
      formatDateTime,
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

.dialog-footer {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
}
</style>