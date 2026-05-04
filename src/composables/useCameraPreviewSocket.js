import { computed, onBeforeUnmount, ref, watch } from 'vue'

const DEFAULT_WS_PATH = '/ws/camera/device-preview/'
const DEFAULT_STREAM_FPS = 10

export function useCameraPreviewSocket(options = {}) {
  const wsPath = options.wsPath || DEFAULT_WS_PATH
  const streamFps = options.streamFps || DEFAULT_STREAM_FPS
  const active = options.active
  const payload = options.payload
  const includeFrameDataUrl = options.includeFrameDataUrl === true
  const onStatus = options.onStatus || (() => {})
  const onReady = options.onReady || (() => {})
  const onError = options.onError || (() => {})

  const imageUrl = ref('')
  const frameDataUrl = ref('')
  const connected = ref(false)
  const errorMessage = ref('')
  const status = ref(null)

  let socket = null
  let reconnectTimer = null
  let manualClose = false
  let latestFrameBlob = null

  const isActive = computed(() => (typeof active === 'function' ? !!active() : !!active?.value))
  const previewPayload = computed(() => {
    const raw = typeof payload === 'function' ? payload() : payload?.value || {}
    return {
      fps: streamFps,
      ...raw
    }
  })

  const buildSocketUrl = () => {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    const normalizedPath = wsPath.startsWith('/') ? wsPath : `/${wsPath}`
    return `${protocol}//${window.location.host}${normalizedPath}`
  }

  const revokeImageUrl = () => {
    if (imageUrl.value) {
      URL.revokeObjectURL(imageUrl.value)
      imageUrl.value = ''
    }
    frameDataUrl.value = ''
    latestFrameBlob = null
  }

  const closeSocket = ({ clearImage = false } = {}) => {
    manualClose = true
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    const current = socket
    socket = null
    connected.value = false

    if (current && current.readyState === WebSocket.OPEN) {
      try {
        current.send(JSON.stringify({ type: 'preview.unsubscribe' }))
      } catch (error) {
        console.warn('preview unsubscribe failed', error)
      }
    }

    if (current && [WebSocket.OPEN, WebSocket.CONNECTING].includes(current.readyState)) {
      current.close()
    }

    if (clearImage) {
      revokeImageUrl()
    }
  }

  const scheduleReconnect = () => {
    if (reconnectTimer || !isActive.value) {
      return
    }
    reconnectTimer = window.setTimeout(() => {
      reconnectTimer = null
      connect()
    }, 1500)
  }

  const blobToDataUrl = (blob) =>
    new Promise((resolve, reject) => {
      const reader = new FileReader()
      reader.onload = () => resolve(typeof reader.result === 'string' ? reader.result : '')
      reader.onerror = () => reject(reader.error || new Error('failed to read preview frame'))
      reader.readAsDataURL(blob)
    })

  const updateImage = async (data) => {
    const nextBlob = data instanceof Blob ? data : new Blob([data], { type: 'image/jpeg' })
    const nextUrl = URL.createObjectURL(nextBlob)
    revokeImageUrl()
    imageUrl.value = nextUrl
    latestFrameBlob = nextBlob
    if (includeFrameDataUrl) {
      frameDataUrl.value = await blobToDataUrl(nextBlob)
    }
    errorMessage.value = ''
  }

  const getFrameDataUrl = async () => {
    if (frameDataUrl.value) {
      return frameDataUrl.value
    }
    if (!latestFrameBlob) {
      return ''
    }
    frameDataUrl.value = await blobToDataUrl(latestFrameBlob)
    return frameDataUrl.value
  }

  const handleControlMessage = (raw) => {
    try {
      const message = JSON.parse(raw)
      status.value = message
      if (message.type === 'preview.ready') {
        onReady(message)
        return
      }
      if (message.type === 'preview.status') {
        onStatus(message)
        if (!message.camera_active) {
          revokeImageUrl()
        }
        return
      }
      if (message.type === 'preview.error') {
        errorMessage.value = message.message || '摄像头预览失败'
        onError(message)
      }
    } catch (error) {
      console.warn('preview message parse failed', error)
    }
  }

  const sendMessage = (message) => {
    if (!socket || socket.readyState !== WebSocket.OPEN) {
      return
    }
    socket.send(JSON.stringify(message))
  }

  const syncConfig = () => {
    if (!isActive.value || !socket || socket.readyState !== WebSocket.OPEN) {
      return
    }
    sendMessage({
      type: 'preview.update',
      ...previewPayload.value
    })
  }

  const connect = () => {
    if (!isActive.value) {
      return
    }
    if (socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) {
      return
    }
    if (reconnectTimer) {
      window.clearTimeout(reconnectTimer)
      reconnectTimer = null
    }

    manualClose = false
    errorMessage.value = ''
    const nextSocket = new WebSocket(buildSocketUrl())
    nextSocket.binaryType = 'blob'

    nextSocket.onopen = () => {
      connected.value = true
      sendMessage({
        type: 'preview.subscribe',
        ...previewPayload.value
      })
    }

    nextSocket.onmessage = async (event) => {
      if (typeof event.data === 'string') {
        handleControlMessage(event.data)
        return
      }
      await updateImage(event.data)
    }

    nextSocket.onerror = () => {
      errorMessage.value = '摄像头预览 WebSocket 连接异常'
    }

    nextSocket.onclose = () => {
      connected.value = false
      socket = null
      if (manualClose || !isActive.value) {
        return
      }
      errorMessage.value = '摄像头预览连接已断开，正在尝试重连'
      revokeImageUrl()
      scheduleReconnect()
    }

    socket = nextSocket
  }

  watch(
    isActive,
    (value) => {
      if (value) {
        connect()
        return
      }
      closeSocket({ clearImage: true })
    },
    { immediate: true }
  )

  watch(
    previewPayload,
    () => {
      syncConfig()
    },
    { deep: true }
  )

  onBeforeUnmount(() => {
    closeSocket({ clearImage: true })
  })

  return {
    connected,
    errorMessage,
    frameDataUrl,
    getFrameDataUrl,
    imageUrl,
    status,
    connect,
    closeSocket,
    syncConfig,
    sendMessage
  }
}
