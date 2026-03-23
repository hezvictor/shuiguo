<template>
  <div class="register-container">
    <!-- 装饰性背景元素 -->
    <div class="bg-decoration">
      <div class="circle c1"></div>
      <div class="circle c2"></div>
      <div class="circle c3"></div>
    </div>
    
    <!-- 主注册卡片 -->
    <div class="register-card">
      <!-- 左侧表单区 -->
      <div class="form-section">
        <div class="form-header">
          <h2>创建您的账户</h2>
          <p>加入我们，开启精彩旅程</p>
        </div>
        
        <el-form 
          :model="form" 
          :rules="rules" 
          ref="registerForm"
          class="register-form"
          @submit.prevent="register"
        >
          <!-- 用户名输入 -->
          <el-form-item prop="username">
            <el-input 
              v-model="form.username" 
              placeholder="请输入用户名"
              size="large"
              :prefix-icon="User"
              class="custom-input"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <!-- 真实姓名输入 -->
          <el-form-item prop="name">
            <el-input 
              v-model="form.name" 
              placeholder="请输入真实姓名"
              size="large"
              :prefix-icon="User"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <!-- 邮箱输入 -->
          <el-form-item prop="email">
            <el-input 
              v-model="form.email" 
              placeholder="请输入邮箱地址"
              size="large"
              :prefix-icon="Message"
            >
              <template #prefix>
                <el-icon><Message /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <!-- 手机号输入 -->
          <el-form-item prop="phone">
            <el-input 
              v-model="form.phone" 
              placeholder="请输入手机号码"
              size="large"
              :prefix-icon="Phone"
            >
              <template #prefix>
                <el-icon><Phone /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <!-- 密码输入 -->
          <el-form-item prop="password">
            <el-input 
              v-model="form.password" 
              type="password" 
              placeholder="请输入密码（6-20位）"
              size="large"
              :prefix-icon="Lock"
              show-password
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <!-- 确认密码 -->
          <el-form-item prop="confirmPassword">
            <el-input 
              v-model="form.confirmPassword" 
              type="password" 
              placeholder="请再次输入密码"
              size="large"
              :prefix-icon="Lock"
              show-password
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>
          
          <!-- 注册按钮 -->
          <el-form-item>
            <el-button 
              type="primary" 
              @click="register" 
              :loading="isLoading"
              class="register-btn"
              size="large"
            >
              {{ isLoading ? '注册中...' : '立即注册' }}
            </el-button>
          </el-form-item>
        </el-form>
        
        <!-- 登录链接 -->
        <div class="login-link">
          已有账户？
          <span @click="goToLogin" class="link-text">立即登录</span>
        </div>
      </div>
      
      <!-- 右侧欢迎区 -->
      <div class="welcome-section">
        <div class="welcome-content">
          <h1>Welcome Back</h1>
          <p>Already have an account?</p>
          <el-button @click="goToLogin" class="login-btn-secondary">
            Sign In
          </el-button>
        </div>
        
        <!-- 装饰性SVG -->
        <div class="svg-decoration">
          <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
            <path fill="#FF0066" d="M45.2,-58.1C58.1,-46.3,67.3,-30.1,70.8,-12.3C74.3,5.5,72.1,25,63.9,40.9C55.7,56.8,41.5,69.1,25.1,74.9C8.7,80.7,-10,79.9,-26.7,73.5C-43.4,67.1,-58.1,55,-67.1,39.1C-76.1,23.2,-79.5,3.4,-75.9,-13.9C-72.3,-31.3,-61.7,-45.9,-47.9,-57.3C-34.1,-68.7,-17.1,-76.9,0.3,-77.2C17.6,-77.5,35.1,-69.9,45.2,-58.1Z" transform="translate(100 100)" />
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { User, Lock, Message, Phone } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { register, setUserId, setUserName, setToken } from '@/utils/auth'

