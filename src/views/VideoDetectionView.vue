<template>
  <div class="video-processing">
    <div class="container">
      <h1>视频文件水果识别</h1>
      
      <!-- 文件上传区域 -->
      <div class="upload-section">
        <div 
          class="upload-area"
          @drop="handleDrop"
          @dragover="handleDragOver"
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
            <p>支持 MP4, AVI, MOV 等格式</p>
          </div>
        </div>
        
        <!-- 文件信息 -->
        <div v-if="selectedFile" class="file-info">
          <h4>已选择文件:</h4>
          <p><strong>文件名:</strong> {{ selectedFile.name }}</p>
          <p><strong>大小:</strong> {{ formatFileSize(selectedFile.size) }}</p>
          <p><strong>类型:</strong> {{ selectedFile.type }}</p>
          
          <!-- 处理参数 -->
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
            <small>较低的帧率可以加快处理速度</small>
          </div>
          
          <button 
            @click="startProcessing" 
            :disabled="isProcessing"
            class="btn btn-primary"
          >
            {{ isProcessing ? '处理中...' : '开始处理视频' }}
          </button>
        </div>
      </div>

      <!-- 处理进度 -->
      <div v-if="currentTask" class="progress-section">
        <h3>处理进度</h3>
        
        <div class="progress-card">
          <div class="progress-header">
            <span class="task-id">任务ID: {{ currentTask.taskId }}</span>
            <span :class="['status-badge', currentTask.status]">
              {{ getStatusText(currentTask.status) }}
            </span>
          </div>
          
          <div class="progress-details">
            <div class="progress-row">
              <span>进度:</span>
              <div class="progress-bar-container">
                <div 
                  class="progress-bar" 
                  :style="{ width: (currentTask.progress || 0) + '%' }"
                ></div>
                <span class="progress-text">{{ currentTask.progress || 0 }}%</span>
              </div>
            </div>
            
            <div class="progress-row">
              <span>处理帧数:</span>
              <span>{{ currentTask.processedFrames || 0 }} / {{ currentTask.totalFrames || '?' }}</span>
            </div>
            
            <div class="progress-row">
              <span>视频信息:</span>
              <span>
                {{ currentTask.videoWidth || '?' }}x{{ currentTask.videoHeight || '?' }} 
                @ {{ currentTask.frameRate || '?' }} FPS
              </span>
            </div>
            
            <div class="progress-row">
              <span>状态信息:</span>
              <span>{{ currentTask.message || '等待开始...' }}</span>
            </div>
          </div>

          <!-- 操作按钮 -->
          <div class="action-buttons" v-if="currentTask.status === 'completed'">
            <button @click="downloadVideo" class="btn btn-success">
              📥 下载处理后的视频
            </button>
            <button @click="cleanupTask" class="btn btn-secondary">
              清理任务
            </button>
          </div>
          
          <div class="action-buttons" v-else-if="currentTask.status === 'error'">
            <button @click="retryProcessing" class="btn btn-warning">
              🔄 重新尝试
            </button>
            <button @click="cleanupTask" class="btn btn-secondary">
              清理任务
            </button>
          </div>
        </div>
      </div>

      <!-- 处理历史 -->
      <div v-if="taskHistory.length > 0" class="history-section">
        <h3>处理历史</h3>
        <div class="history-list">
          <div 
            v-for="task in taskHistory" 
            :key="task.taskId"
            class="history-item"
          >
            <div class="history-info">
              <strong>{{ task.originalFileName }}</strong>
              <span class="history-status" :class="task.status">
                {{ getStatusText(task.status) }}
              </span>
            </div>
            <div class="history-actions">
              <button 
                v-if="task.status === 'completed'"
                @click="downloadHistoryVideo(task.taskId)"
                class="btn btn-sm btn-success"
              >
                下载
              </button>
              <button 
                @click="removeHistoryTask(task.taskId)"
                class="btn btn-sm btn-secondary"
              >
                删除
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>
    </div>
  </div>
</template>

