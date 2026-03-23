<template>
  <div class="dashboard-container">
    <h1>欢迎来到仪表盘</h1>
    <p>这里是系统的主要控制面板，您可以从侧边栏导航到各个功能模块。</p>
  </div>
</template>

<script>
import { defineComponent } from 'vue'

export default defineComponent({
  name: 'DashboardView'
})
</script>

<style scoped>
.dashboard-container {
  padding: 20px;
  text-align: left;
}

h1 {
  color: #304156;
  font-size: 28px;
  margin-bottom: 20px;
}

p {
  color: #606266;
  font-size: 16px;
}
</style>