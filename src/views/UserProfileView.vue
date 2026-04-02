<template>
  <div class="profile-container">
    <el-row :gutter="20">
      <el-col :span="24">
        <div class="profile-header">
          <h1>个人中心</h1>
          <p>管理您的个人信息和账户安全设置。</p>
        </div>
      </el-col>
    </el-row>

    <el-row :gutter="20">
      <el-col :span="16">
        <el-card class="info-card" shadow="hover">
          <template #header>
            <div class="card-header">
              <span>个人信息</span>
              <el-button
                v-if="!isEditing"
                type="primary"
                size="small"
                @click="showEditDialog"
              >
                编辑信息
              </el-button>
            </div>
          </template>

          <div v-if="!isEditing && userInfo" class="user-info">
            <el-descriptions :column="1" border>
              <el-descriptions-item label="用户 ID">{{ userInfo.id }}</el-descriptions-item>
              <el-descriptions-item label="用户名">{{ userInfo.username }}</el-descriptions-item>
              <el-descriptions-item label="昵称">
                {{ userInfo.first_name || '未设置' }}
              </el-descriptions-item>
              <el-descriptions-item label="邮箱">
                {{ userInfo.email || '未设置' }}
              </el-descriptions-item>
            </el-descriptions>
          </div>

          <div v-if="isEditing" class="edit-form">
            <el-form
              ref="editFormRef"
              :model="editForm"
              :rules="editRules"
              label-width="80px"
              label-position="left"
            >
              <el-form-item label="用户名" prop="username">
                <el-input v-model="editForm.username" disabled></el-input>
              </el-form-item>
              <el-form-item label="昵称" prop="first_name">
                <el-input v-model="editForm.first_name"></el-input>
              </el-form-item>
              <el-form-item label="邮箱" prop="email">
                <el-input v-model="editForm.email"></el-input>
              </el-form-item>
              <el-form-item>
                <el-button type="primary" :loading="editLoading" @click="submitEditForm">
                  保存
                </el-button>
                <el-button @click="cancelEdit">取消</el-button>
              </el-form-item>
            </el-form>
          </div>
        </el-card>
      </el-col>

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
              <el-button type="primary" size="small" @click="showPasswordDialog">
                修改密码
              </el-button>
            </div>
          </div>
        </el-card>
      </el-col>
    </el-row>

    <el-dialog v-model="passwordDialogVisible" title="修改密码" width="400px">
      <el-form
        ref="passwordFormRef"
        :model="passwordForm"
        :rules="passwordRules"
        label-width="90px"
      >
        <el-form-item label="旧密码" prop="oldPassword">
          <el-input v-model="passwordForm.oldPassword" type="password" show-password></el-input>
        </el-form-item>
        <el-form-item label="新密码" prop="newPassword">
          <el-input v-model="passwordForm.newPassword" type="password" show-password></el-input>
        </el-form-item>
        <el-form-item label="确认密码" prop="confirmPassword">
          <el-input
            v-model="passwordForm.confirmPassword"
            type="password"
            show-password
          ></el-input>
        </el-form-item>
      </el-form>
      <template #footer>
        <el-button @click="passwordDialogVisible = false">取消</el-button>
        <el-button type="primary" :loading="passwordLoading" @click="submitPasswordChange">
          确定
        </el-button>
      </template>
    </el-dialog>
  </div>
</template>

<script>
import { defineComponent, ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { ElMessage } from 'element-plus'
import {
  changePassword,
  clearLoginState,
  getCurrentUserInfo,
  storeLoginState,
  updateUserInfo
} from '@/utils/auth'

export default defineComponent({
  name: 'UserProfileView',
  setup() {
    const router = useRouter()

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
      email: [{ type: 'email', message: '请输入正确的邮箱地址', trigger: ['blur', 'change'] }]
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
        { min: 6, message: '密码长度至少 6 位', trigger: 'blur' }
      ],
      confirmPassword: [
        { required: true, message: '请确认新密码', trigger: 'blur' },
        {
          validator: (_rule, value, callback) => {
            if (value !== passwordForm.value.newPassword) {
              callback(new Error('两次输入的密码不一致'))
              return
            }
            callback()
          },
          trigger: ['blur', 'change']
        }
      ]
    }

    const syncEditForm = () => {
      if (!userInfo.value) {
        return
      }

      editForm.value.username = userInfo.value.username
      editForm.value.first_name = userInfo.value.first_name || ''
      editForm.value.email = userInfo.value.email || ''
    }

    const fetchUserInfo = async () => {
      try {
        const res = await getCurrentUserInfo()
        if (!res) {
          ElMessage.error('获取用户信息失败')
          return
        }

        userInfo.value = res
        storeLoginState(res)
        syncEditForm()
      } catch (error) {
        console.error(error)
        ElMessage.error('获取用户信息失败')
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
      const valid = await editFormRef.value?.validate().catch(() => false)
      if (!valid) {
        return
      }

      editLoading.value = true
      try {
        const res = await updateUserInfo({
          first_name: editForm.value.first_name,
          email: editForm.value.email
        })

        if (res?.status === 'success') {
          userInfo.value = res.user
          storeLoginState(res.user)
          syncEditForm()
          isEditing.value = false
          ElMessage.success('个人信息更新成功')
          return
        }

        ElMessage.error(res?.error || '更新失败')
      } catch (_error) {
        ElMessage.error('更新失败，请稍后重试')
      } finally {
        editLoading.value = false
      }
    }

    const showPasswordDialog = () => {
      passwordForm.value = { oldPassword: '', newPassword: '', confirmPassword: '' }
      passwordDialogVisible.value = true
    }

    const submitPasswordChange = async () => {
      const valid = await passwordFormRef.value?.validate().catch(() => false)
      if (!valid) {
        return
      }

      passwordLoading.value = true
      try {
        const res = await changePassword({
          old_password: passwordForm.value.oldPassword,
          new_password: passwordForm.value.newPassword
        })

        if (res?.status === 'success') {
          clearLoginState()
          passwordDialogVisible.value = false
          ElMessage.success('密码修改成功，请重新登录')
          await router.replace('/login')
          return
        }

        ElMessage.error(res?.error || '密码修改失败')
      } catch (_error) {
        ElMessage.error('密码修改失败，请稍后重试')
      } finally {
        passwordLoading.value = false
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

<style scoped>
.profile-container {
  padding: 8px;
}

.profile-header {
  margin-bottom: 20px;
  text-align: left;
}

.profile-header h1 {
  margin: 0 0 8px;
  font-size: 28px;
  color: #304156;
}

.profile-header p {
  margin: 0;
  color: #5f8276;
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.user-info,
.edit-form,
.security-info {
  text-align: left;
}

.security-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

@media (max-width: 768px) {
  .profile-header h1 {
    font-size: 24px;
  }
}
</style>
