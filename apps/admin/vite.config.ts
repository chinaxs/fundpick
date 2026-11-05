import { fileURLToPath, URL } from 'node:url'

import { defineConfig, loadEnv } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, process.cwd(), '')

  return {
    plugins: [vue(), vueDevTools()],
    resolve: {
      alias: {
        '@': fileURLToPath(new URL('./src', import.meta.url)),
      },
    },
    css: {
      preprocessorOptions: {
        scss: {
          // 全局变量，组件内可直接使用
          additionalData: `@use "@/styles/variables.scss" as *;`,
        },
      },
    },
    server: {
      port: Number(env.VITE_PORT ?? 5174),
      host: true,
      proxy: {
        // 开发环境把 /api 转发到 FastAPI，避免跨域
        '/api': {
          target: env.VITE_PROXY_TARGET || 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
      },
    },
    build: {
      outDir: 'dist',
      sourcemap: mode !== 'production',
      chunkSizeWarningLimit: 1200,
      rollupOptions: {
        output: {
          // 按体积拆分，避免单个 chunk 过大影响首屏
          manualChunks(id: string) {
            if (!id.includes('node_modules')) return undefined
            if (id.includes('element-plus')) return 'element-plus'
            if (/node_modules\/(@vue|vue|vue-router|pinia)\//.test(id)) return 'vue'
            return undefined
          },
        },
      },
    },
  }
})
