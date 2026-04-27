<template>
  <div class="register-container">
    <div class="bg-decoration">
      <div class="circle c1"></div>
      <div class="circle c2"></div>
      <div class="circle c3"></div>
    </div>

    <div class="register-card">
      <div class="form-section">
        <div class="form-header">
          <h2>创建您的账号</h2>
          <p>注册后即可进入水果识别与检测系统。</p>
        </div>

        <el-form
          ref="registerForm"
          :model="form"
          :rules="rules"
          class="register-form"
          status-icon
          @submit.prevent="handleRegister"
        >
          <el-form-item prop="username">
            <el-input
              v-model="form.username"
              placeholder="请输入用户名"
              size="large"
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="email">
            <el-input
              v-model="form.email"
              placeholder="请输入邮箱地址"
              size="large"
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><Message /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="password">
            <el-input
              v-model="form.password"
              type="password"
              show-password
              placeholder="请输入密码（至少 6 位）"
              size="large"
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item prop="confirmPassword">
            <el-input
              v-model="form.confirmPassword"
              type="password"
              show-password
              placeholder="请再次输入密码"
              size="large"
              @keyup.enter="handleRegister"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </el-form-item>

          <el-form-item>
            <el-button
              type="primary"
              class="register-btn"
              size="large"
              :loading="isLoading"
              @click="handleRegister"
            >
              {{ isLoading ? '注册中...' : '立即注册' }}
            </el-button>
          </el-form-item>
        </el-form>

        <div class="login-link">
          已有账号？
          <span class="link-text" @click="goToLogin">立即登录</span>
        </div>
      </div>

      <div class="welcome-section">
        <div class="welcome-content">
          <h1>Welcome Back</h1>
          <p>已有账号的话，直接返回登录页即可继续使用系统。</p>
          <el-button class="login-btn-secondary" @click="goToLogin">
            去登录
          </el-button>
        </div>

        <div class="svg-decoration">
          <svg viewBox="0 0 200 200" xmlns="http://www.w3.org/2000/svg">
            <path
              fill="#FF0066"
              d="M45.2,-58.1C58.1,-46.3,67.3,-30.1,70.8,-12.3C74.3,5.5,72.1,25,63.9,40.9C55.7,56.8,41.5,69.1,25.1,74.9C8.7,80.7,-10,79.9,-26.7,73.5C-43.4,67.1,-58.1,55,-67.1,39.1C-76.1,23.2,-79.5,3.4,-75.9,-13.9C-72.3,-31.3,-61.7,-45.9,-47.9,-57.3C-34.1,-68.7,-17.1,-76.9,0.3,-77.2C17.6,-77.5,35.1,-69.9,45.2,-58.1Z"
              transform="translate(100 100)"
            />
          </svg>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { User, Lock, Message } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { register as registerApi, storeLoginState } from '@/utils/auth'

export default {
  name: 'Register',
  components: { User, Lock, Message },
  data() {
    return {
      form: {
        username: '',
        email: '',
        password: '',
        confirmPassword: ''
      },
      rules: {
        username: [
          { required: true, message: '请输入用户名', trigger: 'blur' },
          { min: 3, max: 30, message: '用户名长度需为 3-30 位', trigger: 'blur' }
        ],
        email: [
          { required: true, message: '请输入邮箱地址', trigger: 'blur' },
          { type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }
        ],
        password: [
          { required: true, message: '请输入密码', trigger: 'blur' },
          { min: 6, message: '密码长度至少 6 位', trigger: 'blur' }
        ],
        confirmPassword: [{ required: true, message: '请再次输入密码', trigger: 'blur' }]
      },
      isLoading: false
    }
  },
  methods: {
    async handleRegister() {
      const valid = await this.$refs.registerForm?.validate().catch(() => false)
      if (!valid) {
        return
      }

      if (this.form.password !== this.form.confirmPassword) {
        ElMessage.error('两次输入的密码不一致')
        return
      }

      this.isLoading = true
      try {
        const res = await registerApi({
          username: this.form.username,
          password: this.form.password,
          email: this.form.email
        })

        if (res?.status === 'success') {
          storeLoginState(res.user || null)
          ElMessage.success('注册成功，正在进入系统...')
          await this.$router.push('/console')
          return
        }

        ElMessage.error(res?.error || '注册失败')
      } catch (error) {
        ElMessage.error(error?.response?.data?.error || '注册失败，请检查网络连接')
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
.register-container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: linear-gradient(135deg, #e8f5e8 0%, #b8dcc0 100%);
  position: relative;
  overflow: hidden;
}

.bg-decoration {
  position: absolute;
  inset: 0;
  overflow: hidden;
  z-index: 0;
}

.circle {
  position: absolute;
  border-radius: 50%;
  background: rgba(255, 255, 255, 0.1);
  animation: float 6s ease-in-out infinite;
}

.c1 {
  width: 80px;
  height: 80px;
  top: 20%;
  left: 10%;
  animation-delay: 0s;
}

.c2 {
  width: 120px;
  height: 120px;
  top: 60%;
  right: 10%;
  animation-delay: 2s;
}

.c3 {
  width: 60px;
  height: 60px;
  bottom: 20%;
  left: 80%;
  animation-delay: 4s;
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0);
  }
  50% {
    transform: translateY(-20px);
  }
}

.register-card {
  display: flex;
  width: 100%;
  max-width: 780px;
  background: rgba(255, 255, 255, 0.75);
  border-radius: 24px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.18);
  overflow: hidden;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.3);
  position: relative;
  z-index: 1;
}

