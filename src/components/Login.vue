<template>
  <div class="container">
    <div class="main">
      <div class="loginbox">
        <div class="loginbox-in">
          <div class="login-title">登录</div>

          <div class="userbox">
            <el-input
              id="user"
              v-model="name"
              class="user"
              placeholder="请输入用户名"
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><User /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="pwdbox">
            <el-input
              id="password"
              v-model="pwd"
              class="pwd"
              type="password"
              show-password
              placeholder="请输入密码"
              @keyup.enter="handleLogin"
            >
              <template #prefix>
                <el-icon><Lock /></el-icon>
              </template>
            </el-input>
          </div>

          <div class="log-box">
            <span class="register_btn" @click="forgotPassword">忘记密码</span>
          </div>

          <button type="button" class="login_btn" @click="handleLogin">登录</button>

          <div class="register-link">
            <span class="register_btn" @click="goToRegister">若无账号请点击注册</span>
          </div>
        </div>

        <div class="background">
          <div class="title">Welcome to Fruit System Management Center</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script>
import { User, Lock } from '@element-plus/icons-vue'
import { ElLoading, ElMessage } from 'element-plus'
import { login as loginApi, getCurrentUserInfo, storeLoginState } from '@/utils/auth'

function resolveLoginError(error) {
  return (
    error?.response?.data?.error ||
    error?.response?.data?.detail ||
    error?.message ||
    '登录失败，请稍后重试'
  )
}

export default {
  name: 'Login',
  components: { User, Lock },
  data() {
    return {
      name: '',
      pwd: ''
    }
  },
  methods: {
    async handleLogin() {
      if (!this.name || !this.pwd) {
        ElMessage.warning('请输入用户名和密码')
        return
      }

      const loading = ElLoading.service({ lock: true, text: '登录中...' })

      try {
        const res = await loginApi({ username: this.name, password: this.pwd })

        if (!res || res.status !== 'success') {
          ElMessage.error(res?.error || '登录失败')
          return
        }

        let currentUser = res.user || null
        if (currentUser) {
          storeLoginState(currentUser)
        }

        try {
          const userInfo = await getCurrentUserInfo()
          if (userInfo) {
            currentUser = userInfo
            storeLoginState(userInfo)
          }
        } catch (_error) {
          if (!currentUser) {
            throw _error
          }
        }

        ElMessage.success('登录成功')
        await this.$router.replace(res.redirect || '/console')
      } catch (error) {
        ElMessage.error(resolveLoginError(error))
      } finally {
        loading.close()
      }
    },
    forgotPassword() {
      ElMessage.info('忘记密码功能暂未开放，请联系管理员重置密码')
    },
    goToRegister() {
      this.$router.push('/register')
    }
  }
}
</script>

<style scoped>
.container {
  min-height: 100vh;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  background: linear-gradient(135deg, #e8f5e8 0%, #b8dcc0 100%);
}

.main {
  width: 100%;
  max-width: 750px;
}

.loginbox {
  display: flex;
  width: 100%;
  background: rgba(255, 255, 255, 0.75);
  border-radius: 20px;
  box-shadow: 0 8px 32px rgba(31, 38, 135, 0.18);
  overflow: hidden;
  backdrop-filter: blur(12px);
  -webkit-backdrop-filter: blur(12px);
  border: 1px solid rgba(255, 255, 255, 0.3);
}

.loginbox-in {
  width: 32%;
  padding: 40px 35px;
  display: flex;
  flex-direction: column;
  justify-content: center;
}

.login-title {
  font-size: 26px;
  font-weight: bold;
  color: #445b53;
  text-align: center;
  margin-bottom: 30px;
  letter-spacing: 2px;
  position: relative;
}

.login-title::after {
  content: '';
  position: absolute;
  bottom: -10px;
  left: 50%;
  transform: translateX(-50%);
  width: 40px;
  height: 2.5px;
  background: linear-gradient(90deg, #5f8276 0%, #89ab9e 100%);
  border-radius: 3px;
}

.background {
  flex: 1;
  background: url('../assets/shenlin.jpg') center / cover no-repeat;
  position: relative;
}

.background::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(45deg, rgba(68, 91, 83, 0.4), rgba(137, 171, 158, 0.3));
}

.title {
  position: relative;
  font-size: 26px;
  font-weight: bold;
  color: #fff;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.25);
  text-align: center;
  padding: 30px;
  line-height: 1.4;
}

.userbox,
.pwdbox {
  margin-bottom: 20px;
}

:deep(.el-input__inner) {
  background: transparent;
  border: 0;
  border-bottom: 2px solid rgba(68, 91, 83, 0.35);
  color: #445b53;
  font-size: 15px;
  padding-left: 32px !important;
  height: 42px !important;
  line-height: 42px !important;
  border-radius: 0;
  transition: border-color 0.3s;
}

:deep(.el-input__inner:focus) {
  border-color: #5f8276;
}

:deep(.el-input__prefix) {
  left: 4px;
  color: #5f8276;
}

input:-webkit-autofill {
  -webkit-box-shadow: 0 0 0 1000px rgba(255, 255, 255, 0.9) inset;
  -webkit-text-fill-color: #445b53;
}

.login_btn {
  width: 100%;
  height: 42px;
  border: 0;
  border-radius: 21px;
  background: linear-gradient(90deg, #5f8276 0%, #89ab9e 100%);
  color: #fff;
  font-size: 16px;
  font-weight: bold;
  letter-spacing: 1.5px;
  cursor: pointer;
  transition: all 0.3s;
}

.login_btn:hover {
  transform: translateY(-2px);
  box-shadow: 0 6px 20px rgba(95, 130, 118, 0.35);
}

.login_btn:active {
  transform: translateY(0);
}

.log-box {
  text-align: right;
  margin: -5px 0 18px;
}

.register_btn {
  font-size: 12px;
  color: #5f8276;
  cursor: pointer;
  text-decoration: underline;
}

.register_btn:hover {
  color: #445b53;
}

.register-link {
  margin-top: 40px;
  text-align: center;
}

@media (max-width: 768px) {
  .loginbox {
    flex-direction: column;
  }

  .loginbox-in {
    width: 100%;
    padding: 30px 25px;
  }

  .login-title {
    font-size: 24px;
    margin-bottom: 25px;
  }

  .background {
    height: 140px;
  }

  .title {
    font-size: 22px;
    padding: 15px;
  }
}

@media (max-width: 480px) {
  .loginbox {
    border-radius: 14px;
  }

  .loginbox-in {
    padding: 25px 15px;
  }

  .login-title {
    font-size: 22px;
    margin-bottom: 20px;
  }

  .title {
    font-size: 18px;
  }

  .register-link {
    margin-top: 30px;
  }
}
</style>