export default {
  name: 'Register',
  components: { User, Lock, Message, Phone },
  data() {
    // 表单验证规则...
    return {
      form: { username: '', password: '', confirmPassword: '', name: '', email: '', phone: '' },
      rules: { /* ... */ },
      isLoading: false
    }
  },
  methods: {
    async register() {
      const valid = await this.$refs.registerForm.validate().catch(() => false)
      if (!valid) return
      this.isLoading = true
      try {
        const res = await register({
          username: this.form.username,
          password: this.form.password,
          email: this.form.email
        })
        if (res.status === 'success') {
          const user = res.user
          if (user) {
            setUserId(user.id)
            setUserName(user.username)
            localStorage.setItem('userInfo', JSON.stringify(user))
          }
          setToken('logged_in')
          ElMessage.success('注册成功，正在进入系统...')
          this.$router.push('/dashboard')
        } else {
          ElMessage.error(res.error || '注册失败')
        }
      } catch (err) {
        ElMessage.error('注册失败，请检查网络')
      } finally {
        this.isLoading = false
      }
    },
    goToLogin() {
      this.$router.push('/login')
    }
  }
}
</script>

<style scoped>
/* ==========================================================
   响应式注册页 - 玻璃拟态风格
   1. 与登录页保持统一视觉风格
   2. 弹性布局 + 媒体查询适配
   3. 动效与交互细节优化
   ========================================================== */

/* -------------- 基础布局 -------------- */
.register-container{
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  padding:20px;
  background:linear-gradient(135deg,#e8f5e8 0%,#b8dcc0 100%);
  position:relative;
  overflow:hidden;
}

/* 背景装饰 */
.bg-decoration{
  position:absolute;
  top:0;
  left:0;
  width:100%;
  height:100%;
  overflow:hidden;
  z-index:0;
}
.circle{
  position:absolute;
  border-radius:50%;
  background:rgba(255,255,255,.1);
  animation:float 6s ease-in-out infinite;
}
.c1{width:80px;height:80px;top:20%;left:10%;animation-delay:0s;}
.c2{width:120px;height:120px;top:60%;right:10%;animation-delay:2s;}
.c3{width:60px;height:60px;bottom:20%;left:80%;animation-delay:4s;}
@keyframes float{
  0%,100%{transform:translateY(0);}
  50%{transform:translateY(-20px);}
}

/* -------------- 注册卡片 -------------- */
.register-card{
  display:flex;
  width:100%;
  max-width:780px; /* 缩小最大宽度 */
  background:rgba(255,255,255,.75);
  border-radius:24px;
  box-shadow:0 8px 32px rgba(31,38,135,.18);
  overflow:hidden;
  backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,.3);
  position:relative;
  z-index:1;
}

/* 表单区域 */
.form-section{
  flex:1;
  padding:40px 40px; /* 减少内边距 */
  display:flex;
  flex-direction:column;
  justify-content:center;
}
.form-header{
  text-align:center;
  margin-bottom:24px; /* 减少底部间距 */
}
.form-header h2{
  margin:0 0 10px 0;
  color:#445b53;
  font-size:24px; /* 缩小标题 */
  font-weight:600;
  letter-spacing:1px;
}
.form-header p{
  margin:0;
  color:#5f8276;
  font-size:15px; /* 缩小副标题 */
}

/* -------------- 输入框样式 -------------- */
.register-form{
  width:100%;
  max-width:320px; /* 限制表单最大宽度 */
  margin:0 auto; /* 居中表单 */
}
:deep(.el-form-item){
  margin-bottom:18px; /* 减少表单项间距 */
}
:deep(.el-input__wrapper){
  background:transparent;
  border:0;
  border-bottom:2px solid rgba(68,91,83,.35);
  border-radius:0;
  padding:8px 0; /* 减少输入框内边距 */
  transition:border-color .3s;
}
:deep(.el-input__wrapper:hover){
  border-color:#5f8276;
}
:deep(.el-input__wrapper.is-focus){
  border-color:#5f8276;
  box-shadow:0 2px 0 0 #5f8276;
}
:deep(.el-input__inner){
  height:40px; /* 缩小输入框高度 */
  line-height:40px;
  font-size:15px; /* 缩小字体 */
  color:#445b53;
  padding-left:32px !important; /* 调整图标与文字间距 */
}
:deep(.el-input__prefix){
  left:4px;
  color:#5f8276;
  font-size:16px; /* 缩小图标 */
}
/* 自动填充样式 */
input:-webkit-autofill{
  -webkit-box-shadow:0 0 0 1000px rgba(255,255,255,.9) inset;
  -webkit-text-fill-color:#445b53;
  caret-color:#445b53;
}

