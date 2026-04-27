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
        redirect: '/console'
      },
      {
        path: '/console',
        name: 'console',
        component: () => import('../views/ConsoleView.vue')
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
        path: '/detection/diameter',
        name: 'diameterMeasurement',
        component: () => import('../views/DiameterMeasurementView.vue')
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
        component: () => import('../views/AboutView.vue')
      }
    ]
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

router.beforeEach((to, _from, next) => {
  const token = getToken()

  if (to.path === '/login' && token) {
    next('/console')
    return
  }

  if (to.path !== '/login' && to.path !== '/register' && !token) {
    next('/login')
    return
  }

  next()
})

export default router
