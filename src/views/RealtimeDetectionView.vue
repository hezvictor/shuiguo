<template>
  <div class="fruit-recognition">
    <div class="container">
      <h1>水果实时识别系统</h1>
      
      <div class="video-container">
        <!-- 显示视频元素，不隐藏 -->
        <video ref="videoElement" class="video-preview" autoplay playsinline muted></video>
        <canvas ref="canvasElement" class="video-canvas"></canvas>
      </div>

      <div class="controls">
        <button 
          @click="startCamera" 
          :disabled="isStreaming" 
          class="btn btn-primary"
        >
          开启摄像头
        </button>
        <button 
          @click="stopCamera" 
          :disabled="!isStreaming" 
          class="btn btn-secondary"
        >
          关闭摄像头
        </button>
        <button 
          @click="toggleProcessing" 
          :class="['btn', isProcessing ? 'btn-warning' : 'btn-success']"
          :disabled="!isStreaming || !isConnected"
        >
          {{ isProcessing ? '停止识别' : '开始识别' }}
        </button>
      </div>

      <!-- 结果显示 -->
      <div v-if="predictions.length > 0" class="results-container">
        <h3>识别结果 (FPS: {{ fps.toFixed(1) }})</h3>
        <div class="predictions">
          <div 
            v-for="(pred, index) in predictions" 
            :key="index" 
            class="prediction-item"
          >
            <span class="class-name">{{ pred.className }}</span>
            <span class="confidence">{{ (pred.confidence * 100).toFixed(1) }}%</span>
            <div class="confidence-bar">
              <div 
                class="confidence-fill" 
                :style="{ width: (pred.confidence * 100) + '%' }"
              ></div>
            </div>
          </div>
        </div>
      </div>

      <!-- 状态信息 -->
      <div class="status">
        <div class="status-item">
          <span class="status-label">摄像头状态:</span>
          <span :class="['status-value', isStreaming ? 'status-on' : 'status-off']">
            {{ isStreaming ? '运行中' : '未开启' }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-label">识别状态:</span>
          <span :class="['status-value', isProcessing ? 'status-on' : 'status-off']">
            {{ isProcessing ? '识别中' : '已停止' }}
          </span>
        </div>
        <div class="status-item">
          <span class="status-label">处理时间:</span>
          <span class="status-value">{{ processingTime }}ms</span>
        </div>
        <div class="status-item">
          <span class="status-label">WebSocket:</span>
          <span :class="['status-value', isConnected ? 'status-on' : 'status-off']">
            {{ isConnected ? '已连接' : '未连接' }}
          </span>
        </div>
      </div>

      <!-- 错误信息 -->
      <div v-if="errorMessage" class="error-message">
        {{ errorMessage }}
      </div>

      <!-- 调试信息 -->
      <div v-if="showDebug" class="debug-info">
        <h4>调试信息</h4>
        <p>视频状态: {{ videoState }}</p>
        <p>WebSocket状态: {{ websocketState }}</p>
        <p>最后错误: {{ lastError }}</p>
      </div>
    </div>
  </div>
</template>

<script>
// 导入封装的WebSocket API函数
import { createWebSocket, setupWebSocketHandlers, getWebSocketUrl } from '@/api/detection'

export default {
  name: 'FruitRecognition',
  data() {
    return {
      isStreaming: false,
      isProcessing: false,
      isConnected: false,
      videoStream: null,
      websocket: null,
      canvasContext: null,
      sendInterval: null,
      
      // 结果数据
      predictions: [],
      fps: 0,
      processingTime: 0,
      errorMessage: '',
      
      // 调试信息
      showDebug: true,
      videoState: '未初始化',
      websocketState: '未连接',
      lastError: '',
      
      // 配置
      targetFPS: 5, // 降低帧率以减少负载
      imageQuality: 0.7, // 降低图像质量
      canvasWidth: 640,
      canvasHeight: 480,
      
      // 视频绘制循环
      drawInterval: null
    };
  },
  mounted() {
    this.initCanvas();
    console.log('组件已挂载');
  },
  beforeUnmount() {
    this.cleanup();
  },
  methods: {
    // 初始化画布
    initCanvas() {
      const canvas = this.$refs.canvasElement;
      if (canvas) {
        this.canvasContext = canvas.getContext('2d');
        canvas.width = this.canvasWidth;
        canvas.height = this.canvasHeight;
        console.log('画布初始化完成');
      }
    },

    // 开启摄像头
    async startCamera() {
      try {
        this.errorMessage = '';
        this.lastError = '';
        this.videoState = '正在请求摄像头权限...';
        
        console.log('开始启动摄像头...');
        
        // 获取摄像头权限
        this.videoStream = await navigator.mediaDevices.getUserMedia({
          video: {
            width: { ideal: this.canvasWidth },
            height: { ideal: this.canvasHeight },
            facingMode: 'environment'
          },
          audio: false
        });

        const video = this.$refs.videoElement;
        if (!video) {
          throw new Error('视频元素未找到');
        }

        video.srcObject = this.videoStream;
        this.videoState = '摄像头已连接，等待视频加载...';

        // 等待视频准备就绪
        await new Promise((resolve, reject) => {
          const timeout = setTimeout(() => {
            reject(new Error('视频加载超时'));
          }, 5000);

          video.onloadedmetadata = () => {
            clearTimeout(timeout);
            video.play().then(resolve).catch(reject);
          };

          video.onerror = () => {
            clearTimeout(timeout);
            reject(new Error('视频播放失败'));
          };
        });

        this.isStreaming = true;
        this.videoState = '视频流运行中';
        console.log('摄像头启动成功');

        // 开始绘制视频到画布
        this.startDrawingVideo();
        
        // 连接WebSocket
        await this.connectWebSocket();
        
      } catch (error) {
        console.error('开启摄像头失败:', error);
        this.errorMessage = `开启摄像头失败: ${error.message}`;
        this.lastError = error.message;
        this.videoState = `错误: ${error.message}`;
        this.stopCamera();
      }
    },

    // 开始绘制视频到画布
    startDrawingVideo() {
      this.stopDrawingVideo(); // 先停止之前的绘制
        
      const drawFrame = () => {
        if (this.isStreaming) {
          this.drawVideoFrame();
          this.drawInterval = requestAnimationFrame(drawFrame);
        }
      };
      
      drawFrame();
    },

    // 停止绘制视频
    stopDrawingVideo() {
      if (this.drawInterval) {
        cancelAnimationFrame(this.drawInterval);
        this.drawInterval = null;
      }
    },

    // 绘制视频帧到画布
    drawVideoFrame() {
      const canvas = this.$refs.canvasElement;
      const video = this.$refs.videoElement;
      const ctx = this.canvasContext;
      
      if (canvas && video && ctx && video.readyState >= 2) { // HAVE_CURRENT_DATA or better
        // 清除画布
        ctx.clearRect(0, 0, canvas.width, canvas.height);
        
        // 绘制视频帧
        ctx.drawImage(video, 0, 0, canvas.width, canvas.height);
        
        // 如果正在处理，绘制处理状态
        if (this.isProcessing) {
          ctx.fillStyle = 'rgba(0, 0, 0, 0.7)';
          ctx.fillRect(10, 10, 200, 40);
          ctx.fillStyle = '#00ff00';
          ctx.font = '16px Arial';
          ctx.fillText('识别中...', 20, 35);
        }
      }
    },

    // 连接WebSocket - 使用封装的API
    connectWebSocket() {
      return new Promise((resolve, reject) => {
        try {
          // 使用封装的函数获取WebSocket URL
          const wsUrl = getWebSocketUrl('/ws/fruit-recognition');
          
          console.log('正在连接WebSocket:', wsUrl);
          
          // 使用封装的函数创建WebSocket
          this.websocket = createWebSocket(wsUrl);
          
          // 使用封装的函数设置WebSocket处理器
          setupWebSocketHandlers(this.websocket, {
            onOpen: () => {
              console.log('WebSocket连接已建立');
              this.isConnected = true;
              this.websocketState = '已连接';
              resolve();
            },
            
            onMessage: (event) => {
              this.handleWebSocketMessage(event.data);
            },
            
            onClose: (event) => {
              console.log('WebSocket连接已关闭:', event);
              this.isConnected = false;
              this.websocketState = '已断开: ' + event.code + ' ' + event.reason;
              if (this.isProcessing) {
                this.stopProcessing();
              }
              
              // 如果是异常断开，尝试重新连接
              if (event.code !== 1000) {
                console.log('WebSocket异常断开，尝试重新连接...');
                setTimeout(() => {
                  if (this.isStreaming) {
                    this.connectWebSocket().catch(console.error);
                  }
                }, 3000);
              }
            },
            
            onError: (error) => {
              console.error('WebSocket错误:', error);
              this.errorMessage = 'WebSocket连接错误';
              this.isConnected = false;
              this.websocketState = '连接错误';
              reject(error);
            }
          });
          
        } catch (error) {
          console.error('创建WebSocket连接失败:', error);
          this.errorMessage = '创建WebSocket连接失败';
          this.websocketState = '创建连接失败';
          reject(error);
        }
      });
    },

    // 处理WebSocket消息
    handleWebSocketMessage(message) {
      try {
        console.log('收到WebSocket消息:', message.substring(0, 100) + '...');
        const response = JSON.parse(message);
        
        if (response.status === 'success') {
          this.predictions = response.predictions || [];
          this.processingTime = response.processingTime || 0;
          this.fps = response.fps || 0;
          
          // 在画布上绘制识别结果
          this.drawPredictionsOnCanvas();
          
        } else if (response.status === 'error') {
          this.errorMessage = response.errorMessage || '处理图像时发生错误';
          this.lastError = response.errorMessage;
          console.error('服务器返回错误:', response.errorMessage);
        }
        
      } catch (error) {
        console.error('解析WebSocket消息失败:', error);
        this.errorMessage = '解析服务器响应失败';
        this.lastError = error.message;
      }
    },

    // 在画布上绘制识别结果
    drawPredictionsOnCanvas() {
      const canvas = this.$refs.canvasElement;
      const ctx = this.canvasContext;
      
      if (!canvas || !ctx) return;
      
      // 设置绘制样式
      ctx.font = '16px Arial, "Microsoft YaHei", sans-serif';
      ctx.textBaseline = 'top';
      
      // 绘制FPS
      ctx.fillStyle = '#ff00ff';
      ctx.fillText(`FPS: ${this.fps.toFixed(1)}`, 20, 20);
      
      // 绘制预测结果
      this.predictions.forEach((pred, index) => {
        const y = 50 + index * 30;
        const text = `${pred.className} ${(pred.confidence * 100).toFixed(1)}%`;
        
        // 绘制背景矩形
        ctx.fillStyle = 'rgba(0, 0, 0, 0.5)';
        ctx.fillRect(15, y - 5, ctx.measureText(text).width + 10, 25);
        
        // 绘制文本
        ctx.fillStyle = '#ffffff';
        ctx.fillText(text, 20, y);
        
        // 绘制置信度条
        const barWidth = 150;
        const barHeight = 6;
        const barY = y + 20;
        
        // 背景条
        ctx.fillStyle = 'rgba(255, 255, 255, 0.3)';
        ctx.fillRect(20, barY, barWidth, barHeight);
        
        // 前景条
        ctx.fillStyle = '#ff0000';
        ctx.fillRect(20, barY, barWidth * pred.confidence, barHeight);
      });
    },

    // 开始处理
    toggleProcessing() {
      if (this.isProcessing) {
        this.stopProcessing();
      } else {
        this.startProcessing();
      }
    },

    // 开始处理帧
    startProcessing() {
      if (!this.isStreaming) {
        this.errorMessage = '请先开启摄像头';
        return;
      }
      
      if (!this.isConnected) {
        this.errorMessage = 'WebSocket未连接，请检查服务器状态';
        return;
      }
      
      this.isProcessing = true;
      this.errorMessage = '';
      
      console.log('开始图像识别处理...');
      
      // 设置发送帧的间隔
      const interval = 1000 / this.targetFPS;
      this.sendInterval = setInterval(() => {
        this.sendFrameToServer();
      }, interval);
    },

    // 停止处理
    stopProcessing() {
      this.isProcessing = false;
      if (this.sendInterval) {
        clearInterval(this.sendInterval);
        this.sendInterval = null;
      }
      console.log('停止图像识别处理');
    },

    // 发送帧到服务器
    sendFrameToServer() {
      if (!this.isConnected || !this.websocket || this.websocket.readyState !== WebSocket.OPEN) {
        console.warn('WebSocket连接已断开，停止发送');
        this.errorMessage = 'WebSocket连接已断开';
        this.stopProcessing();
        return;
      }

      try {
        const canvas = this.$refs.canvasElement;
        if (!canvas) {
          throw new Error('画布元素未找到');
        }

        // 检查画布是否有有效内容
        if (canvas.width === 0 || canvas.height === 0) {
          console.warn('画布尺寸为0，跳过发送');
          return;
        }

        // 将画布内容转换为Base64，降低质量以减少数据量
        const imageData = canvas.toDataURL('image/jpeg', 0.6); // 降低质量到0.6
        
        // 检查数据大小
        if (imageData.length > 500000) { // 如果超过500KB
          console.warn('图像数据过大:', imageData.length);
          // 可以进一步降低质量或尺寸
        }

        // 发送到服务器
        this.websocket.send(imageData);
        
      } catch (error) {
        console.error('发送帧数据失败:', error);
        this.errorMessage = '发送图像数据失败: ' + error.message;
        this.lastError = error.message;
        
        // 如果是频繁的错误，停止处理
        this.stopProcessing();
      }
    },

    // 关闭摄像头
    stopCamera() {
      console.log('正在关闭摄像头...');
      
      this.stopProcessing();
      this.stopDrawingVideo();
      
      if (this.videoStream) {
        this.videoStream.getTracks().forEach(track => {
          track.stop();
          console.log('停止轨道:', track.kind);
        });
        this.videoStream = null;
      }
      
      if (this.websocket && this.websocket.readyState === WebSocket.OPEN) {
        this.websocket.close();
      }
      
      this.isStreaming = false;
      this.isConnected = false;
      this.predictions = [];
      this.videoState = '已停止';
      
      // 清除画布
      const canvas = this.$refs.canvasElement;
      if (canvas && this.canvasContext) {
        this.canvasContext.clearRect(0, 0, canvas.width, canvas.height);
      }
      
      console.log('摄像头已关闭');
    },

    // 清理资源
    cleanup() {
      this.stopCamera();
    }
  }
};
</script>

<style scoped>
.fruit-recognition {
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

.video-container {
  position: relative;
  width: 100%;
  margin-bottom: 20px;
  border: 2px solid #ddd;
  border-radius: 8px;
  overflow: hidden;
  background-color: #000;
}

.video-preview, .video-canvas {
  width: 100%;
  height: auto;
  display: block;
}

/* 修改这里：视频元素不隐藏，但画布覆盖在视频上方 */
.video-container {
  position: relative;
}

.video-preview {
  /* 视频作为背景 */
  width: 100%;
  height: auto;
}

.video-canvas {
  /* 画布覆盖在视频上方，用于绘制识别结果 */
  position: absolute;
  top: 0;
  left: 0;
  background: transparent; /* 透明背景，显示下方的视频 */
}

.controls {
  display: flex;
  gap: 10px;
  justify-content: center;
  margin-bottom: 20px;
  flex-wrap: wrap;
}

.btn {
  padding: 10px 20px;
  border: none;
  border-radius: 5px;
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

.btn-secondary {
  background-color: #6c757d;
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

.results-container {
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 8px;
  padding: 20px;
  margin-bottom: 20px;
}

.results-container h3 {
  margin-top: 0;
  color: #495057;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 10px;
}

.predictions {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.prediction-item {
  display: flex;
  align-items: center;
  gap: 15px;
  padding: 8px;
  background-color: white;
  border-radius: 4px;
  box-shadow: 0 1px 3px rgba(0,0,0,0.1);
}

.class-name {
  flex: 1;
  font-weight: bold;
  color: #333;
}

.confidence {
  width: 60px;
  text-align: right;
  color: #007bff;
  font-weight: bold;
}

.confidence-bar {
  width: 200px;
  height: 8px;
  background-color: #e9ecef;
  border-radius: 4px;
  overflow: hidden;
}

.confidence-fill {
  height: 100%;
  background-color: #28a745;
  transition: width 0.3s ease;
}

.status {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 15px;
  margin-bottom: 20px;
}

.status-item {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 10px 15px;
  background-color: #f8f9fa;
  border-radius: 5px;
  border-left: 4px solid #6c757d;
}

.status-label {
  font-weight: bold;
  color: #495057;
}

.status-value {
  font-weight: bold;
}

.status-on {
  color: #28a745;
}

.status-off {
  color: #dc3545;
}

.error-message {
  background-color: #f8d7da;
  color: #721c24;
  padding: 15px;
  border-radius: 5px;
  border: 1px solid #f5c6cb;
  text-align: center;
  margin-bottom: 15px;
}

.debug-info {
  background-color: #f8f9fa;
  border: 1px solid #dee2e6;
  border-radius: 5px;
  padding: 15px;
  margin-top: 20px;
  font-size: 14px;
}

.debug-info h4 {
  margin-top: 0;
  color: #6c757d;
  border-bottom: 1px solid #dee2e6;
  padding-bottom: 5px;
}

.debug-info p {
  margin: 5px 0;
}

@media (max-width: 768px) {
  .video-container {
    margin-bottom: 15px;
  }
  
  .controls {
    flex-direction: column;
    align-items: center;
  }
  
  .btn {
    width: 200px;
  }
  
  .status {
    grid-template-columns: 1fr;
  }
  
  .prediction-item {
    flex-direction: column;
    align-items: flex-start;
    gap: 8px;
  }
  
  .confidence-bar {
    width: 100%;
  }
}
</style>