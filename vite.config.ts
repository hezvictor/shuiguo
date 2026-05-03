import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

const projectRoot = fileURLToPath(new URL('.', import.meta.url))

export default defineConfig({
  root: projectRoot,
  plugins: [
    vue(),
    vueDevTools()
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url))
    }
  },
  server: {
    proxy: {
      '/api/': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/media/': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/ws/': {
        target: 'ws://localhost:8000',
        changeOrigin: true,
        ws: true
      },
      '/static/': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})

