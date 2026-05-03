import request from '@/utils/request'

export function createImageDetectionTask(formData) {
  return request({
    url: '/api/image-detection/tasks/',
    method: 'post',
    data: formData,
    headers: { 'Content-Type': 'multipart/form-data' },
    timeout: 300000
  })
}

export function getDetectionHistoryList(params = {}) {
  return request({
    url: '/api/detection/history/',
    method: 'get',
    params,
    timeout: 15000
  })
}

export function getDetectionHistoryDetail(id) {
  return request({
    url: `/api/detection/history/${id}/`,
    method: 'get',
    timeout: 15000
  })
}

export function deleteDetectionHistory(id) {
  return request({
    url: `/api/detection/history/${id}/`,
    method: 'delete',
    timeout: 15000
  })
}

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

export function saveRealtimeReport(data) {
  return request({
    url: '/api/realtime/save_report/',
    method: 'post',
    data,
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

export function getCameraRegistry() {
  return request({
    url: '/api/camera/registry/',
    method: 'get',
    timeout: 10000
  })
}

export function scanCameraRegistry(data = {}) {
  return request({
    url: '/api/camera/registry/scan/',
    method: 'post',
    data,
    timeout: 120000
  })
}

export function updateCameraSelection(data) {
  return request({
    url: '/api/camera/registry/select/',
    method: 'post',
    data,
    timeout: 15000
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

export function captureCameraImages(data) {
  return request({
    url: '/api/camera/capture/',
    method: 'post',
    data,
    timeout: 120000
  })
}

export function saveCameraCaptureStages(data) {
  return request({
    url: '/api/camera/capture/save/',
    method: 'post',
    data,
    timeout: 120000
  })
}

export function getCameraCaptures(params = {}) {
  return request({
    url: '/api/camera/captures/',
    method: 'get',
    params,
    timeout: 15000
  })
}

export function deleteCameraCaptureRecord(recordId) {
  return request({
    url: `/api/camera/captures/${recordId}/`,
    method: 'delete',
    timeout: 15000
  })
}

export function downloadCameraCaptures(data) {
  return request({
    url: '/api/camera/captures/download/',
    method: 'post',
    data,
    responseType: 'blob',
    timeout: 120000
  })
}

export function detectRealtimeCurrentFrame(data) {
  return request({
    url: '/api/realtime/detect/current-frame/',
    method: 'post',
    data,
    timeout: 300000
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
