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
                <img :src="defaultAvatar" alt="用户头像" />
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

    <aside
      class="sidebar"
      :class="{ 'sidebar-collapsed': isCollapsed }"
      @mouseenter="handleMouseEnter"
      @mouseleave="handleMouseLeave"
    >
      <div class="sidebar-toggle" @click="toggleSidebar">
        <el-icon v-if="isCollapsed"><Expand /></el-icon>
        <el-icon v-else><Fold /></el-icon>
      </div>

      <el-menu
        :default-active="currentRoute"
        background-color="#304156"
        text-color="#e8f5e9"
        active-text-color="#ffd04b"
        :default-openeds="['1']"
        :router="true"
        :collapse="isCollapsed"
        :collapse-transition="false"
        class="sidebar-menu"
      >
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>

        <el-sub-menu index="1">
          <template #title>
            <el-icon><Search /></el-icon>
            <span>目标检测</span>
          </template>

          <el-menu-item index="/detection/image">
            <el-icon><Picture /></el-icon>
            <span>图片检测</span>
          </el-menu-item>

          <el-menu-item index="/detection/video">
            <el-icon><VideoPlay /></el-icon>
            <span>视频检测</span>
          </el-menu-item>

          <el-menu-item index="/detection/realtime">
            <el-icon><Monitor /></el-icon>
            <span>实时检测</span>
          </el-menu-item>

          <el-menu-item index="/detection/diameter">
            <el-icon><Picture /></el-icon>
            <span>果径测量</span>
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
import { defineComponent, ref, onMounted, computed, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { ElMessage } from 'element-plus'
import defaultAvatar from '@/assets/default-avatar.png'
import { clearLoginState, getToken, getUserName, logout as logoutApi } from '@/utils/auth'
import {
  ElMenu,
  ElMenuItem,
  ElSubMenu,
  ElIcon,
  ElDropdown,
  ElDropdownMenu,
  ElDropdownItem,
  ElAvatar,
  ElButton
} from 'element-plus'
import {
  HomeFilled,
  Search,
  Picture,
  VideoPlay,
  Monitor,
  Timer,
  User,
  Expand,
  Fold,
  ArrowDown,
  SwitchButton
} from '@element-plus/icons-vue'

export default defineComponent({
  name: 'MainLayout',
  components: {
    ElMenu,
    ElMenuItem,
    ElSubMenu,
    ElIcon,
    ElDropdown,
    ElDropdownMenu,
    ElDropdownItem,
    ElAvatar,
    ElButton,
    HomeFilled,
    Search,
    Picture,
    VideoPlay,
    Monitor,
    Timer,
    User,
    Expand,
    Fold,
    ArrowDown,
    SwitchButton
  },
  setup() {
    const router = useRouter()
    const route = useRoute()

    const isCollapsed = ref(true)
    const isHovering = ref(false)
    const userAvatar = ref(defaultAvatar)
    const userName = ref('用户')
    const isLoggedIn = ref(false)

    const currentRoute = computed(() => route.path)

    const checkLoginStatus = () => {
      const token = getToken()
      isLoggedIn.value = !!token

      if (!token) {
        userName.value = '用户'
        userAvatar.value = defaultAvatar
        return
      }

      const storedUserName = getUserName()
      if (storedUserName) {
        userName.value = storedUserName
      }

      const userInfo = localStorage.getItem('userInfo')
      if (userInfo) {
        try {
          const userData = JSON.parse(userInfo)
          userName.value = userData.username || storedUserName || '用户'
          if (userData.avatar) {
            userAvatar.value = userData.avatar
          }
        } catch (error) {
          console.error('解析用户信息失败:', error)
        }
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

    const handleMouseEnter = () => {
      isHovering.value = true
    }

    const handleMouseLeave = () => {
      isHovering.value = false
    }

    const handleLoginClick = () => {
      router.push('/login')
    }

    const handleUserCommand = async (command) => {
      switch (command) {
        case 'profile':
          router.push('/profile')
          break
        case 'logout':
          try {
            await logoutApi()
          } catch (_error) {
            // 即使后端 session 已失效，也继续清理本地登录态。
          }

          clearLoginState()
          isLoggedIn.value = false
          userName.value = '用户'
          userAvatar.value = defaultAvatar
          ElMessage.success('已退出登录')
          router.push('/login')
          break
        default:
          break
      }
    }

    return {
      defaultAvatar,
      isCollapsed,
      isHovering,
      userAvatar,
      userName,
      currentRoute,
      isLoggedIn,
      toggleSidebar,
      handleMouseEnter,
      handleMouseLeave,
      handleUserCommand,
      handleLoginClick
    }
  }
})
</script>

<style scoped>
.main-layout {
  display: flex;
  flex-direction: column;
  height: 100vh;
  background-color: #f5f7fa;
  transition: all 0.3s ease;
}

.top-navbar {
  height: 60px;
  background: linear-gradient(135deg, #304156 0%, #2c3e50 100%);
  box-shadow: 0 2px 8px rgba(0, 0, 0, 0.15);
  position: fixed;
  top: 0;
  left: 0;
  right: 0;
  z-index: 2000;
  display: flex;
  align-items: center;
}

.navbar-container {
  width: 100%;
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: 0 20px;
  height: 100%;
}

.navbar-logo {
  display: flex;
  align-items: center;
  gap: 12px;
  color: white;
  font-weight: 600;
  font-size: 18px;
}

.logo-img {
  width: 32px;
  height: 32px;
  border-radius: 4px;
  object-fit: cover;
}

.logo-text {
  font-size: 18px;
  font-weight: bold;
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
  cursor: pointer;
  padding: 8px 12px;
  border-radius: 6px;
  transition: background-color 0.3s ease;
}

.user-avatar-wrapper:hover {
  background-color: rgba(255, 255, 255, 0.1);
}

.user-avatar {
  border: 2px solid rgba(255, 255, 255, 0.3);
  transition: border-color 0.3s ease;
}

.user-avatar-wrapper:hover .user-avatar {
  border-color: rgba(255, 255, 255, 0.6);
}

.dropdown-arrow {
  color: rgba(255, 255, 255, 0.7);
  font-size: 14px;
  transition: transform 0.3s ease;
}

.login-button {
  background-color: #1890ff;
  border-color: #1890ff;
  color: white;
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 6px 16px;
  transition: all 0.3s ease;
}

.login-button:hover {
  background-color: #096dd9;
  border-color: #096dd9;
}

:deep(.el-dropdown.is-active) .dropdown-arrow {
  transform: rotate(180deg);
}

.sidebar {
  width: 240px;
  background-color: #304156;
  transition: all 0.3s ease;
  position: fixed;
  top: 60px;
  bottom: 0;
  left: 0;
  z-index: 1000;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
}

.sidebar-collapsed {
  width: 64px !important;
}

.sidebar .el-menu {
  border-right: none;
  height: calc(100% - 56px);
  transition: all 0.3s ease;
  overflow: hidden !important;
}

.sidebar-collapsed .el-menu:not(.el-menu--collapse) {
  width: 64px;
}

.sidebar-toggle {
  height: 56px;
  display: flex;
  align-items: center;
  justify-content: center;
  background-color: rgba(0, 0, 0, 0.2);
  color: #fff;
  cursor: pointer;
  transition: all 0.3s ease;
  border-bottom: 1px solid rgba(255, 255, 255, 0.1);
}

.sidebar-toggle:hover {
  background-color: rgba(0, 0, 0, 0.3);
}

.sidebar-toggle .el-icon {
  font-size: 20px;
  transition: transform 0.3s ease;
}

.sidebar-menu .el-menu-item,
.sidebar-menu .el-sub-menu__title {
  height: 56px;
  line-height: 56px;
  transition: all 0.3s ease;
}

.sidebar-menu .el-menu-item .el-icon,
.sidebar-menu .el-sub-menu__title .el-icon {
  margin-right: 12px;
  font-size: 18px;
}

.sidebar-collapsed .el-menu-item .el-icon,
.sidebar-collapsed .el-sub-menu__title .el-icon {
  margin-right: 0;
}

.main-content {
  flex: 1;
  overflow: hidden;
  transition: all 0.3s ease;
  margin-top: 60px;
  margin-left: 64px;
}

.content-wrapper {
  height: 100%;
  overflow-y: auto;
  padding: 20px;
  transition: all 0.3s ease;
}

.sidebar:not(.sidebar-collapsed) + .main-content {
  margin-left: 240px;
}

@media (max-width: 768px) {
  .sidebar {
    width: 64px;
    position: fixed;
    left: 0;
    top: 60px;
    bottom: 0;
    z-index: 1000;
    transform: translateX(0);
  }

  .sidebar:not(.sidebar-collapsed) {
    width: 240px;
    box-shadow: 4px 0 16px rgba(0, 0, 0, 0.2);
  }

  .main-content {
    margin-left: 64px;
  }

  .content-wrapper {
    padding: 15px;
  }

  .navbar-container {
    padding: 0 15px;
  }

  .logo-text {
    font-size: 16px;
  }
}

@media (max-width: 480px) {
  .sidebar:not(.sidebar-collapsed) {
    width: 200px;
  }

  .content-wrapper {
    padding: 10px;
  }

  .navbar-container {
    padding: 0 10px;
  }

  .logo-text {
    display: none;
  }
}

@media (min-width: 769px) {
  .sidebar:hover:not(.sidebar-collapsed) {
    width: 240px;
  }

  .sidebar:not(.sidebar-collapsed) {
    width: 240px !important;
  }
}

:deep(.el-sub-menu .el-sub-menu__title) {
  display: flex;
  align-items: center;
}

:deep(.el-sub-menu .el-menu) {
  background-color: #2c3e50 !important;
}

:deep(.el-sub-menu .el-menu-item) {
  background-color: #2c3e50 !important;
  min-width: 0;
}

:deep(.el-sub-menu .el-menu-item:hover) {
  background-color: #243447 !important;
}

:deep(.el-menu-item:hover) {
  background-color: #2c3e50 !important;
}

:deep(.el-sub-menu__title:hover) {
  background-color: #2c3e50 !important;
}

:deep(.el-menu-item.is-active) {
  background-color: #1890ff !important;
  color: #ffd04b !important;
}

:deep(.el-tooltip__trigger) {
  display: flex;
  align-items: center;
  justify-content: center;
}

:deep(.el-popper) {
  margin-left: 4px !important;
}

:deep(.el-dropdown-menu) {
  border: none;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
  border-radius: 8px;
  padding: 8px 0;
}

:deep(.el-dropdown-menu__item) {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 16px;
  font-size: 14px;
  transition: all 0.3s ease;
}

:deep(.el-dropdown-menu__item .el-icon) {
  font-size: 16px;
  color: #304156;
}

:deep(.el-dropdown-menu__item:hover) {
  background-color: #f5f7fa;
  color: #1890ff;
}

:deep(.el-dropdown-menu__item--divided) {
  border-top: 1px solid #ebeef5;
}
</style>
