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
