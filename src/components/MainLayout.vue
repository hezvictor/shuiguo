<template>
  <div class="main-layout">
    <header class="top-navbar">
      <div class="navbar-container">
        <div class="navbar-logo">
          <img src="@/assets/logo.png" alt="Logo" class="logo-img" />
          <span class="logo-text">Fruit Classify System</span>
        </div>

        <div class="navbar-user">
          <el-dropdown
            v-if="isLoggedIn"
            trigger="click"
            placement="bottom-end"
            @command="handleUserCommand"
          >
            <div class="user-avatar-wrapper">
              <el-avatar :size="36" :src="userAvatar" class="user-avatar">
                <img :src="defaultAvatar" alt="Default Avatar" />
              </el-avatar>
              <span class="user-name">{{ userName }}</span>
              <el-icon class="dropdown-arrow"><ArrowDown /></el-icon>
            </div>
            <template #dropdown>
              <el-dropdown-menu class="user-dropdown-menu">
                <el-dropdown-item command="profile" class="dropdown-item">
                  <el-icon><User /></el-icon>
                  <span>个人中心</span>
                </el-dropdown-item>
                <el-dropdown-item command="logout" class="dropdown-item">
                  <el-icon><SwitchButton /></el-icon>
                  <span>退出登录</span>
                </el-dropdown-item>
              </el-dropdown-menu>
            </template>
          </el-dropdown>

          <el-button
            v-else
            type="primary"
            size="small"
            class="login-button"
            @click="handleLoginClick"
          >
            <el-icon><User /></el-icon>
            <span>登录</span>
          </el-button>
        </div>
      </div>
    </header>

    <aside class="sidebar" :class="{ 'sidebar-collapsed': isCollapsed }">
      <div class="sidebar-toggle" @click="toggleSidebar">
        <el-icon v-if="isCollapsed"><Expand /></el-icon>
        <el-icon v-else><Fold /></el-icon>
      </div>

      <el-menu
        :default-active="currentRoute"
        background-color="#304156"
        text-color="#e8f5e9"
        active-text-color="#ffd04b"
        :default-openeds="['detect']"
        :router="true"
        :collapse="isCollapsed"
        :collapse-transition="false"
        class="sidebar-menu"
      >
        <el-menu-item index="/console">
          <el-icon><HomeFilled /></el-icon>
          <span>控制台</span>
        </el-menu-item>

        <el-sub-menu index="detect">
          <template #title>
            <el-icon><Search /></el-icon>
            <span>检测功能</span>
          </template>

          <el-menu-item index="/detection/image">
            <el-icon><Picture /></el-icon>
            <span>图片检测</span>
          </el-menu-item>

          <el-menu-item index="/detection/realtime">
            <el-icon><Monitor /></el-icon>
            <span>实时检测</span>
          </el-menu-item>

          <el-menu-item index="/camera/config">
            <el-icon><DataAnalysis /></el-icon>
            <span>摄像头配置</span>
          </el-menu-item>
        </el-sub-menu>

        <el-menu-item index="/history">
          <el-icon><Timer /></el-icon>
          <span>检测历史</span>
        </el-menu-item>

        <el-menu-item v-if="isLoggedIn" index="/profile">
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <main class="main-content" :class="{ 'content-expanded': isCollapsed }">
      <div class="content-wrapper">
        <router-view />
      </div>
    </main>
  </div>
</template>

<script>
import { computed, defineComponent, onMounted, ref, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import defaultAvatar from '@/assets/default-avatar.png'
import { clearLoginState, getToken, getUserName, logout as logoutApi } from '@/utils/auth'
import {
  ArrowDown,
  DataAnalysis,
  Expand,
  Fold,
  HomeFilled,
  Monitor,
  Picture,
  Search,
  SwitchButton,
  Timer,
  User
} from '@element-plus/icons-vue'

export default defineComponent({
  name: 'MainLayout',
  components: {
    ArrowDown,
    DataAnalysis,
    Expand,
    Fold,
    HomeFilled,
    Monitor,
    Picture,
    Search,
    SwitchButton,
    Timer,
    User
  },
  setup() {
    const router = useRouter()
    const route = useRoute()

    const isCollapsed = ref(true)
    const userAvatar = ref(defaultAvatar)
    const userName = ref('用户')
    const isLoggedIn = ref(false)

    const currentRoute = computed(() => route.path)

    const checkLoginStatus = () => {
      const token = getToken()
      isLoggedIn.value = !!token

      if (!token) {
        userAvatar.value = defaultAvatar
        userName.value = '用户'
        return
      }

      const storedUserName = getUserName()
      if (storedUserName) {
        userName.value = storedUserName
      }

      const rawUserInfo = localStorage.getItem('userInfo')
      if (!rawUserInfo) {
        return
      }

      try {
        const userInfo = JSON.parse(rawUserInfo)
        userName.value = userInfo.username || storedUserName || '用户'
        if (userInfo.avatar) {
          userAvatar.value = userInfo.avatar
        }
      } catch (error) {
        console.error('parse user info failed', error)
      }
    }

    onMounted(() => {
      checkLoginStatus()
      if (window.innerWidth >= 1200) {
        isCollapsed.value = false
      }
    })

    watch(
      () => route.path,
      () => {
        checkLoginStatus()
      }
    )

    const toggleSidebar = () => {
      isCollapsed.value = !isCollapsed.value
    }

    const handleLoginClick = () => {
      router.push('/login')
    }

    const handleUserCommand = async (command) => {
      if (command === 'profile') {
        router.push('/profile')
        return
      }

      if (command !== 'logout') {
        return
      }

      try {
        await logoutApi()
      } catch (_error) {
        // keep local logout flow even when backend session already expired
      }

      clearLoginState()
      isLoggedIn.value = false
      userName.value = '用户'
      userAvatar.value = defaultAvatar
      ElMessage.success('已退出登录')
      router.push('/login')
    }

    return {
      currentRoute,
      defaultAvatar,
      handleLoginClick,
      handleUserCommand,
      isCollapsed,
      isLoggedIn,
      toggleSidebar,
      userAvatar,
      userName
    }
  }
})
</script>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  min-height: 100vh;
  background: #f5f7fa;
}

