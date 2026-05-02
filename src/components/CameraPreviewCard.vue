<template>
  <article class="preview-card">
    <div class="preview-card__head">
      <strong>{{ title }}</strong>
      <span>索引 {{ cameraIndex }}</span>
    </div>
    <div class="preview-card__stage">
      <img v-if="imageUrl" :src="imageUrl" :alt="title" class="preview-image" />
      <div v-else class="preview-placeholder">
        <p>{{ active ? '等待摄像头预览连接' : '摄像头已停止' }}</p>
      </div>
    </div>
    <div class="preview-card__meta">
      <span>{{ connected ? 'WebSocket 已连接' : 'WebSocket 未连接' }}</span>
      <span v-if="errorMessage" class="preview-card__error">{{ errorMessage }}</span>
    </div>
  </article>
</template>

<script setup>
import { computed, toRef } from 'vue'
import { useCameraPreviewSocket } from '@/composables/useCameraPreviewSocket'

const props = defineProps({
  cameraIndex: {
    type: Number,
    required: true
  },
  title: {
    type: String,
    required: true
  },
  active: {
    type: Boolean,
    default: true
  }
})

const cameraIndex = toRef(props, 'cameraIndex')
const active = toRef(props, 'active')

const { connected, errorMessage, imageUrl } = useCameraPreviewSocket({
  active,
  payload: computed(() => ({
    mode: 'single',
    camera_index: cameraIndex.value,
    detect: false,
    fps: 4
  }))
})
</script>

<style scoped>
.preview-card {
  border-radius: 20px;
  overflow: hidden;
  background: #f6faf7;
}

.preview-card__head {
  display: flex;
  justify-content: space-between;
  gap: 12px;
  padding: 12px 14px;
  color: #173b32;
}

.preview-card__stage {
  min-height: 180px;
  display: grid;
  place-items: center;
  background: linear-gradient(140deg, #0f172a 0%, #1a2c43 100%);
}

.preview-image {
  width: 100%;
  display: block;
}

.preview-placeholder {
  color: #d5dbe5;
  text-align: center;
  padding: 24px 16px;
}

.preview-card__meta {
  display: grid;
  gap: 6px;
  padding: 12px 14px 14px;
  color: #587166;
  font-size: 12px;
}

.preview-card__error {
  color: #b42318;
}
</style>
