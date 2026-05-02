import axios from 'axios'
import { getToken } from '@/utils/auth.js'

function getCookie(name) {
  let cookieValue = null
  if (document.cookie && document.cookie !== '') {
    const cookies = document.cookie.split(';')
    for (let i = 0; i < cookies.length; i += 1) {
      const cookie = cookies[i].trim()
      if (cookie.substring(0, name.length + 1) === `${name}=`) {
        cookieValue = decodeURIComponent(cookie.substring(name.length + 1))
        break
      }
    }
  }
  return cookieValue
}

const request = axios.create({
  baseURL: '',
  timeout: 30000,
  withCredentials: true
})

let csrfBootstrapPromise = null

async function ensureCsrfCookie() {
  if (getCookie('csrftoken')) {
    return getCookie('csrftoken')
  }
  if (!csrfBootstrapPromise) {
    csrfBootstrapPromise = fetch('/api/csrf/', {
      method: 'GET',
      credentials: 'include'
    })
      .then(() => getCookie('csrftoken'))
      .finally(() => {
        csrfBootstrapPromise = null
      })
  }
  return csrfBootstrapPromise
}

request.interceptors.request.use(
  async (config) => {
    const method = String(config.method || 'get').toUpperCase()
    const isSafeMethod = ['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method)
    let csrftoken = getCookie('csrftoken')
    if (!isSafeMethod && !csrftoken) {
      csrftoken = await ensureCsrfCookie()
    }
    if (csrftoken) {
      config.headers['X-CSRFToken'] = csrftoken
    }

    const token = getToken()
    if (token) {
      config.headers.token = token
    }

    return config
  },
  (error) => Promise.reject(error)
)

request.interceptors.response.use(
  (response) => {
    if (response.config.responseType === 'blob') {
      return response.data
    }

    if (response.headers['content-type']?.includes('image')) {
      return response.data
    }

    const payload = response.data
    if (typeof payload === 'string') {
      try {
        return payload ? JSON.parse(payload) : payload
      } catch (_error) {
        return payload
      }
    }

    return payload
  },
  async (error) => {
    if (error.response?.status === 401) {
      const { clearLoginState } = await import('@/utils/auth')
      clearLoginState()
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }

    return Promise.reject(error)
  }
)

export default request
