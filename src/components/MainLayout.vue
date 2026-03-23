<template>
  <div class="main-layout">
    <!-- 顶部导航栏 -->
    <header class="top-navbar">
      <div class="navbar-container">
        <!-- Logo 区域 -->
        <div class="navbar-logo">
          <img src="@/assets/logo.png" alt="Logo" class="logo-img" />
          <span class="logo-text">Fruit Classify System</span>
        </div>

        <!-- 右侧用户菜单或登录按钮 -->
        <div class="navbar-user">
          <!-- 登录状态显示用户信息 -->
          <el-dropdown 
            v-if="isLoggedIn"
            trigger="click" 
            placement="bottom-end"
            @command="handleUserCommand"
          >
            <div class="user-avatar-wrapper">
              <el-avatar 
                :size="36" 
                :src="userAvatar"
                class="user-avatar"
              >
                <img src="@/assets/default-avatar.png" alt="用户头像" />
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

          <!-- 未登录状态显示登录按钮 -->
          <el-button 
            v-else
            type="primary" 
            size="small" 
            @click="handleLoginClick"
            class="login-button"
          >
            <el-icon><User /></el-icon>
            <span>登录</span>
          </el-button>
        </div>
      </div>
    </header>

    <!-- 侧边栏导航 -->
    <aside 
      class="sidebar" 
      :class="{ 'sidebar-collapsed': isCollapsed }"
      @mouseenter="handleMouseEnter"
      @mouseleave="handleMouseLeave"
    >
      <!-- 折叠/展开按钮 -->
      <div class="sidebar-toggle" @click="toggleSidebar">
        <el-icon v-if="isCollapsed">
          <Expand />
        </el-icon>
        <el-icon v-else>
          <Fold />
        </el-icon>
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
        <!-- 仪表盘 -->
        <el-menu-item index="/dashboard">
          <el-icon><HomeFilled /></el-icon>
          <span>仪表盘</span>
        </el-menu-item>

        <!-- 目标检测（带子菜单） -->
        <el-sub-menu index="1">
          <template #title>
            <el-icon><Search /></el-icon>
            <span>目标检测</span>
          </template>
          
          <!-- 图片检测 -->
          <el-menu-item index="/detection/image">
            <el-icon><Picture /></el-icon>
            <span>图片检测</span>
          </el-menu-item>

          <!-- 视频检测 -->
          <el-menu-item index="/detection/video">
            <el-icon><VideoPlay /></el-icon>
            <span>视频检测</span>
          </el-menu-item>

          <!-- 实时检测 -->
          <el-menu-item index="/detection/realtime">
            <el-icon><Monitor /></el-icon>
            <span>实时检测(连接摄像头)</span>
          </el-menu-item>
        </el-sub-menu>

        <!-- 检测历史 -->
        <el-menu-item index="/history">
          <el-icon><Timer /></el-icon>
          <span>检测历史(可查看...)</span>
        </el-menu-item>

        <!-- 个人中心（仅登录状态显示） -->
        <el-menu-item 
          index="/profile"
          v-if="isLoggedIn"
        >
          <el-icon><User /></el-icon>
          <span>个人中心</span>
        </el-menu-item>
      </el-menu>
    </aside>

    <!-- 主内容区域 -->
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
// 导入auth.js中的方法
import { removeToken, removeUserId, getToken, getUserName, removeUserName } from '@/utils/auth'
import { 
  ElMenu, ElMenuItem, ElSubMenu, ElIcon, ElDropdown, ElDropdownMenu, ElDropdownItem, 
  ElAvatar, ElButton
} from 'element-plus'
import { 
  HomeFilled, Search, Picture, VideoPlay, 
  Monitor, Timer, User, Expand, Fold, ArrowDown, SwitchButton
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
    
    // 响应式状态
    const isCollapsed = ref(true)
    const isHovering = ref(false)
    const userAvatar = ref('@/assets/default-avatar.png')
    const isLoggedIn = ref(false) // 登录状态标记
    
    // 计算当前路由用于菜单高亮
    const currentRoute = computed(() => route.path)

    // 获取用户名（使用getUserName方法）
    const userName = ref('用户')
    
    // 检查登录状态
    const checkLoginStatus = () => {
      const token = getToken()
      isLoggedIn.value = !!token
      
      // 如果已登录，获取用户信息
      if (isLoggedIn.value) {
        // 优先使用getUserName获取用户名
        const storedUserName = getUserName()
        if (storedUserName) {
          userName.value = storedUserName
        } else {
          // 如果getUserName获取不到，尝试从userInfo获取（兼容旧版本）
          const userInfo = localStorage.getItem('userInfo')
          if (userInfo) {
            try {
              const userData = JSON.parse(userInfo)
              userName.value = userData.username || '用户'
              // 如果有头像信息，更新头像
              if (userData.avatar) {
                userAvatar.value = userData.avatar
              }
            } catch (e) {
              console.error('解析用户信息失败:', e)
            }
          }
        }
      }
    }
    
    // 初始化时检查登录状态
    onMounted(() => {
      checkLoginStatus()
      
      // 大屏幕默认展开侧边栏
      if (window.innerWidth >= 1200) {
        isCollapsed.value = false
      }
    })

    // 监听路由变化，检查登录状态
    watch(
      () => route.path,
      () => {
        checkLoginStatus()
      }
    )

    // 侧边栏切换方法
    const toggleSidebar = () => {
      isCollapsed.value = !isCollapsed.value
    }

    const handleMouseEnter = () => {
      isHovering.value = true
    }

    const handleMouseLeave = () => {
      isHovering.value = false
    }

    // 处理登录按钮点击
    const handleLoginClick = () => {
      router.push('/login')
    }

    // 用户菜单命令处理
    const handleUserCommand = (command) => {
      switch (command) {
        case 'profile':
          router.push('/profile')
          break
        case 'logout':
          // 清除token、userid和username
          removeToken()
          removeUserId()
          removeUserName()
          localStorage.removeItem('userInfo')
          ElMessage.success('退出登录成功')
          router.push('/login')
          
          // 更新登录状态
          isLoggedIn.value = false
          userName.value = '用户'
          
          // 显示退出成功消息
          ElMessage.success('退出登录成功')
          
          // 跳转到登录页面
          router.push('/login')
          break
        default:
          break
      }
    }

    return {
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

/* 顶部导航栏样式 */
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

/* Logo 区域样式 */
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

/* 用户头像区域样式 */
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

/* 登录按钮样式 */
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

/* 下拉菜单激活时箭头旋转 */
:deep(.el-dropdown.is-active) .dropdown-arrow {
  transform: rotate(180deg);
}

/* 侧边栏基础样式 - 与顶部导航栏配色统一 */
.sidebar {
  width: 240px;
  background-color: #304156; /* 与顶部导航栏起始色一致 */
  /* 移除overflow-y: auto以取消滚动条 */
  transition: all 0.3s ease;
  position: fixed;
  top: 60px; /* 在顶部导航栏下方 */
  bottom: 0;
  left: 0;
  z-index: 1000;
  box-shadow: 2px 0 8px rgba(0, 0, 0, 0.15);
}

/* 折叠状态下的侧边栏 */
.sidebar-collapsed {
  width: 64px !important;
}

/* 侧边栏菜单 */
.sidebar .el-menu {
  border-right: none;
  height: calc(100% - 56px); /* 减去折叠按钮的高度 */
  transition: all 0.3s ease;
  /* 确保菜单不会出现滚动条 */
  overflow: hidden !important;
}

/* 折叠状态下隐藏菜单文字 */
.sidebar-collapsed .el-menu:not(.el-menu--collapse) {
  width: 64px;
}

/* 折叠按钮样式 */
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

/* 菜单项样式优化 */
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

/* 折叠状态下调整图标间距 */
.sidebar-collapsed .el-menu-item .el-icon,
.sidebar-collapsed .el-sub-menu__title .el-icon {
  margin-right: 0;
}

/* 主内容区域 */
.main-content {
  flex: 1;
  overflow: hidden;
  transition: all 0.3s ease;
  margin-top: 60px; /* 为顶部导航栏留出空间 */
  margin-left: 64px; /* 默认折叠状态的侧边栏宽度 */
}

.content-wrapper {
  height: 100%;
  overflow-y: auto;
  padding: 20px;
  transition: all 0.3s ease;
}

/* 侧边栏展开时调整主内容区域 */
.sidebar:not(.sidebar-collapsed) + .main-content {
  margin-left: 240px;
}

/* 响应式设计 */
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
    display: none; /* 在小屏幕上隐藏文字，只显示logo */
  }
}