.form-section {
  flex: 1;
  padding: 40px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.form-header {
  text-align: center;
  margin-bottom: 24px;
}

.form-header h2 {
  margin: 0 0 10px;
  color: #445b53;
  font-size: 24px;
  font-weight: 600;
  letter-spacing: 1px;
}

.form-header p {
  margin: 0;
  color: #5f8276;
  font-size: 15px;
}

.register-form {
  width: 100%;
  max-width: 320px;
  margin: 0 auto;
}

:deep(.el-form-item) {
  margin-bottom: 18px;
}

:deep(.el-input__wrapper) {
  background: transparent;
  border: 0;
  border-bottom: 2px solid rgba(68, 91, 83, 0.35);
  border-radius: 0;
  padding: 8px 0;
  transition: border-color 0.3s;
}

:deep(.el-input__wrapper:hover) {
  border-color: #5f8276;
}

:deep(.el-input__wrapper.is-focus) {
  border-color: #5f8276;
  box-shadow: 0 2px 0 0 #5f8276;
}

:deep(.el-input__inner) {
  height: 40px;
  line-height: 40px;
  font-size: 15px;
  color: #445b53;
  padding-left: 32px !important;
}

:deep(.el-input__prefix) {
  left: 4px;
  color: #5f8276;
  font-size: 16px;
}

input:-webkit-autofill {
  -webkit-box-shadow: 0 0 0 1000px rgba(255, 255, 255, 0.9) inset;
  -webkit-text-fill-color: #445b53;
  caret-color: #445b53;
}

.register-btn {
  width: 100%;
  height: 42px;
  border: 0;
  border-radius: 21px;
  background: linear-gradient(90deg, #5f8276 0%, #89ab9e 100%);
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  letter-spacing: 2px;
  cursor: pointer;
  transition: all 0.3s;
  margin-top: 6px;
}

.register-btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(95, 130, 118, 0.35);
}

.register-btn:active {
  transform: translateY(0);
}

.login-link {
  text-align: center;
  margin-top: 16px;
  color: #5f8276;
  font-size: 13px;
}

.link-text {
  color: #445b53;
  cursor: pointer;
  text-decoration: underline;
  font-weight: 500;
  transition: color 0.3s;
}

.link-text:hover {
  color: #2c3e50;
}

.welcome-section {
  flex: 0 0 35%;
  background: url('../assets/shenlin.jpg') center / cover no-repeat;
  position: relative;
  display: flex;
  align-items: center;
  justify-content: center;
}

.welcome-section::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(45deg, rgba(68, 91, 83, 0.4), rgba(137, 171, 158, 0.3));
}

.welcome-content {
  position: relative;
  text-align: center;
  color: #fff;
  z-index: 2;
  padding: 0 20px;
}

.welcome-content h1 {
  font-size: 26px;
  margin-bottom: 12px;
  font-weight: 600;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
}

.welcome-content p {
  font-size: 16px;
  margin-bottom: 24px;
  opacity: 0.9;
}

.login-btn-secondary {
  background: transparent;
  border: 2px solid #fff;
  color: #fff;
  padding: 10px 24px;
  border-radius: 20px;
  font-size: 15px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.3s;
}

.login-btn-secondary:hover {
  background: #fff;
  color: #445b53;
  transform: translateY(-2px);
}

.svg-decoration {
  position: absolute;
  bottom: -40px;
  right: -40px;
  width: 160px;
  height: 160px;
  opacity: 0.1;
  z-index: 1;
}

@media (max-width: 768px) {
  .register-card {
    flex-direction: column;
    max-width: 500px;
  }

  .form-section {
    padding: 30px 25px;
  }

  .welcome-section {
    flex: 0 0 180px;
    order: -1;
  }

  .form-header h2 {
    font-size: 22px;
  }

  .welcome-content h1 {
    font-size: 22px;
  }
}

@media (max-width: 480px) {
  .register-card {
    border-radius: 16px;
    max-width: 100%;
  }

  .form-section {
    padding: 25px 15px;
  }

  .welcome-section {
    flex: 0 0 140px;
  }

  .welcome-content h1 {
    font-size: 18px;
  }

  .welcome-content p {
    font-size: 14px;
  }

  :deep(.el-input__inner) {
    font-size: 13px;
    height: 38px;
    line-height: 38px;
  }

  .register-btn {
    height: 40px;
    font-size: 15px;
  }
}

:deep(.el-form-item__error) {
  color: #e74c3c;
  font-size: 12px;
  padding-top: 4px;
}
</style>
