// src/api/detection.js
import request from '@/utils/request'

export function detectImage(formData) {
  return request({
    url: '/api/yolo_detect_info/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000
  })
}

export function detectImageWithBoxes(formData) {
  return request({
    url: '/api/yolo_detect_with_boxes/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob',
    timeout: 30000
  })
}

export function generateReport(formData) {
  return request({
    url: '/api/yolo_report/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000
  })
}

// 视频检测相关 API
export function uploadVideo(formData) {
  return request({
    url: '/api/video/upload/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 60000 // 上传视频可能需要更长时间
  })
}

export function getVideoProgress(taskId) {
  return request({
    url: `/api/video/progress/${taskId}/`,
    method: 'get',
    timeout: 10000
  })
}

export function downloadVideo(taskId) {
  return request({
    url: `/api/video/download/${taskId}/`,
    method: 'get',
    responseType: 'blob',
    timeout: 120000
  })
}

export function cleanupVideoTask(taskId) {
  return request({
    url: `/api/video/cleanup/${taskId}/`,
    method: 'delete',
    timeout: 10000
  })
}

// detection.js
export function saveRealtimeReport(data) {
  return request({
    url: '/api/realtime/save_report/',
    method: 'post',
    data: data,
    timeout: 10000
  })
}

export function measureFruitDiameter(formData) {
  return request({
    url: '/api/measure/diameter/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 120000
  })
}

export function measureInfer(formData) {
  return request({
    url: '/api/measure/infer/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000
  })
}

export function measureDistance(data) {
  return request({
    url: '/api/measure/distance/',
    method: 'post',
    data,
    timeout: 120000
  })
}

export function getCameraStatus() {
  return request({
    url: '/api/camera/status/',
    method: 'get',
    timeout: 10000
  })
}

export function probeCameraIndices(maxIndex = 4) {
  return request({
    url: `/api/camera/probe/?max_index=${maxIndex}`,
    method: 'get',
    timeout: 120000
  })
}

export function startStereoCamera(data) {
  return request({
    url: '/api/camera/start/',
    method: 'post',
    data,
    timeout: 120000
  })
}

export function stopStereoCamera() {
  return request({
    url: '/api/camera/stop/',
    method: 'post',
    data: {},
    timeout: 10000
  })
}

export function measureCurrentStereoFrame(data) {
  return request({
    url: '/api/camera/measure/',
    method: 'post',
    data,
    timeout: 300000
  })
}

export function getMeasureRuntimeStatus() {
  return request({
    url: '/api/measure/runtime-status/',
    method: 'get',
    timeout: 15000
  })
}

export function getCalibrationStatus(sessionId = '') {
  const suffix = sessionId ? `?session_id=${encodeURIComponent(sessionId)}` : ''
  return request({
    url: `/api/camera/calibration/status/${suffix}`,
    method: 'get',
    timeout: 15000
  })
}

export function captureCalibrationFrame(data) {
  return request({
    url: '/api/camera/calibration/capture/',
    method: 'post',
    data,
    timeout: 60000
  })
}

export function runStereoCalibration(data) {
  return request({
    url: '/api/camera/calibration/run/',
    method: 'post',
    data,
    timeout: 600000
  })
}
