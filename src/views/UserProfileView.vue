<template>
  <div class="profile-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="profile-header">
          <h1>个人中心</h1>
          <p>管理您的个人信息和账户设置</p>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>个人信息</span>
              <el-button type="primary" size="small" @click="showEditDialog" v-if="!isEditing">编辑信息</el-button>
            </div>
          </template>
          
          <!-- 用户信息展示 -->
          <div class="user-info" v-if="!isEditing && userInfo">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="用户ID">{{ userInfo.id }}</el-descriptions-item>
              <el-descriptions-item label="用户名">{{ userInfo.username }}</el-descriptions-item>
              <el-descriptions-item label="昵称">{{ userInfo.first_name || '未设置' }}</el-descriptions-item>
              <el-descriptions-item label="邮箱">{{ userInfo.email || '未设置' }}</el-descriptions-item>
            </el-descriptions>
          </div>
          
          <!-- 编辑表单（仅支持 first_name 和 email） -->
          <div class="edit-form" v-if="isEditing">
            <el-form 
              :model="editForm" 
              :rules="editRules" 
              ref="editFormRef" 
              label-width="80px"
              label-position="left"
            >
              <el-form-item label="用户名" prop="username">
                <el-input v-model="editForm.username" :disabled="true"></el-input>
              </el-form-item>
              <el-form-item label="昵称" prop="first_name">
                <el-input v-model="editForm.first_name"></el-input>
              </el-form-item>
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="editForm.email"></el-input>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" @click="submitEditForm" :loading="editLoading">保存</el-button>
                <el-button @click="cancelEdit">取消</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-col>
      
      <!-- 安全信息卡片 -->
      <el-col :span="8">
        <el-card class="info-sidebar" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>账户安全</span>
            </div>
          </template>
          <div class="security-info">
            <div class="security-item">
              <span>修改密码</span>
              <el-button type="primary" size="small" @click="showPasswordDialog">修改密码</el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <!-- 修改密码弹窗 -->
    <el-dialog title="修改密码" v-model="passwordDialogVisible" width="400px">
      <el-form :model="passwordForm" :rules="passwordRules" ref="passwordFormRef" label-width="80px">
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input type="password" v-model="passwordForm.oldPassword"></el-input>
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input type="password" v-model="passwordForm.newPassword"></el-input>
        </el-form-item>
        <el-form-item label="确认新密码" prop="confirmPassword">
          <el-input type="password" v-model="passwordForm.confirmPassword"></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" @click="submitPasswordChange" :loading="passwordLoading">确定</el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { defineComponent, ref, onMounted } from 'vue'
import { ElMessage } from 'element-plus'
import { getCurrentUserInfo, updateUserInfo, changePassword } from '@/utils/auth'

export default defineComponent({
  name: 'UserProfileView',
  setup() {
    const userInfo = ref(null)
    const isEditing = ref(false)
    const editLoading = ref(false)
    const editFormRef = ref(null)
    const passwordDialogVisible = ref(false)
    const passwordLoading = ref(false)
    const passwordFormRef = ref(null)

    const editForm = ref({
      username: '',
      first_name: '',
      email: ''
    })

    const editRules = {
      email: [{ type: 'email', message: '请输入正确的邮箱地址', trigger: 'blur' }]
    }

    const passwordForm = ref({
      oldPassword: '',
      newPassword: '',
      confirmPassword: ''
    })

    const passwordRules = {
      oldPassword: [{ required: true, message: '请输入旧密码', trigger: 'blur' }],
      newPassword: [
        { required: true, message: '请输入新密码', trigger: 'blur' },
        { min: 6, message: '密码长度至少6位', trigger: 'blur' }
      ],
      confirmPassword: [
        { required: true, message: '请确认新密码', trigger: 'blur' },
        { validator: (rule, value, callback) => {
          if (value !== passwordForm.value.newPassword) {
            callback(new Error('两次输入的密码不一致'))
          } else {
            callback()
          }
        }, trigger: 'blur' }
      ]
    }

    const fetchUserInfo = async () => {
      try {
        const res = await getCurrentUserInfo()
        if (res) {
          userInfo.value = res
          syncEditForm()
        } else {
          ElMessage.error('获取用户信息失败')
        }
      } catch (err) {
        console.error(err)
        ElMessage.error('获取用户信息失败')
      }
    }

    const syncEditForm = () => {
      if (userInfo.value) {
        editForm.value.username = userInfo.value.username
        editForm.value.first_name = userInfo.value.first_name || ''
        editForm.value.email = userInfo.value.email || ''
      }
    }

    const showEditDialog = () => {
      isEditing.value = true
      syncEditForm()
    }

    const cancelEdit = () => {
      isEditing.value = false
      syncEditForm()
    }

    const submitEditForm = async () => {
      if (editFormRef.value) {
        await editFormRef.value.validate(async (valid) => {
          if (valid) {
            editLoading.value = true
            try {
              const res = await updateUserInfo({
                first_name: editForm.value.first_name,
                email: editForm.value.email
              })
              if (res.status === 'success') {
                ElMessage.success('个人信息更新成功')
                isEditing.value = false
                await fetchUserInfo()  // 重新获取最新信息
              } else {
                ElMessage.error(res.error || '更新失败')
              }
            } catch (err) {
              ElMessage.error('更新失败')
            } finally {
              editLoading.value = false
            }
          }
        })
      }
    }

    const showPasswordDialog = () => {
      passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
      passwordDialogVisible.value = true
    }

    const submitPasswordChange = async () => {
      if (passwordFormRef.value) {
        await passwordFormRef.value.validate(async (valid) => {
          if (valid) {
            passwordLoading.value = true
            try {
              const res = await changePassword({
                old_password: passwordForm.value.oldPassword,
                new_password: passwordForm.value.newPassword
              })
              if (res.status === 'success') {
                ElMessage.success('密码修改成功，请重新登录')
                setTimeout(() => {
                  window.location.href = '/login'
                }, 2000)
              } else {
                ElMessage.error(res.error || '密码修改失败')
              }
            } catch (err) {
              ElMessage.error('密码修改失败')
            } finally {
              passwordLoading.value = false
              passwordDialogVisible.value = false
            }
          }
        })
      }
    }

    onMounted(() => {
      fetchUserInfo()
    })

    return {
      userInfo,
      isEditing,
      editForm,
      editRules,
      editFormRef,
      editLoading,
      showEditDialog,
      cancelEdit,
      submitEditForm,
      passwordDialogVisible,
      passwordForm,
      passwordRules,
      passwordFormRef,
      passwordLoading,
      showPasswordDialog,
      submitPasswordChange
    }
  }
})
</script>