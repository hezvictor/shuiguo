import request from '@/utils/request'

export function getConsoleOverview(params) {
  return request({
    url: '/api/console/overview/',
    method: 'get',
    params,
    timeout: 30000
  })
}

export function getConsoleRecent(params) {
  return request({
    url: '/api/console/recent/',
    method: 'get',
    params,
    timeout: 30000
  })
}

export function getConsoleSystemStatus() {
  return request({
    url: '/api/console/system-status/',
    method: 'get',
    timeout: 15000
  })
}
