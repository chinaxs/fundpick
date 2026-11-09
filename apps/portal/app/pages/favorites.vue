<script setup lang="ts">
const { isLoggedIn, openAuth, ensureSession, user } = useAuth()
await ensureSession()
const { codes, count, loaded, pending: favoritePending, load: loadFavorites } = useFavorites()
await loadFavorites()
const page = ref(1)
const pageSize = 20
const detailed = ref(false)
const { data, pending, error, refresh } = await useFavoriteList(page, pageSize)
// 保留服务端快照，只派生过滤；取消失败回滚代码集合时可立即恢复原行。
const items = computed(() =>
  (data.value?.items ?? []).filter((item) => !loaded.value || codes.value.has(item.code)),
)
const total = computed(() => (loaded.value ? count.value : (data.value?.total ?? 0)))
const pages = computed(() => Math.max(1, Math.ceil(total.value / pageSize)))
watch(
  () => user.value?.id,
  () => {
    page.value = 1
    detailed.value = false
  },
)
watch(favoritePending, (busy, wasBusy) => {
  if (busy || !wasBusy || !isLoggedIn.value) return
  const next = Math.min(page.value, pages.value)
  if (next !== page.value) page.value = next
  else refresh()
})
function goPage(next: number) {
  if (pending.value || favoritePending.value || next < 1 || next > pages.value) return
  page.value = next
  if (import.meta.client) window.scrollTo({ top: 0, behavior: 'smooth' })
}
useSeoMeta({
  title: '我的关注',
  description: '查看关注基金表现，直接买入或加仓。',
  robots: 'noindex, nofollow',
})
</script>
<template>
  <div class="favorites">
    <div class="container">
      <header class="head">
        <div>
          <h1>我的关注</h1>
          <p class="head__sub">
            {{ isLoggedIn ? `${total} 只基金 · 最近关注在前` : '把感兴趣的基金留在这里。' }}
          </p>
        </div>
        <NuxtLink to="/funds" class="text-link">+ 添加基金</NuxtLink>
      </header>
      <MemberNav />
      <section v-if="!isLoggedIn" class="empty">
        <h2>登录后查看关注清单</h2>
        <p>关注基金，持续观察表现。</p>
        <button type="button" class="btn" @click="openAuth('login')">登录 / 注册</button>
      </section>
      <section v-else-if="error" class="empty" role="alert">
        <h2>关注列表加载失败</h2>
        <button type="button" class="btn" @click="refresh()">重试</button>
      </section>
      <section v-else-if="!pending && !favoritePending && total === 0" class="empty">
        <h2>还没有关注基金</h2>
        <p>在基金旁点星标，加入这份清单。</p>
        <NuxtLink to="/funds" class="btn">去筛选基金</NuxtLink>
      </section>
      <template v-else>
        <div class="toolbar">
          <span>历史表现，与持仓收益分别统计</span
          ><button
            type="button"
            class="detail-toggle"
            :aria-pressed="detailed"
            @click="detailed = !detailed"
          >
            {{ detailed ? '收起风险指标' : '查看风险指标' }}
          </button>
        </div>
        <div v-if="pending" class="loading" role="status">正在加载关注基金…</div>
        <section v-else class="list" aria-label="关注基金">
          <FavoritesFundRow
            v-for="item in items"
            :key="item.code"
            :item="item"
            :detailed="detailed"
          />
          <p v-if="!items.length" class="loading" role="status">正在更新清单…</p>
        </section>
        <nav v-if="pages > 1 || page > 1" class="pager" aria-label="关注列表分页">
          <button
            type="button"
            :disabled="page <= 1 || pending || favoritePending"
            @click="goPage(page - 1)"
          >
            上一页</button
          ><span class="num">{{ page }} / {{ pages }}</span
          ><button
            type="button"
            :disabled="page >= pages || pending || favoritePending"
            @click="goPage(page + 1)"
          >
            下一页
          </button>
        </nav>
      </template>
    </div>
  </div>
</template>
<style scoped src="~/assets/css/favorites.css"></style>
