<template>
  <div class="diameter-page">
    <div class="card">
      <h1>果径测量</h1>
      <p class="desc">上传左右相机图像，系统将自动框选目标并输出每个目标的果径（mm）。</p>

      <div class="upload-grid">
        <div class="upload-item">
          <label>左图</label>
          <input type="file" accept="image/*" @change="onFileChange($event, 'left')" />
          <img v-if="leftPreview" :src="leftPreview" alt="left" class="preview" />
        </div>
        <div class="upload-item">
          <label>右图</label>
          <input type="file" accept="image/*" @change="onFileChange($event, 'right')" />
          <img v-if="rightPreview" :src="rightPreview" alt="right" class="preview" />
        </div>
      </div>

      <div class="actions">
        <button class="btn primary" :disabled="loading || !leftFile || !rightFile" @click="handleMeasure">
          {{ loading ? '测量中...' : '开始测量' }}
        </button>
        <button class="btn" :disabled="loading" @click="resetAll">重置</button>
      </div>

      <p v-if="errorMessage" class="error">{{ errorMessage }}</p>

      <div v-if="result" class="result-section">
        <div class="stats">
          <span>目标总数: {{ result.total_targets }}</span>
          <span>有效测量: {{ result.valid_measurements }}</span>
          <span>平均果径: {{ formatMm(result.statistics?.avg_diameter_mm) }}</span>
        </div>

        <img
          v-if="result.visualization_url"
          :src="result.visualization_url"
          alt="measurement-result"
          class="result-image"
        />

        <table class="result-table">
          <thead>
            <tr>
              <th>#</th>
              <th>类别</th>
              <th>置信度</th>
              <th>框坐标</th>
              <th>果径(mm)</th>
              <th>状态</th>
            </tr>
          </thead>
          <tbody>
            <tr v-for="(item, index) in result.targets" :key="index">
              <td>{{ index + 1 }}</td>
              <td>{{ item.label }}</td>
              <td>{{ (item.confidence * 100).toFixed(1) }}%</td>
              <td>[{{ item.bbox.join(', ') }}]</td>
              <td>{{ formatMm(item.diameter_mm) }}</td>
              <td>{{ item.status }}</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>
</template>

<script>
import { measureFruitDiameter } from '@/api/detection'

export default {
  name: 'DiameterMeasurementView',
  data() {
    return {
      leftFile: null,
      rightFile: null,
      leftPreview: '',
      rightPreview: '',
      loading: false,
      errorMessage: '',
      result: null
    }
  },
  methods: {
    onFileChange(event, side) {
      const file = event.target.files[0]
      if (!file || !file.type.startsWith('image/')) {
        this.errorMessage = '请上传图片文件'
        return
      }
      this.errorMessage = ''
      const url = URL.createObjectURL(file)
      if (side === 'left') {
        if (this.leftPreview) URL.revokeObjectURL(this.leftPreview)
        this.leftFile = file
        this.leftPreview = url
      } else {
        if (this.rightPreview) URL.revokeObjectURL(this.rightPreview)
        this.rightFile = file
        this.rightPreview = url
      }
    },
    async handleMeasure() {
      if (!this.leftFile || !this.rightFile) {
        this.errorMessage = '请先上传左右图像'
        return
      }
      this.loading = true
      this.errorMessage = ''
      this.result = null
      try {
        const formData = new FormData()
        formData.append('left_image', this.leftFile)
        formData.append('right_image', this.rightFile)
        formData.append('save_vis', 'true')

        const res = await measureFruitDiameter(formData)
        if (res.status !== 'success') {
          throw new Error(res.error || '测量失败')
        }
        this.result = res
      } catch (error) {
        this.errorMessage =
          error?.response?.data?.error ||
          error?.response?.data?.detail ||
          error?.message ||
          '测量失败，请稍后重试'
      } finally {
        this.loading = false
      }
    },
    formatMm(value) {
      return value === null || value === undefined ? '-' : `${Number(value).toFixed(2)}`
    },
    resetAll() {
      if (this.leftPreview) URL.revokeObjectURL(this.leftPreview)
      if (this.rightPreview) URL.revokeObjectURL(this.rightPreview)
      this.leftFile = null
      this.rightFile = null
      this.leftPreview = ''
      this.rightPreview = ''
      this.loading = false
      this.errorMessage = ''
      this.result = null
    }
  },
  beforeUnmount() {
    if (this.leftPreview) URL.revokeObjectURL(this.leftPreview)
    if (this.rightPreview) URL.revokeObjectURL(this.rightPreview)
  }
}
</script>

<style scoped>
.diameter-page {
  max-width: 1200px;
  margin: 0 auto;
}
.card {
  background: #fff;
  border-radius: 12px;
  padding: 24px;
  box-shadow: 0 4px 14px rgba(0, 0, 0, 0.08);
}
h1 {
  margin: 0 0 8px;
  color: #1f2d3d;
}
.desc {
  margin: 0 0 20px;
  color: #54627a;
}
.upload-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 16px;
}
.upload-item {
  border: 1px solid #e5e7eb;
  border-radius: 10px;
  padding: 12px;
}
.upload-item label {
  display: block;
  margin-bottom: 8px;
  font-weight: 600;
}
.preview {
  width: 100%;
  max-height: 300px;
  object-fit: contain;
  margin-top: 10px;
  border-radius: 8px;
  background: #f8fafc;
}
.actions {
  margin-top: 16px;
  display: flex;
  gap: 10px;
}
.btn {
  border: none;
  border-radius: 8px;
  padding: 10px 18px;
  cursor: pointer;
  background: #e5e7eb;
}
.btn.primary {
  background: #2563eb;
  color: #fff;
}
.btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}
.error {
  margin-top: 12px;
  color: #dc2626;
}
.result-section {
  margin-top: 20px;
}
.stats {
  display: flex;
  gap: 14px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}
.result-image {
  width: 100%;
  border-radius: 8px;
  border: 1px solid #e5e7eb;
  margin-bottom: 12px;
}
.result-table {
  width: 100%;
  border-collapse: collapse;
}
.result-table th,
.result-table td {
  border: 1px solid #e5e7eb;
  padding: 8px 10px;
  text-align: left;
}
.result-table th {
  background: #f8fafc;
}
@media (max-width: 768px) {
  .upload-grid {
    grid-template-columns: 1fr;
  }
}
</style>
