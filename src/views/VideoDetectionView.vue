<template>
  <div class="video-processing">
    <div class="container">
      <h1>视频文件水果识别</h1>
      
      <!-- 文件上传区域 -->
      <div class="upload-section">
        <div 
          class="upload-area"
          :class="{ 'drag-over': dragOver }"
          @drop="handleDrop"
          @dragover="handleDragOver"
          @dragleave="dragOver = false"
          @click="triggerFileInput"
        >
          <input
            ref="fileInput"
            type="file"
            accept="video/*"
            @change="handleFileSelect"
            style="display: none"
          />
          <div class="upload-content">
            <i class="upload-icon">📁</i>
            <h3>点击或拖拽视频文件到这里</h3>
            <p>支持 MP4, AVI, MOV 等格式，最大 500MB</p>
          </div>
        </div>
        
        <div v-if="selectedFile" class="file-info">
          <div class="file-details">
            <div class="file-name">
              <strong>📹 {{ selectedFile.name }}</strong>
            </div>
            <div class="file-meta">
              <span>大小: {{ formatFileSize(selectedFile.size) }}</span>
              <span>类型: {{ selectedFile.type || 'video/mp4' }}</span>
            </div>
          </div>
          
          <div class="processing-params">
            <label>
              处理帧率 (FPS):
              <input 
                type="number" 
                v-model.number="processFps" 
                min="1" 
                max="30"
                class="fps-input"
              >
            </label>
            <span class="fps-hint">较低的帧率可以加快处理速度</span>
          </div>
          
          <button 
            @click="startProcessing" 
            :disabled="isProcessing"
            class="btn btn-primary"
          >
            <span v-if="isProcessing" class="loading-spinner"></span>
            {{ isProcessing ? '处理中...' : '开始处理视频' }}
          </button>
        </div>
      </div>

      <!-- 视频预览区域 -->
      <div v-if="originalVideoUrl || processedVideoUrl" class="video-preview-section">
        <h3>视频预览</h3>
        <div class="video-comparison">
          <div class="video-container">
            <h4>原视频</h4>
            <video 
              v-if="originalVideoUrl" 
              :src="originalVideoUrl" 
              controls 
              class="video-player"
              @error="handleVideoError"
            ></video>
            <div v-else class="placeholder">未选择视频</div>
          </div>
          <div class="video-container">
            <h4>处理后视频</h4>
            <video 
              v-if="processedVideoUrl" 
              :src="processedVideoUrl" 
              controls 
              class="video-player"
            ></video>
            <div v-else class="placeholder">等待处理完成</div>
          </div>
        </div>
      </div>

      <!-- 处理进度 - 新增明显的进度条 -->
      <div v-if="currentTask && currentTask.status !== 'completed'" class="progress-section">
        <h3>处理进度</h3>
        <div class="progress-card">
          <div class="progress-info">
            <span class="progress-label">视频处理中</span>
            <span class="progress-percent">{{ currentTask.progress || 0 }}%</span>
          </div>
          <div class="progress-bar-container">
            <div 
              class="progress-bar-fill" 
              :style="{ width: (currentTask.progress || 0) + '%' }"
              :class="{ 'progress-animate': currentTask.progress < 100 }"
            ></div>
          </div>
          <div class="progress-details">
            <span v-if="currentTask.processedFrames && currentTask.totalFrames">
              已处理 {{ currentTask.processedFrames }} / {{ currentTask.totalFrames }} 帧
            </span>
            <span v-if="currentTask.message" class="progress-message">
              {{ currentTask.message }}
            </span>
          </div>
          <div v-if="currentTask.status === 'error'" class="error-message">
            <i>⚠️</i> 处理失败: {{ currentTask.message }}
            <button @click="retryProcessing" class="btn-retry">重试</button>
          </div>
        </div>
      </div>

      <!-- 处理完成后的操作栏 -->
      <div v-if="currentTask && currentTask.status === 'completed'" class="completed-section">
        <div class="action-buttons">
          <button @click="downloadVideo" class="btn btn-success">
            <i>⬇️</i> 下载处理后视频
          </button>
          <button @click="cleanupTask" class="btn btn-secondary">
            <i>🗑️</i> 清理任务
          </button>
        </div>
      </div>

      <!-- 报告展示区域 - 水果种类按次数降序排序 -->
      <div v-if="reportData" class="report-section">
        <h3>📊 检测报告</h3>
        <div class="report-card">
          <div class="report-summary">
            <div class="summary-item">
              <span class="summary-label">总检测目标数（帧级）</span>
              <span class="summary-value">{{ reportData.total_targets }}</span>
            </div>
          </div>
          
          <!-- 水果种类统计 - 按出现次数降序排序 -->
          <div class="report-table-wrapper">
            <h4>🍎 水果种类统计</h4>
            <table class="report-table fruit-table">
              <thead>
                <tr>
                  <th>排名</th>
                  <th>水果种类</th>
                  <th>出现次数</th>
                  <th>占比</th>
                </tr>
              </thead>
              <tbody>
                <tr 
                  v-for="(item, index) in sortedFruitCounts" 
                  :key="item.fruit"
                  :class="{ 'top-row': index === 0 }"
                >
                  <td class="rank">{{ index + 1 }}</td>
                  <td class="fruit-name">
                    <span class="fruit-icon">{{ getFruitIcon(item.fruit) }}</span>
                    {{ item.fruit }}
                  </td>
                  <td class="count">{{ item.count }}</td>
                  <td class="percentage">{{ getPercentage(item.count, reportData.total_targets) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <!-- 成熟度统计 -->
          <div v-if="sortedRipenessData.length > 0" class="report-table-wrapper">
            <h4>🍌 成熟度统计</h4>
            <table class="report-table ripeness-table">
              <thead>
                <tr>
                  <th>水果种类</th>
                  <th>成熟度</th>
                  <th>出现次数</th>
                  <th>占比</th>
                </tr>
              </thead>
              <tbody>
                <tr v-for="item in sortedRipenessData" :key="`${item.fruit}-${item.ripeness}`">
                  <td>{{ item.fruit }}</td>
                  <td>
                    <span :class="getRipenessClass(item.ripeness)">
                      {{ item.ripeness }}
                    </span>
                  </td>
                  <td>{{ item.count }}</td>
                  <td>{{ getPercentage(item.count, getFruitTotal(item.fruit)) }}%</td>
                </tr>
              </tbody>
            </table>
          </div>

          <div class="report-actions">
            <button @click="downloadReport" class="btn btn-success">
              <i>📄</i> 下载报告（JSON）
            </button>
          </div>
        </div>
      </div>

      <!-- 历史任务记录 -->
      <div v-if="taskHistory.length > 0" class="history-section">
        <h3>📋 历史任务</h3>
        <div class="history-list">
          <div 
            v-for="task in taskHistory" 
            :key="task.taskId" 
            class="history-item"
          >
            <div class="history-info">
              <div class="history-name">{{ task.originalFileName }}</div>
              <div class="history-meta">
                <span :class="['status-badge', task.status]">
                  {{ getStatusText(task.status) }}
                </span>
                <span v-if="task.progress" class="history-progress">{{ task.progress }}%</span>
              </div>
            </div>
            <div class="history-actions">
              <button 
                v-if="task.status === 'completed'" 
                @click="downloadHistoryVideo(task.taskId)" 
                class="btn-icon"
                title="下载视频"
              >
                ⬇️
              </button>
              <button 
                @click="removeHistoryTask(task.taskId)" 
                class="btn-icon delete"
                title="删除记录"
              >
                🗑️
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="errorMessage" class="error-message">
        <i>⚠️</i> {{ errorMessage }}
        <button @click="errorMessage = ''" class="close-error">✖</button>
      </div>
    </div>
  </div>
</template>

<script>
import { uploadVideo, getVideoProgress, downloadVideo, cleanupVideoTask } from '@/api/detection'

export default {
  name: 'VideoProcessing',
  data() {
    return {
      selectedFile: null,
      isProcessing: false,
      processFps: 5,
      currentTask: null,
      taskHistory: [],
      errorMessage: '',
      progressInterval: null,
      originalVideoUrl: null,
      processedVideoUrl: null,
      reportData: null,
      dragOver: false
    };
  },
  computed: {
    // 水果种类按出现次数降序排序
    sortedFruitCounts() {
      if (!this.reportData || !this.reportData.fruit_counts) return [];
      const counts = this.reportData.fruit_counts;
      return Object.entries(counts)
        .map(([fruit, count]) => ({ fruit, count }))
        .sort((a, b) => b.count - a.count);
    },
    // 成熟度数据整理并排序
    sortedRipenessData() {
      if (!this.reportData || !this.reportData.ripeness_counts) return [];
      const result = [];
      Object.entries(this.reportData.ripeness_counts).forEach(([fruit, ripenessMap]) => {
        Object.entries(ripenessMap).forEach(([ripeness, count]) => {
          result.push({ fruit, ripeness, count });
        });
      });
      // 按水果名称排序，再按次数降序
      return result.sort((a, b) => {
        if (a.fruit !== b.fruit) return a.fruit.localeCompare(b.fruit);
        return b.count - a.count;
      });
    }
  },
  mounted() {
    this.loadTaskHistory();
  },
  beforeUnmount() {
    this.cleanupProgressPolling();
    if (this.originalVideoUrl) URL.revokeObjectURL(this.originalVideoUrl);
    if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl);
  },
  methods: {
    handleVideoError() {
      this.errorMessage = '视频无法播放，可能是编码格式不支持。您可以尝试下载后使用本地播放器观看。';
    },
    triggerFileInput() {
      this.$refs.fileInput.click();
    },
    handleFileSelect(event) {
      const file = event.target.files[0];
      if (file) {
        this.validateAndSetFile(file);
      }
    },
    handleDrop(event) {
      event.preventDefault();
      this.dragOver = false;
      const files = event.dataTransfer.files;
      if (files.length > 0) {
        this.validateAndSetFile(files[0]);
      }
    },
    handleDragOver(event) {
      event.preventDefault();
      this.dragOver = true;
    },
    validateAndSetFile(file) {
      if (!file.type.startsWith('video/')) {
        this.errorMessage = '请选择视频文件';
        return;
      }
      const maxSize = 500 * 1024 * 1024;
      if (file.size > maxSize) {
        this.errorMessage = '文件大小不能超过500MB';
        return;
      }

      this.selectedFile = file;
      this.errorMessage = '';
      this.currentTask = null;
      this.reportData = null;
      this.processedVideoUrl = null;
      
      if (this.originalVideoUrl) URL.revokeObjectURL(this.originalVideoUrl);
      this.originalVideoUrl = URL.createObjectURL(file);
    },
    
    async startProcessing() {
      if (!this.selectedFile) {
        this.errorMessage = '请先选择视频文件';
        return;
      }

      this.isProcessing = true;
      this.errorMessage = '';

      const formData = new FormData();
      formData.append('file', this.selectedFile);
      formData.append('processFps', this.processFps.toString());

      try {
        const result = await uploadVideo(formData);
        this.currentTask = result;
        this.addToTaskHistory(result);
        this.startProgressPolling(result.taskId);
      } catch (error) {
        console.error('处理视频失败:', error);
        this.errorMessage = `处理失败: ${error.message}`;
        this.isProcessing = false;
      }
    },
    
    startProgressPolling(taskId) {
      this.cleanupProgressPolling();
      this.progressInterval = setInterval(async () => {
        try {
          const task = await getVideoProgress(taskId);
          this.currentTask = task;
          this.updateTaskHistory(task);

          if (task.status === 'completed') {
            this.isProcessing = false;
            this.cleanupProgressPolling();
            await this.fetchProcessedVideo(taskId);
            if (task.report) {
              this.reportData = task.report;
            }
          } else if (task.status === 'error') {
            this.isProcessing = false;
            this.cleanupProgressPolling();
          }
        } catch (error) {
          console.error('获取进度失败:', error);
        }
      }, 2000);
    },
    
    async fetchProcessedVideo(taskId) {
      try {
        const blob = await downloadVideo(taskId);
        if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl);
        this.processedVideoUrl = URL.createObjectURL(blob);
      } catch (error) {
        console.error('获取处理后的视频失败:', error);
        this.errorMessage = '获取处理后的视频失败，请检查服务器日志';
      }
    },
    
    async downloadVideo() {
      if (!this.currentTask || this.currentTask.status !== 'completed') {
        this.errorMessage = '视频尚未处理完成';
        return;
      }

      try {
        const blob = await downloadVideo(this.currentTask.taskId);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `processed_${this.currentTask.originalFileName}`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } catch (error) {
        console.error('下载视频失败:', error);
        this.errorMessage = '下载视频失败';
      }
    },
    
    async downloadHistoryVideo(taskId) {
      try {
        const blob = await downloadVideo(taskId);
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        const task = this.taskHistory.find(t => t.taskId === taskId);
        a.download = `processed_${task?.originalFileName || 'video'}.mp4`;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
      } catch (error) {
        console.error('下载视频失败:', error);
        this.errorMessage = '下载视频失败';
      }
    },
    
    async cleanupTask() {
      if (!this.currentTask) return;

      try {
        await cleanupVideoTask(this.currentTask.taskId);
        this.removeFromTaskHistory(this.currentTask.taskId);
        this.currentTask = null;
        this.reportData = null;
        if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl);
        this.processedVideoUrl = null;
      } catch (error) {
        console.error('清理任务失败:', error);
      }
    },
    
    removeHistoryTask(taskId) {
      this.removeFromTaskHistory(taskId);
      if (this.currentTask?.taskId === taskId) {
        this.currentTask = null;
        this.reportData = null;
        if (this.processedVideoUrl) URL.revokeObjectURL(this.processedVideoUrl);
        this.processedVideoUrl = null;
      }
    },
    
    retryProcessing() {
      if (this.selectedFile) {
        this.startProcessing();
      }
    },
    
    downloadReport() {
      if (!this.reportData) return;
      const reportStr = JSON.stringify(this.reportData, null, 2);
      const blob = new Blob([reportStr], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `video_report_${this.currentTask?.taskId || Date.now()}.json`;
      document.body.appendChild(a);
      a.click();
      URL.revokeObjectURL(url);
      document.body.removeChild(a);
    },
    
    formatFileSize(bytes) {
      if (bytes === 0) return '0 B';
      const k = 1024;
      const sizes = ['B', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },
    
    getPercentage(count, total) {
      if (!total || total === 0) return '0';
      return ((count / total) * 100).toFixed(1);
    },
    
    getFruitTotal(fruit) {
      if (!this.reportData?.fruit_counts) return 0;
      return this.reportData.fruit_counts[fruit] || 0;
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
      };
      return iconMap[fruit] || '🍎';
    },
    
    getRipenessClass(ripeness) {
      if (ripeness.includes('Ripe') || ripeness.includes('熟')) return 'ripeness-ripe';
      if (ripeness.includes('Unripe') || ripeness.includes('生')) return 'ripeness-unripe';
      if (ripeness.includes('Half') || ripeness.includes('半')) return 'ripeness-half';
      return '';
    },
    
    getStatusText(status) {
      const map = {
        processing: '处理中',
        completed: '已完成',
        error: '失败'
      };
      return map[status] || status;
    },
    
    loadTaskHistory() {
      const saved = localStorage.getItem('videoTaskHistory');
      if (saved) {
        try {
          this.taskHistory = JSON.parse(saved);
        } catch (e) {
          console.error('加载历史记录失败', e);
        }
      }
    },
    
    addToTaskHistory(task) {
      const existing = this.taskHistory.find(t => t.taskId === task.taskId);
      if (!existing) {
        this.taskHistory.unshift({
          taskId: task.taskId,
          originalFileName: task.originalFileName,
          status: task.status,
          progress: task.progress,
          timestamp: Date.now()
        });
        this.saveTaskHistory();
      }
    },
    
    updateTaskHistory(updatedTask) {
      const index = this.taskHistory.findIndex(t => t.taskId === updatedTask.taskId);
      if (index !== -1) {
        this.taskHistory[index] = {
          ...this.taskHistory[index],
          status: updatedTask.status,
          progress: updatedTask.progress
        };
        this.saveTaskHistory();
      }
    },
    
    removeFromTaskHistory(taskId) {
      this.taskHistory = this.taskHistory.filter(t => t.taskId !== taskId);
      this.saveTaskHistory();
    },
    
    saveTaskHistory() {
      localStorage.setItem('videoTaskHistory', JSON.stringify(this.taskHistory.slice(0, 10)));
    },
    
    cleanupProgressPolling() {
      if (this.progressInterval) {
        clearInterval(this.progressInterval);
        this.progressInterval = null;
      }
    }
  }
};
</script>

