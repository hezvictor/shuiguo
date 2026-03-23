// src/utils/request.js
import axios from 'axios'
import { getToken } from '@/utils/auth.js'

// 直接从 cookie 获取 csrftoken
function getCookie(name) {
  let cookieValue = null;
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';');
    for (let i = 0; i < cookies.length; i++) {
      const cookie = cookies[i].trim();
      if (cookie.substring(0, name.length + 1) === (name + '=')) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
        break;
      }
    }
  }
  return cookieValue;
}

// 开发环境下使用代理，baseURL 设为空，请求将发送到当前域名（Vite dev server）
// 生产环境可改为实际后端地址（如 /api 或完整 URL）
const serverUrl = ''   

const request = axios.create({
  baseURL: serverUrl,   
  timeout: 30000,
  withCredentials: true           // 允许携带 cookie
})

// 拦截器等其他代码保持不变
request.interceptors.request.use(config => {
  const csrftoken = getCookie('csrftoken');
  if (csrftoken) {
    config.headers['X-CSRFToken'] = csrftoken;
  }
  const token = getToken();
  if (token) {
    config.headers['token'] = token;
  }
  return config
}, error => {
  console.error('request error:' + error)
  return Promise.reject(error)
})

request.interceptors.response.use(
  response => {
    let res = response.data;
    if (response.headers['content-type'] && response.headers['content-type'].includes('image')) {
      return res;
    }
    if (typeof res === 'string') {
      res = res ? JSON.parse(res) : res
    }
    return res
  }, error => {
    if (error.response && error.response.status === 401) {
      import('@/utils/auth').then(({ removeToken, removeUserId, removeUserName }) => {
        removeToken()
        removeUserId()
        removeUserName()
        localStorage.removeItem('userInfo')
        window.location.href = '/login'
      })
    }
    return Promise.reject(error)
  }
)

export default request