.top-navbar {
  position: fixed;
  top: 0;
  right: 0;
  left: 0;
  z-index: 2000;
  height: 60px;
  display: flex;
  align-items: center;
  background: linear-gradient(135deg, #304156 0%, #2c3e50 100%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
}

.navbar-container {
  width: 100%;
  height: 100%;
  padding: 0 20px;
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.navbar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  color: #fff;
}

.logo-img {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  object-fit: cover;
}

.logo-text {
  font-size: 18px;
  font-weight: 700;
  background: linear-gradient(90deg, #ffd04b, #ffa726);
  -webkit-background-clip: text;
  -webkit-text-fill-color: transparent;
  background-clip: text;
}

.navbar-user {
  display: flex;
  align-items: center;
}

.user-avatar-wrapper {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 8px 12px;
  border-radius: 8px;
  cursor: pointer;
  transition: background-color 0.2s ease;
}

.user-avatar-wrapper:hover {
  background: rgba(255, 255, 255, 0.1);
}

.user-avatar {
  border: 2px solid rgba(255, 255, 255, 0.28);
}

.user-name,
.dropdown-arrow {
  color: rgba(255, 255, 255, 0.92);
}

.login-button {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.sidebar {
  position: fixed;
  top: 60px;
  bottom: 0;
  left: 0;
  z-index: 1000;
  width: 240px;
  background: #304156;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
  transition: width 0.3s ease;
}

.sidebar-collapsed {
  width: 64px;
}

.sidebar-toggle {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  color: #fff;
  background: rgba(0, 0, 0, 0.2);
  border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  cursor: pointer;
}

.sidebar-toggle:hover {
  background: rgba(0, 0, 0, 0.28);
}

.sidebar-menu {
  border-right: none;
  height: calc(100% - 56px);
}

.sidebar-menu :deep(.el-menu-item),
.sidebar-menu :deep(.el-sub-menu__title) {
  height: 56px;
  line-height: 56px;
}

.sidebar-menu :deep(.el-menu-item .el-icon),
.sidebar-menu :deep(.el-sub-menu__title .el-icon) {
  margin-right: 12px;
  font-size: 18px;
}

.sidebar-collapsed .sidebar-menu :deep(.el-menu-item .el-icon),
.sidebar-collapsed .sidebar-menu :deep(.el-sub-menu__title .el-icon) {
  margin-right: 0;
}

.sidebar-menu :deep(.el-sub-menu .el-menu) {
  background: #2c3e50 !important;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item) {
  background: #2c3e50 !important;
}

.sidebar-menu :deep(.el-sub-menu .el-menu-item:hover),
.sidebar-menu :deep(.el-menu-item:hover),
.sidebar-menu :deep(.el-sub-menu__title:hover) {
  background: #243447 !important;
}

.sidebar-menu :deep(.el-menu-item.is-active) {
  background: #1890ff !important;
  color: #ffd04b !important;
}

.main-content {
  flex: 1;
  margin-top: 60px;
  margin-left: 240px;
  transition: margin-left 0.3s ease;
}

.content-expanded {
  margin-left: 64px;
}

.content-wrapper {
  height: calc(100vh - 60px);
  overflow-y: auto;
  padding: 20px;
}

:deep(.el-dropdown-menu) {
  border: none;
  border-radius: 10px;
  box-shadow: 0 8px 18px rgba(0, 0, 0, 0.16);
}

:deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: 8px;
}

@media (max-width: 768px) {
  .sidebar {
    width: 64px;
  }

  .sidebar:not(.sidebar-collapsed) {
    width: 220px;
  }

  .main-content {
    margin-left: 64px;
  }

  .content-wrapper {
    padding: 14px;
  }

  .logo-text {
    font-size: 16px;
  }
}

@media (max-width: 480px) {
  .navbar-container {
    padding: 0 12px;
  }

  .logo-text {
    display: none;
  }
}
</style>
