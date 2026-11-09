// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  // 只在登录/注册弹窗等局部使用，按需自动引入，不整包进首屏
  modules: ['@element-plus/nuxt'],

  elementPlus: {
    importStyle: 'css',
  },

  // Nuxt 4 默认源码目录即 app/
  srcDir: 'app/',

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    // 服务端私有：SSR 阶段由 Node 直连后端，不受浏览器同源策略约束。
    // 生产可用 NUXT_API_BASE 覆盖（如容器内 http://api:8000/api/v1）。
    apiBase: 'http://127.0.0.1:8000/api/v1',
    public: {
      // 浏览器统一走同源的 /api/v1，由 Nitro 代理转发到后端。
      // 这样页面无论用 localhost 还是 127.0.0.1 打开、端口怎么变，都不会触发跨域。
      apiBase: '/api/v1',
      // 页脚外部入口，生产用环境变量覆盖。文档按消费方拆分，门户只看 portal 那份
      apiDocsUrl: 'http://127.0.0.1:8000/docs/portal',
      adminUrl: 'http://localhost:5174',
    },
  },

  // 反向代理：把浏览器的 /api/v1/** 转发到 FastAPI，避免 CORS
  routeRules: {
    '/api/v1/**': {
      proxy: `${process.env.NUXT_API_BASE || 'http://127.0.0.1:8000/api/v1'}/**`,
    },
  },

  app: {
    head: {
      htmlAttrs: { lang: 'zh-CN' },
      title: '拾贝 FundPick',
      titleTemplate: '%s · 拾贝',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        {
          name: 'description',
          content:
            '拾贝 FundPick：开源基金模拟交易与持仓管理工具，支持基金投资记账、买入卖出记录、净值查询、收益分析与基金筛选。',
        },
        { name: 'format-detection', content: 'telephone=no' },
      ],
      link: [{ rel: 'icon', type: 'image/svg+xml', href: '/favicon.svg' }],
    },
  },

  nitro: {
    compressPublicAssets: true,
  },

  typescript: {
    typeCheck: false,
    strict: true,
  },

  devServer: {
    port: 3000,
  },
})