/* 大屏幕下的悬停效果 */
@media (min-width: 769px) {
  .sidebar:hover:not(.sidebar-collapsed) {
    width: 240px;
  }
  
  /* 确保在非折叠状态下保持完整宽度 */
  .sidebar:not(.sidebar-collapsed) {
    width: 240px !important;
  }
}

/* 子菜单弹出框样式调整 - 与顶部导航栏配色协调 */
:deep(.el-sub-menu .el-sub-menu__title) {
  display: flex;
  align-items: center;
}

:deep(.el-sub-menu .el-menu) {
  background-color: #2c3e50 !important; /* 与顶部导航栏结束色一致 */
}

:deep(.el-sub-menu .el-menu-item) {
  background-color: #2c3e50 !important;
  min-width: 0;
}

:deep(.el-sub-menu .el-menu-item:hover) {
  background-color: #243447 !important; /* 更深的变体色 */
}

/* 菜单项悬停效果 */
:deep(.el-menu-item:hover) {
  background-color: #2c3e50 !important; /* 与顶部导航栏结束色一致 */
}

:deep(.el-sub-menu__title:hover) {
  background-color: #2c3e50 !important;
}

/* 激活菜单项样式 - 使用Logo文字的金色调 */
:deep(.el-menu-item.is-active) {
  background-color: #1890ff !important;
  color: #ffd04b !important; /* 与Logo文字的金色一致 */
}

/* 折叠状态下的工具提示 */
:deep(.el-tooltip__trigger) {
  display: flex;
  align-items: center;
  justify-content: center;
}

/* 确保在折叠状态下子菜单弹出位置正确 */
:deep(.el-popper) {
  margin-left: 4px !important;
}

/* 下拉菜单样式优化 */
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
  color: #304156; /* 使用侧边栏主色 */
}

:deep(.el-dropdown-menu__item:hover) {
  background-color: #f5f7fa;
  color: #1890ff;
}

:deep(.el-dropdown-menu__item--divided) {
  border-top: 1px solid #ebeef5;
}
</style>
