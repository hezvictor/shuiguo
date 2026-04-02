import request from '@/utils/request.js'

export function login(params) {
  return request({
    url: '/api/login/',
    method: 'post',
    data: params
  })
}

export function register(params) {
  return request({
    url: '/api/register/',
    method: 'post',
    data: params
  })
}

export function logout() {
  return request({
    url: '/api/logout/',
    method: 'post'
  })
}

export function getCurrentUserInfo() {
  return request({
    url: '/api/user_info/',
    method: 'get'
  })
}

export function updateUserInfo(params) {
  return request({
    url: '/api/update_profile/',
    method: 'post',
    data: params
  })
}

export function changePassword(params) {
  return request({
    url: '/api/change_password/',
    method: 'post',
    data: params
  })
}

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

export function storeLoginState(user) {
  setToken('logged_in')

  if (!user) {
    removeUserId()
    removeUserName()
    localStorage.removeItem('userInfo')
    return
  }

  setUserId(String(user.id ?? ''))
  setUserName(user.username || '')
  localStorage.setItem('userInfo', JSON.stringify(user))
}

export function clearLoginState() {
  removeToken()
  removeUserId()
  removeUserName()
  localStorage.removeItem('userInfo')
}