<style scoped>
.video-processing {
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
  font-size: 2em;
}

/* 上传区域 */
.upload-section {
  margin-bottom: 30px;
}

.upload-area {
  border: 3px dashed #dcdfe6;
  border-radius: 16px;
  padding: 60px 20px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #fafafa;
  margin-bottom: 20px;
}

.upload-area:hover {
  border-color: #409eff;
  background-color: #f0f7ff;
}

.upload-area.drag-over {
  border-color: #409eff;
  background-color: #ecf5ff;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 16px;
  display: block;
}

.upload-content h3 {
  margin: 10px 0;
  color: #606266;
}

.upload-content p {
  color: #909399;
  font-size: 14px;
}

.file-info {
  background: #f8f9fa;
  border-radius: 12px;
  padding: 20px;
  margin-top: 20px;
}

.file-details {
  margin-bottom: 20px;
}

.file-name {
  font-size: 16px;
  margin-bottom: 8px;
  word-break: break-all;
}

.file-meta {
  display: flex;
  gap: 20px;
  color: #7f8c8d;
  font-size: 14px;
}

.processing-params {
  margin: 20px 0;
  display: flex;
  align-items: center;
  gap: 20px;
  flex-wrap: wrap;
}

.fps-input {
  width: 80px;
  padding: 8px 12px;
  border: 1px solid #dcdfe6;
  border-radius: 8px;
  margin-left: 10px;
}

