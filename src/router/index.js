import { createRouter, createWebHistory } from 'vue-router'
import { getToken } from '@/utils/auth'  
const routes = [
  {
    path: '/',
    redirect: '/login'
  },
  {
    path: '/login',
    name: 'login',
    component: () => import('../components/Login.vue')
  },
  {
    path: '/register',
    name: 'register',
    component: () => import('../components/Register.vue')
  },
  {
    path: '/',
    component: () => import('../components/MainLayout.vue'),
    children: [
      {
        path: '/dashboard',
        name: 'dashboard',
        component: () => import('../views/DashboardView.vue')
      },
      {
        path: '/detection/image',
        name: 'imageDetection',
        component: () => import('../views/ImageDetectionView.vue')
      },
      {
        path: '/detection/video',
        name: 'videoDetection',
        component: () => import('../views/VideoDetectionView.vue')
      },
      {
        path: '/detection/realtime',
        name: 'realtimeDetection',
        component: () => import('../views/RealtimeDetectionView.vue')
      },
      {
        path: '/history',
        name: 'detectionHistory',
        component: () => import('../views/DetectionHistoryView.vue')
      },
      {
        path: '/profile',
        name: 'userProfile',
        component: () => import('../views/UserProfileView.vue')
      },
      {
        path: '/about',
        name: 'about',
        component: () => import(/* webpackChunkName: "about" */ '../views/AboutView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, from, next) => {
  const token = getToken()   // 使用统一的 getToken
  if (to.path === '/login' && token) {
    next('/dashboard')
  } else if (to.path !== '/login' && !token && to.path !== '/register') {
    next('/login')
  } else {
    next()
  }
})

export default router