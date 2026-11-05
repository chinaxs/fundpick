<template>
  <footer class="footer">
    <div class="container footer__inner">
      <div>
        <div class="footer__brand">Study 门户</div>
        <p class="footer__desc">
          基于 Nuxt 构建的门户站点，内容由后台管理系统统一维护，服务端渲染、SEO 友好。
        </p>
      </div>

      <div class="footer__links">
        <div class="footer__col">
          <div class="footer__title">站点</div>
          <NuxtLink to="/">首页</NuxtLink>
          <NuxtLink to="/articles">资讯</NuxtLink>
          <NuxtLink to="/about">关于</NuxtLink>
        </div>
        <div class="footer__col">
          <div class="footer__title">资源</div>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">接口文档</a>
          <a href="http://localhost:5174" target="_blank" rel="noreferrer">管理后台</a>
        </div>
      </div>
    </div>

    <div class="footer__bottom">
      <div class="container">© {{ new Date().getFullYear() }} Study. All rights reserved.</div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  margin-top: 64px;
  color: #cbd5e0;
  background: #1a202c;
}

.footer__inner {
  display: flex;
  flex-wrap: wrap;
  gap: 40px;
  justify-content: space-between;
  padding: 48px 20px 32px;
}

.footer__brand {
  margin-bottom: 10px;
  font-size: 18px;
  font-weight: 700;
  color: #fff;
}

.footer__desc {
  max-width: 380px;
  margin: 0;
  font-size: 14px;
  line-height: 1.8;
  color: #a0aec0;
}

.footer__links {
  display: flex;
  gap: 64px;
}

.footer__col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 14px;
}

.footer__title {
  margin-bottom: 4px;
  font-weight: 600;
  color: #fff;
}

.footer__col a {
  color: #a0aec0;
  transition: color 0.15s ease;
}

.footer__col a:hover {
  color: #fff;
}

.footer__bottom {
  padding: 16px 0;
  font-size: 13px;
  color: #718096;
  border-top: 1px solid #2d3748;
}
</style>
