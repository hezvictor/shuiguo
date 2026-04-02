/// <reference types="vite/client" />

declare module '*.vue'

declare module './router' {
  import type { Router } from 'vue-router'
  const router: Router
  export default router
}