/* -------------- 按钮样式 -------------- */
.register-btn{
  width:100%;
  height:42px; /* 缩小按钮高度 */
  border:0;
  border-radius:21px; /* 按比例调整圆角 */
  background:linear-gradient(90deg,#5f8276 0%,#89ab9e 100%);
  color:#fff;
  font-size:16px; /* 缩小按钮文字 */
  font-weight:bold;
  letter-spacing:2px;
  cursor:pointer;
  transition:all .3s;
  margin-top:6px;
}
.register-btn:hover{
  transform:translateY(-2px);
  box-shadow:0 6px 20px rgba(95,130,118,.35);
}
.register-btn:active{
  transform:translateY(0);
}

/* 登录链接 */
.login-link{
  text-align:center;
  margin-top:16px; /* 减少间距 */
  color:#5f8276;
  font-size:13px; /* 缩小字体 */
}
.link-text{
  color:#445b53;
  cursor:pointer;
  text-decoration:underline;
  font-weight:500;
  transition:color .3s;
}
.link-text:hover{
  color:#2c3e50;
}

/* -------------- 欢迎区域 -------------- */
.welcome-section{
  flex:0 0 35%; /* 缩小右侧区域比例 */
  background:url('../assets/shenlin.jpg') center/cover no-repeat;
  position:relative;
  display:flex;
  align-items:center;
  justify-content:center;
}
.welcome-section::before{
  content:'';
  position:absolute;
  inset:0;
  background:linear-gradient(45deg,rgba(68,91,83,.4),rgba(137,171,158,.3));
}
.welcome-content{
  position:relative;
  text-align:center;
  color:#fff;
  z-index:2;
  padding:0 20px; /* 增加内边距避免内容溢出 */
}
.welcome-content h1{
  font-size:26px; /* 缩小标题 */
  margin-bottom:12px;
  font-weight:600;
  text-shadow:0 2px 8px rgba(0,0,0,.25);
}
.welcome-content p{
  font-size:16px; /* 缩小文字 */
  margin-bottom:24px; /* 减少间距 */
  opacity:.9;
}
.login-btn-secondary{
  background:transparent;
  border:2px solid #fff;
  color:#fff;
  padding:10px 24px; /* 缩小按钮内边距 */
  border-radius:20px; /* 按比例调整圆角 */
  font-size:15px; /* 缩小文字 */
  font-weight:500;
  cursor:pointer;
  transition:all .3s;
}
.login-btn-secondary:hover{
  background:#fff;
  color:#445b53;
  transform:translateY(-2px);
}

/* SVG装饰 */
.svg-decoration{
  position:absolute;
  bottom:-40px;
  right:-40px;
  width:160px; /* 缩小SVG */
  height:160px;
  opacity:.1;
  z-index:1;
}

/* -------------- 响应式设计 -------------- */
@media (max-width:768px){
  .register-card{flex-direction:column; max-width:500px;}
  .form-section{padding:30px 25px;}
  .welcome-section{flex:0 0 180px;order:-1;}
  .form-header h2{font-size:22px;}
  .welcome-content h1{font-size:22px;}
}
@media (max-width:480px){
  .register-card{border-radius:16px; max-width:100%;}
  .form-section{padding:25px 15px;}
  .welcome-section{flex:0 0 140px;}
  .welcome-content h1{font-size:18px;}
  .welcome-content p{font-size:14px;}
  :deep(.el-input__inner){font-size:13px;height:38px;line-height:38px;}
  .register-btn{height:40px;font-size:15px;}
}

/* 错误提示 */
:deep(.el-form-item__error){
  color:#e74c3c;
  font-size:12px;
  padding-top:4px;
}
</style>
