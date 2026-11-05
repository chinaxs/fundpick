// https://nuxt.com/docs/api/configuration/nuxt-config
export default defineNuxtConfig({
  compatibilityDate: '2025-07-15',
  devtools: { enabled: true },

  // Nuxt 4 默认源码目录即 app/
  srcDir: 'app/',

  css: ['~/assets/css/main.css'],

  runtimeConfig: {
    public: {
      // 服务端渲染与客户端共用；生产环境通过 NUXT_PUBLIC_API_BASE 覆盖
      apiBase: 'http://127.0.0.1:8000/api/v1',
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
