import request from '@/utils/request.js'

// 登录
export function login(params) {
  return request({
    url: '/api/login/',
    method: 'post',
    data: params
  })
}

// 注册
export function register(params) {
  return request({
    url: '/api/register/',
    method: 'post',
    data: params
  })
}

// 获取当前用户信息
export function getCurrentUserInfo() {
  return request({
    url: '/api/user_info/',
    method: 'get'
  })
}

// 修改用户信息（仅支持 first_name 和 email）
export function updateUserInfo(params) {
  return request({
    url: '/api/update_profile/',
    method: 'post',
    data: params
  })
}

// 修改密码
export function changePassword(params) {
  return request({
    url: '/api/change_password/',
    method: 'post',
    data: params
  })
}

// 模拟 token 存储（用于前端路由守卫）
export function setToken(token) {
  localStorage.setItem('token', token)
}

export function getToken() {
  return localStorage.getItem('token')
}

export function removeToken() {
  localStorage.removeItem('token')
}

export function setUserId(id) {
  localStorage.setItem('userId', id)
}

export function getUserId() {
  return localStorage.getItem('userId')
}

export function removeUserId() {
  localStorage.removeItem('userId')
}

export function setUserName(name) {
  localStorage.setItem('userName', name)
}

export function getUserName() {
  return localStorage.getItem('userName')
}

export function removeUserName() {
  localStorage.removeItem('userName')
}