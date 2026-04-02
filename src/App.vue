<template>
  <div id="app">
    <RouterView />
  </div>
</template>

<script>
export default {
  name: 'App'
}
</script>

<style>
body {
  margin: 0;
  padding: 0;
  min-height: 100vh;
  background: linear-gradient(135deg, #e8f5e8 0%, #d4edda 25%, #c3e6cb 50%, #b8dcc0 75%, #a8d1b5 100%);
  background-attachment: fixed;
}

body::before {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image:
    radial-gradient(circle at 20% 80%, rgba(120, 190, 150, 0.1) 0%, transparent 50%),
    radial-gradient(circle at 80% 20%, rgba(90, 160, 120, 0.08) 0%, transparent 50%),
    radial-gradient(circle at 40% 40%, rgba(140, 200, 160, 0.06) 0%, transparent 50%);
  pointer-events: none;
  z-index: -2;
}

body::after {
  content: '';
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100%;
  background-image: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="20" cy="20" r="2" fill="%23a8d1b5" opacity="0.3"/><circle cx="80" cy="30" r="1.5" fill="%2378be96" opacity="0.2"/><circle cx="60" cy="70" r="2.5" fill="%23c3e6cb" opacity="0.25"/><circle cx="30" cy="80" r="1" fill="%2390a080" opacity="0.15"/></svg>');
  background-size: 200px 200px;
  animation: float 20s ease-in-out infinite;
  pointer-events: none;
  z-index: -1;
}

@keyframes float {
  0%,
  100% {
    transform: translateY(0) rotate(0deg);
  }
  25% {
    transform: translateY(-10px) rotate(90deg);
  }
  50% {
    transform: translateY(-5px) rotate(180deg);
  }
  75% {
    transform: translateY(-15px) rotate(270deg);
  }
}

#app {
  font-family: Avenir, Helvetica, Arial, sans-serif;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
  text-align: center;
  color: #2c3e50;
  min-height: 100vh;
  position: relative;
}
</style>
