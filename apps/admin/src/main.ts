import { createApp, type Component } from 'vue'
import { createPinia } from 'pinia'
import ElementPlus from 'element-plus'
import zhCn from 'element-plus/es/locale/lang/zh-cn'
import * as ElementPlusIconsVue from '@element-plus/icons-vue'

import 'element-plus/dist/index.css'
import './styles/index.scss'

import App from './App.vue'
import router from './router'

const app = createApp(App)

// 全量注册图标，模板里可直接写 <el-icon><User /></el-icon>
for (const [key, component] of Object.entries(ElementPlusIconsVue)) {
  app.component(key, component as Component)
}

app.use(createPinia())
app.use(ElementPlus, { locale: zhCn })
app.use(router)

app.mount('#app')