<script>
// 导入封装的API函数
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
      progressInterval: null
    };
  },
  mounted() {
    // 加载历史任务
    this.loadTaskHistory();
  },
  beforeUnmount() {
    this.cleanupProgressPolling();
  },
  methods: {
    // 触发文件选择
    triggerFileInput() {
      this.$refs.fileInput.click();
    },

    // 处理文件选择
    handleFileSelect(event) {
      const file = event.target.files[0];
      if (file) {
        this.validateAndSetFile(file);
      }
    },

    // 处理拖拽放置
    handleDrop(event) {
      event.preventDefault();
      const files = event.dataTransfer.files;
      if (files.length > 0) {
        this.validateAndSetFile(files[0]);
      }
    },

    // 处理拖拽悬停
    handleDragOver(event) {
      event.preventDefault();
    },

    // 验证并设置文件
    validateAndSetFile(file) {
      // 验证文件类型
      if (!file.type.startsWith('video/')) {
        this.errorMessage = '请选择视频文件';
        return;
      }

      // 验证文件大小 (限制为500MB)
      const maxSize = 500 * 1024 * 1024;
      if (file.size > maxSize) {
        this.errorMessage = '文件大小不能超过500MB';
        return;
      }

      this.selectedFile = file;
      this.errorMessage = '';
      this.currentTask = null;
    },

    // 开始处理视频 - 修改后的方法
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
        // 使用封装的API函数
        const result = await uploadVideo(formData);
        
        this.currentTask = result;
        
        // 添加到历史记录
        this.addToTaskHistory(result);
        
        // 开始轮询进度
        this.startProgressPolling(result.taskId);
        
      } catch (error) {
        console.error('处理视频失败:', error);
        this.errorMessage = `处理失败: ${error.message}`;
        this.isProcessing = false;
      }
    },

    // 开始轮询进度 - 修改后的方法
    startProgressPolling(taskId) {
      this.cleanupProgressPolling();
      
      this.progressInterval = setInterval(async () => {
        try {
          // 使用封装的API函数
          const task = await getVideoProgress(taskId);
          this.currentTask = task;
          
          // 更新历史记录中的任务状态
          this.updateTaskHistory(task);
          
          // 如果任务完成或出错，停止轮询
          if (task.status === 'completed' || task.status === 'error') {
            this.isProcessing = false;
            this.cleanupProgressPolling();
          }
        } catch (error) {
          console.error('获取进度失败:', error);
        }
      }, 2000); // 每2秒轮询一次
    },

    // 清理进度轮询
    cleanupProgressPolling() {
      if (this.progressInterval) {
        clearInterval(this.progressInterval);
        this.progressInterval = null;
      }
    },

    // 下载处理后的视频 - 修改后的方法
    async downloadVideo() {
      if (!this.currentTask || this.currentTask.status !== 'completed') {
        this.errorMessage = '视频尚未处理完成';
        return;
      }

      try {
        // 使用封装的API函数
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

    // 清理任务 - 修改后的方法
    async cleanupTask() {
      if (!this.currentTask) return;

      try {
        // 使用封装的API函数
        await cleanupVideoTask(this.currentTask.taskId);
        
        this.removeFromTaskHistory(this.currentTask.taskId);
        this.currentTask = null;
        
      } catch (error) {
        console.error('清理任务失败:', error);
      }
    },

    // 重新尝试处理
    retryProcessing() {
      if (this.selectedFile) {
        this.startProcessing();
      }
    },

    // 任务历史相关方法
    loadTaskHistory() {
      const history = localStorage.getItem('videoTaskHistory');
      if (history) {
        this.taskHistory = JSON.parse(history);
      }
    },

    addToTaskHistory(task) {
      this.taskHistory.unshift(task);
      this.saveTaskHistory();
    },

    updateTaskHistory(updatedTask) {
      const index = this.taskHistory.findIndex(t => t.taskId === updatedTask.taskId);
      if (index !== -1) {
        this.taskHistory[index] = updatedTask;
        this.saveTaskHistory();
      }
    },

    removeFromTaskHistory(taskId) {
      this.taskHistory = this.taskHistory.filter(t => t.taskId !== taskId);
      this.saveTaskHistory();
    },

    saveTaskHistory() {
      localStorage.setItem('videoTaskHistory', JSON.stringify(this.taskHistory));
    },

    // 下载历史视频 - 修改后的方法
    async downloadHistoryVideo(taskId) {
      try {
        // 使用封装的API函数
        const blob = await downloadVideo(taskId);
        
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        
        const task = this.taskHistory.find(t => t.taskId === taskId);
        const fileName = task ? `processed_${task.originalFileName}` : `processed_video_${taskId}.mp4`;
        
        a.href = url;
        a.download = fileName;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
        
      } catch (error) {
        console.error('下载历史视频失败:', error);
        this.errorMessage = '下载视频失败';
      }
    },

    removeHistoryTask(taskId) {
      this.removeFromTaskHistory(taskId);
      
      // 如果当前任务是被删除的历史任务，清理当前任务
      if (this.currentTask && this.currentTask.taskId === taskId) {
        this.currentTask = null;
      }
    },

    // 工具方法
    formatFileSize(bytes) {
      if (bytes === 0) return '0 Bytes';
      const k = 1024;
      const sizes = ['Bytes', 'KB', 'MB', 'GB'];
      const i = Math.floor(Math.log(bytes) / Math.log(k));
      return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + ' ' + sizes[i];
    },

    getStatusText(status) {
      const statusMap = {
        'processing': '处理中',
        'completed': '已完成',
        'error': '出错'
      };
      return statusMap[status] || status;
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
  max-width: 800px;
  margin: 0 auto;
}

h1 {
  text-align: center;
  color: #333;
  margin-bottom: 30px;
}

.upload-section {
  margin-bottom: 30px;
}

.upload-area {
  border: 2px dashed #ccc;
  border-radius: 8px;
  padding: 40px;
  text-align: center;
  cursor: pointer;
  transition: all 0.3s ease;
  background-color: #fafafa;
}

.upload-area:hover {
  border-color: #007bff;
  background-color: #f0f8ff;
}

.upload-icon {
  font-size: 48px;
  margin-bottom: 16px;
}

.upload-content h3 {
  margin: 0 0 8px 0;
  color: #333;
}

.upload-content p {
  margin: 0;
  color: #666;
}

.file-info {
  margin-top: 20px;
  padding: 20px;
  background-color: #f8f9fa;
  border-radius: 8px;
}

.processing-params {
  margin: 15px 0;
}

.fps-input {
  width: 80px;
  padding: 5px;
  margin-left: 10px;
  border: 1px solid #ccc;
  border-radius: 4px;
}

.progress-section {
  margin-bottom: 30px;
}

.progress-card {
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  background-color: #fff;
}

.progress-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 15px;
  padding-bottom: 15px;
  border-bottom: 1px solid #dee2e6;
}

.task-id {
  font-family: monospace;
  color: #666;
}

.status-badge {
  padding: 4px 12px;
  border-radius: 20px;
  font-size: 12px;
  font-weight: bold;
}

.status-badge.processing {
  background-color: #fff3cd;
  color: #856404;
}

.status-badge.completed {
  background-color: #d1edff;
  color: #0c5460;
}

.status-badge.error {
  background-color: #f8d7da;
  color: #721c24;
}

.progress-details {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.progress-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.progress-bar-container {
  position: relative;
  width: 200px;
  height: 20px;
  background-color: #e9ecef;
  border-radius: 10px;
  overflow: hidden;
}

.progress-bar {
  height: 100%;
  background-color: #007bff;
  transition: width 0.3s ease;
}

.progress-text {
  position: absolute;
  top: 50%;
  left: 50%;
  transform: translate(-50%, -50%);
  font-size: 12px;
  font-weight: bold;
  color: #333;
}

.action-buttons {
  display: flex;
  gap: 10px;
  margin-top: 20px;
}

.history-section {
  margin-top: 30px;
}

.history-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.history-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 12px 16px;
  border: 1px solid #dee2e6;
  border-radius: 6px;
  background-color: #fff;
}

.history-info {
  flex: 1;
}

.history-status {
  margin-left: 12px;
  padding: 2px 8px;
  border-radius: 12px;
  font-size: 11px;
  font-weight: bold;
}

.history-status.completed {
  background-color: #d4edda;
  color: #155724;
}

.history-status.error {
  background-color: #f8d7da;
  color: #721c24;
}

.history-status.processing {
  background-color: #fff3cd;
  color: #856404;
}

.history-actions {
  display: flex;
  gap: 8px;
}

.btn {
  padding: 8px 16px;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 14px;
  font-weight: bold;
  transition: all 0.3s ease;
}

.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.btn-primary {
  background-color: #007bff;
  color: white;
}

.btn-success {
  background-color: #28a745;
  color: white;
}

.btn-warning {
  background-color: #ffc107;
  color: #212529;
}

.btn-secondary {
  background-color: #6c757d;
  color: white;
}

.btn-sm {
  padding: 4px 8px;
  font-size: 12px;
}

.error-message {
  background-color: #f8d7da;
  color: #721c24;
  padding: 15px;
  border-radius: 5px;
  border: 1px solid #f5c6cb;
  text-align: center;
  margin-top: 20px;
}

@media (max-width: 768px) {
  .upload-area {
    padding: 20px;
  }
  
  .progress-row {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .progress-bar-container {
    width: 100%;
  }
  
  .action-buttons {
    flex-direction: column;
  }
  
  .history-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 10px;
  }
  
  .history-actions {
    align-self: flex-end;
  }
}
</style>
