<template>
  <footer class="footer">
    <div class="container footer__inner">
      <div class="footer__brand-col">
        <div class="footer__brand">
          <span class="footer__mark">S</span>
          <span>Study 基金</span>
        </div>
        <p class="footer__desc">
          全市场公募基金数据筛选与分析。所有指标基于公开净值计算，排名可追溯、口径可复算。
        </p>
      </div>

      <div class="footer__links">
        <div class="footer__col">
          <div class="footer__title">产品</div>
          <NuxtLink to="/funds">基金筛选</NuxtLink>
          <NuxtLink :to="{ path: '/funds', query: { type: 'index' } }">指数基金</NuxtLink>
          <NuxtLink :to="{ path: '/funds', query: { type: 'bond' } }">债券基金</NuxtLink>
        </div>

        <div class="footer__col">
          <div class="footer__title">内容</div>
          <NuxtLink to="/articles">研报</NuxtLink>
          <NuxtLink to="/about">关于</NuxtLink>
        </div>

        <div class="footer__col">
          <div class="footer__title">资源</div>
          <a href="http://127.0.0.1:8000/docs" target="_blank" rel="noreferrer">接口文档</a>
          <a href="http://localhost:5174" target="_blank" rel="noreferrer">管理后台</a>
        </div>
      </div>
    </div>

    <div class="footer__legal">
      <div class="container footer__legal-inner">
        <span>© {{ new Date().getFullYear() }} Study. All rights reserved.</span>
        <span class="footer__note">数据仅供参考，不构成投资建议</span>
      </div>
    </div>
  </footer>
</template>

<style scoped>
.footer {
  color: #94a3b8;
  background: var(--bg-deep);
}

.footer__inner {
  display: flex;
  flex-wrap: wrap;
  gap: 48px;
  justify-content: space-between;
  padding: 56px 24px 40px;
}

.footer__brand-col {
  max-width: 340px;
}

.footer__brand {
  display: flex;
  gap: 10px;
  align-items: center;
  font-size: 16px;
  font-weight: 700;
  color: #f1f5f9;
}

.footer__mark {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  font-size: 14px;
  font-weight: 700;
  color: #fff;
  background: var(--brand);
  border-radius: 8px;
}

.footer__desc {
  margin: 14px 0 0;
  font-size: 13px;
  line-height: 1.9;
  color: #64748b;
}

.footer__links {
  display: flex;
  flex-wrap: wrap;
  gap: 56px;
}

.footer__col {
  display: flex;
  flex-direction: column;
  gap: 10px;
  font-size: 13px;
}

.footer__title {
  margin-bottom: 2px;
  font-size: 12px;
  font-weight: 600;
  color: #e2e8f0;
  letter-spacing: 0.04em;
}

.footer__col a {
  color: #64748b;
  transition: color 0.15s ease;
}

.footer__col a:hover {
  color: #e2e8f0;
}

.footer__legal {
  border-top: 1px solid rgb(255 255 255 / 6%);
}

.footer__legal-inner {
  display: flex;
  flex-wrap: wrap;
  gap: 12px;
  justify-content: space-between;
  padding: 18px 24px;
  font-size: 12px;
  color: #475569;
}

.footer__note {
  color: #475569;
}

@media (max-width: 720px) {
  .footer__inner {
    gap: 32px;
    padding: 40px 18px 32px;
  }

  .footer__links {
    gap: 36px;
  }
}
</style>
