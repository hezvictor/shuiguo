import request from '@/utils/request'

export function detectImage(formData) {
  return request({
    url: '/api/yolo_detect_info/',    // 原为 '/login/yolo_detect_info/'
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000
  })
}

export function detectImageWithBoxes(formData) {
  return request({
    url: '/api/yolo_detect_with_boxes/',   // 原为 '/login/yolo_detect_with_boxes/'
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    responseType: 'blob',
    timeout: 30000
  })
}

export function generateReport(formData) {
  return request({
    url: '/api/yolo_report/',        // 原为 '/login/yolo_report/'
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 30000
  })
}

// 视频检测接口（暂留，但后端未实现）
export function uploadVideo(formData) {
  return request({
    url: '/api/video/upload',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' }
  })
}