// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

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
      title: 'Study 门户',
      titleTemplate: '%s · Study 门户',
      meta: [
        { charset: 'utf-8' },
        { name: 'viewport', content: 'width=device-width, initial-scale=1' },
        {
          name: 'description',
          content:
            'Study 门户网站：产品介绍、行业资讯与解决方案，基于 Nuxt 构建，服务端渲染、SEO 友好。',
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