.fps-hint {
  color: #909399;
  font-size: 12px;
}

/* 视频预览 */
.video-preview-section {
  margin: 30px 0;
}

.video-comparison {
  display: flex;
  gap: 20px;
  flex-wrap: wrap;
  justify-content: center;
}

.video-container {
  flex: 1;
  min-width: 300px;
  text-align: center;
}

.video-container h4 {
  margin-bottom: 10px;
  color: #495057;
}

.video-player {
  width: 100%;
  max-height: 400px;
  border-radius: 12px;
  box-shadow: 0 4px 12px rgba(0,0,0,0.15);
}

.placeholder {
  width: 100%;
  height: 200px;
  background: linear-gradient(135deg, #f5f7fa 0%, #e9ecef 100%);
  display: flex;
  align-items: center;
  justify-content: center;
  color: #adb5bd;
  border-radius: 12px;
  font-size: 14px;
}

/* 进度条区域 - 明显设计 */
.progress-section {
  margin: 30px 0;
}

.progress-card {
  background: linear-gradient(135deg, #ffffff 0%, #f8f9fa 100%);
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 8px 24px rgba(0,0,0,0.12);
  border: 1px solid #e9ecef;
}

.progress-info {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: 12px;
}

.progress-label {
  font-weight: 600;
  color: #2c3e50;
  font-size: 16px;
}

.progress-percent {
  font-size: 24px;
  font-weight: bold;
  color: #409eff;
}

.progress-bar-container {
  background: #e9ecef;
  border-radius: 20px;
  height: 28px;
  overflow: hidden;
  margin-bottom: 16px;
  box-shadow: inset 0 1px 3px rgba(0,0,0,0.1);
}

.progress-bar-fill {
  background: linear-gradient(90deg, #409eff 0%, #66b1ff 50%, #409eff 100%);
  height: 100%;
  border-radius: 20px;
  transition: width 0.3s ease;
  display: flex;
  align-items: center;
  justify-content: flex-end;
  padding-right: 10px;
  color: white;
  font-weight: bold;
  font-size: 12px;
}

.progress-bar-fill.progress-animate {
  background: linear-gradient(90deg, #409eff, #66b1ff, #409eff);
  background-size: 200% 100%;
  animation: shimmer 1.5s infinite;
}

@keyframes shimmer {
  0% { background-position: 200% 0; }
  100% { background-position: -200% 0; }
}

.progress-details {
  display: flex;
  justify-content: space-between;
  color: #6c757d;
  font-size: 13px;
  flex-wrap: wrap;
  gap: 10px;
}

.progress-message {
  color: #409eff;
}

/* 完成后的操作栏 */
.completed-section {
  margin: 20px 0;
}

.action-buttons {
  display: flex;
  gap: 15px;
  justify-content: center;
  flex-wrap: wrap;
}

/* 报告区域 */
.report-section {
  margin: 30px 0;
}

.report-card {
  background: #fff;
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.08);
  border: 1px solid #e9ecef;
}

.report-summary {
  background: linear-gradient(135deg, #e8f5e9 0%, #c8e6d9 100%);
  border-radius: 16px;
  padding: 20px;
  margin-bottom: 24px;
  text-align: center;
}

.summary-item {
  display: inline-block;
  padding: 8px 24px;
  background: white;
  border-radius: 40px;
  box-shadow: 0 2px 8px rgba(0,0,0,0.05);
}

.summary-label {
  font-weight: 500;
  color: #2c3e50;
  margin-right: 12px;
}

.summary-value {
  font-size: 28px;
  font-weight: bold;
  color: #409eff;
}

.report-table-wrapper {
  margin: 24px 0;
  overflow-x: auto;
}

.report-table-wrapper h4 {
  margin-bottom: 16px;
  color: #2c3e50;
  font-size: 18px;
}

.report-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 1px 3px rgba(0,0,0,0.05);
}

.report-table th,
.report-table td {
  border: 1px solid #e9ecef;
  padding: 12px 16px;
  text-align: left;
}

.report-table th {
  background: #f8f9fa;
  font-weight: 600;
  color: #495057;
}

.fruit-table tbody tr:hover {
  background: #f8f9fa;
}

.fruit-table .top-row {
  background: linear-gradient(90deg, #fff9e6, #fff);
  border-left: 4px solid #ffc107;
}

.rank {
  width: 60px;
  font-weight: 600;
  color: #6c757d;
}

.top-row .rank {
  color: #ffc107;
  font-size: 18px;
}

.fruit-name {
  font-weight: 500;
}

.fruit-icon {
  margin-right: 8px;
  font-size: 16px;
}

.count {
  font-weight: 600;
  color: #409eff;
}

.percentage {
  color: #6c757d;
}

/* 成熟度标签样式 */
.ripeness-ripe {
  color: #28a745;
  font-weight: 500;
}

.ripeness-unripe {
  color: #fd7e14;
  font-weight: 500;
}

.ripeness-half {
  color: #ffc107;
  font-weight: 500;
}

.report-actions {
  margin-top: 24px;
  text-align: center;
}

/* 历史任务 */
.history-section {
  margin-top: 30px;
  border-top: 1px solid #e9ecef;
  padding-top: 20px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  background: #f8f9fa;
  padding: 12px 16px;
  border-radius: 12px;
  transition: all 0.2s;
}

.history-item:hover {
  background: #e9ecef;
}

.history-info {
  flex: 1;
}

.history-name {
  font-weight: 500;
  margin-bottom: 4px;
  word-break: break-all;
}

.history-meta {
  display: flex;
  gap: 12px;
  font-size: 12px;
}

.status-badge {
  padding: 2px 8px;
  border-radius: 20px;
  font-size: 11px;
  font-weight: 500;
}

.status-badge.processing {
  background: #fff3cd;
  color: #856404;
}

.status-badge.completed {
  background: #d4edda;
  color: #155724;
}

.status-badge.error {
  background: #f8d7da;
  color: #721c24;
}

.history-progress {
  color: #6c757d;
}

.history-actions {
  display: flex;
  gap: 8px;
}

.btn-icon {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  padding: 6px;
  border-radius: 8px;
  transition: all 0.2s;
}

.btn-icon:hover {
  background: #dee2e6;
  transform: scale(1.05);
}

.btn-icon.delete:hover {
  background: #f8d7da;
}

/* 按钮样式 */
.btn {
  padding: 12px 24px;
  border: none;
  border-radius: 40px;
  cursor: pointer;
  font-size: 14px;
  font-weight: 500;
  transition: all 0.3s ease;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background: linear-gradient(135deg, #409eff 0%, #66b1ff 100%);
  color: white;
  box-shadow: 0 2px 8px rgba(64,158,255,0.3);
}

.btn-primary:hover:not(:disabled) {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(64,158,255,0.4);
}

.btn-success {
  background: linear-gradient(135deg, #67c23a 0%, #85ce61 100%);
  color: white;
}

.btn-success:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(103,194,58,0.3);
}

.btn-secondary {
  background: #909399;
  color: white;
}

.btn-secondary:hover {
  background: #a6a9ad;
  transform: translateY(-2px);
}

.btn-retry {
  background: #ffc107;
  border: none;
  padding: 4px 12px;
  border-radius: 20px;
  cursor: pointer;
  margin-left: 12px;
  font-size: 12px;
}

.loading-spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

/* 错误信息 */
.error-message {
  background-color: #f8d7da;
  color: #721c24;
  padding: 15px 20px;
  border-radius: 12px;
  border: 1px solid #f5c6cb;
  margin: 20px 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.close-error {
  background: none;
  border: none;
  font-size: 18px;
  cursor: pointer;
  color: #721c24;
  opacity: 0.7;
}

.close-error:hover {
  opacity: 1;
}

/* 响应式 */
@media (max-width: 768px) {
  .video-comparison {
    flex-direction: column;
  }
  
  .btn {
    padding: 10px 20px;
    font-size: 13px;
  }
  
  .report-table th,
  .report-table td {
    padding: 8px 12px;
    font-size: 12px;
  }
  
  .progress-percent {
    font-size: 20px;
  }
  
  .progress-bar-container {
    height: 24px;
  }
}
</style>