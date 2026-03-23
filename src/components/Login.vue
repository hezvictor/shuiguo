<template>
  <div class="container">
    <div class="main">
        <!-- 整个注册盒子 -->
      <div class="loginbox">
          <!-- 左侧的注册盒子 -->
          <div class="loginbox-in">
          <!-- 添加登录标题 -->
          <div class="login-title">登录</div>
          
          <div class="userbox"> 
           <el-input class="user" id="user" v-model="name" placeholder="请输入用户名">
             <template #prefix>
               <el-icon><User /></el-icon>
             </template>
           </el-input>
           </div>
          <br>
          <div class="pwdbox">
           <el-input class="pwd" id="password" v-model="pwd" type="password" placeholder="请输入密码">
             <template #prefix>
               <el-icon><Lock /></el-icon>
             </template>
           </el-input>
           </div>
          <br>
          
          <!-- 添加忘记密码链接 -->
          <div class="log-box">
            <span class="register_btn" @click="forgotPassword">忘记密码</span>
          </div>
          
          <br>
          <!-- 修改登录按钮 -->
          <button type="primary" class="login_btn" @click="login">登录</button>
          
          <!-- 添加注册链接 -->
          <div class="register-link">
            <span class="register_btn" @click="goToRegister">若无账号请点击注册</span>
          </div>
     </div>
 
        <!-- 右侧的注册盒子 -->
         <div class="background">
            <div class="title">Welcome to WH System Management Center</div>
        </div>

      </div>
    </div>
  </div>
</template>


<script>
import { User, Lock } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { login, getCurrentUserInfo, setToken, setUserId, setUserName } from '@/utils/auth'

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
    async login() {
      if (!this.name || !this.pwd) {
        ElMessage.warning('请输入用户名和密码')
        return
      }
      const params = { username: this.name, password: this.pwd }
      const loading = this.$loading({ lock: true, text: '登录中...' })
      try {
        const res = await login(params)
        loading.close()
        if (res.status === 'success') {
          // 获取用户信息并存储
          const userInfoRes = await getCurrentUserInfo()
          if (userInfoRes) {
            setUserId(userInfoRes.id)
            setUserName(userInfoRes.username)
            localStorage.setItem('userInfo', JSON.stringify(userInfoRes))
            setToken('logged_in') // 模拟 token，用于路由守卫
          }
          ElMessage.success('登录成功')
          this.$router.push('/dashboard')
        } else {
          ElMessage.error(res.error || '登录失败')
        }
      } catch (err) {
        loading.close()
        ElMessage.error('登录失败，请稍后重试')
      }
    },
    forgotPassword() {
      ElMessage.info('忘记密码功能尚未实现')
    },
    goToRegister() {
      this.$router.push('/register')
    }
  }
}
</script>

<style scoped>
/* ==========================================================
   响应式登录页 - 缩小尺寸版本
   1. 减小整体登录框大小
   2. 调整内边距和元素尺寸保持比例
   3. 保持原有设计风格和响应式特性
   ========================================================== */

