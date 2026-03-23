<template>
  <div class="history-container">
    <h1>检测历史(可查看...)</h1>
    <p>在此页面您可以查看所有历史检测记录。</p>
    <!-- 检测历史功能将在这里实现 -->
  </div>
</template>

<script>
import { defineComponent } from 'vue'
import { getToken, getUserId } from '@/utils/auth'  // 导入token处理函数

export default defineComponent({
  name: 'DetectionHistoryView'
})
console.log("当前登录用户的token为："+getToken());
console.log("当前登录用户的userid为："+getUserId());
</script>

<style scoped>
.history-container {
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