/* -------------- 基础 -------------- */
.container{
  min-height:100vh;
  display:flex;
  align-items:center;
  justify-content:center;
  padding:20px;
  background:linear-gradient(135deg,#e8f5e8 0%,#b8dcc0 100%);
}
.main{
  width:100%;
  max-width:750px; /* 缩小整体最大宽度 */
}

/* -------------- 登录卡片 -------------- */
.loginbox{
  display:flex;
  width:100%;
  background:rgba(255,255,255,.75);
  border-radius:20px; /* 略微减小圆角 */
  box-shadow:0 8px 32px rgba(31,38,135,.18);
  overflow:hidden;
  backdrop-filter:blur(12px);
  -webkit-backdrop-filter:blur(12px);
  border:1px solid rgba(255,255,255,.3);
}

/* 左侧表单区 - 缩小宽度和内边距 */
.loginbox-in{
  width:32%; /* 缩小左侧表单宽度比例 */
  padding:40px 35px; /* 减小内边距 */
  display:flex;
  flex-direction:column;
  justify-content:center;
}

/* 登录标题样式 - 缩小尺寸 */
.login-title {
  font-size: 26px; /* 减小标题大小 */
  font-weight: bold;
  color: #445b53;
  text-align: center;
  margin-bottom: 30px; /* 减小底部间距 */
  letter-spacing: 2px;
  position: relative;
}

.login-title::after {
  content: '';
  position: absolute;
  bottom: -10px; /* 调整下划线位置 */
  left: 50%;
  transform: translateX(-50%);
  width: 40px; /* 缩小下划线 */
  height: 2.5px;
  background: linear-gradient(90deg, #5f8276 0%, #89ab9e 100%);
  border-radius: 3px;
}

/* 右侧欢迎区 - 调整文字大小 */
.background{
  flex:1;
  background:url('../assets/shenlin.jpg') center/cover no-repeat;
  position:relative;
}
.background::before{
  content:'';
  position:absolute;
  inset:0;
  background:linear-gradient(45deg,rgba(68,91,83,.4),rgba(137,171,158,.3));
}
.title{
  position:relative;
  font-size:26px; /* 减小右侧标题 */
  font-weight:bold;
  color:#fff;
  text-shadow:0 2px 8px rgba(0,0,0,.25);
  text-align:center;
  padding:30px; /* 减小内边距 */
  line-height:1.4;
}

/* -------------- 输入框 - 缩小尺寸 -------------- */
.userbox,.pwdbox{
  margin-bottom:20px; /* 减小间距 */
}
/* 深度选择器覆盖 Element-Plus 样式 */
:deep(.el-input__inner){
  background:transparent;
  border:0;
  border-bottom:2px solid rgba(68,91,83,.35);
  color:#445b53;
  font-size:15px; /* 减小字体 */
  padding-left:32px !important;
  height:42px !important; /* 减小输入框高度 */
  line-height:42px !important;
  border-radius:0;
  transition:border-color .3s;
}
:deep(.el-input__inner:focus){
  border-color:#5f8276;
}
:deep(.el-input__prefix){
  left:4px;
  color:#5f8276;
}
/* 自动填充反色 */
input:-webkit-autofill{
  -webkit-box-shadow:0 0 0 1000px rgba(255,255,255,.9) inset;
  -webkit-text-fill-color:#445b53;
}

/* -------------- 按钮 - 缩小尺寸 -------------- */
.login_btn{
  width:100%;
  height:42px; /* 减小按钮高度 */
  border:0;
  border-radius:21px; /* 保持比例的圆角 */
  background:linear-gradient(90deg,#5f8276 0%,#89ab9e 100%);
  color:#fff;
  font-size:16px; /* 减小字体 */
  font-weight:bold;
  letter-spacing:1.5px;
  cursor:pointer;
  transition:all .3s;
}
.login_btn:hover{
  transform:translateY(-2px);
  box-shadow:0 6px 20px rgba(95,130,118,.35);
}
.login_btn:active{
  transform:translateY(0);
}

/* 文字链 - 调整位置和大小 */
.log-box{
  text-align:right;
  margin:-5px 0 10px; /* 调整间距 */
}
.register_btn{
  font-size:12px; /* 减小字体 */
  color:#5f8276;
  cursor:pointer;
  text-decoration:underline;
}
.register_btn:hover{
  color:#445b53;
}

/* 注册链接 - 优化位置 */
.register-link {
  margin-top: 40px; /* 减小顶部距离 */
  text-align: center; /* 居中显示 */
  margin-left: 0; /* 移除左侧偏移 */
}

/* -------------- 响应式 -------------- */
@media (max-width:768px){
  .loginbox{flex-direction:column;}
  .loginbox-in{width:100%;padding:30px 25px;}
  .login-title {
    font-size: 24px;
    margin-bottom: 25px;
  }
  .background{height:140px;}
  .title{font-size:22px;padding:15px;}
}
@media (max-width:480px){
  .loginbox{border-radius:14px;}
  .loginbox-in{padding:25px 15px;}
  .login-title {
    font-size: 22px;
    margin-bottom: 20px;
  }
  .title{font-size:18px;}
  .register-link {
    margin-top: 30px;
  }
}
</style>
