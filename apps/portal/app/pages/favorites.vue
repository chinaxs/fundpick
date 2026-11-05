<script setup lang="ts">
import type { ApiResponse, FundListItem, PageResult } from '@project/shared'
import { FUND_TYPE_MAP, fmtMagnitude, fmtPct, toneOf } from '@project/shared'
import { useApiBase } from '~/composables/usePortalApi'

const { isLoggedIn, authHeaders, openAuth, ensureSession } = useAuth()
// layout 已恢复登录态，这里再 await 一次是幂等的，保证页面内可直接判断
await ensureSession()

const { codes, load: loadFavorites } = useFavorites()
await loadFavorites()

const page = ref(1)
const pageSize = 20

const { data, pending, refresh } = await useAsyncData<PageResult<FundListItem> | null>(
  'favorites-list',
  async () => {
    if (!isLoggedIn.value) return null
    const res = await $fetch<ApiResponse<PageResult<FundListItem>>>('/portal/favorites', {
      baseURL: useApiBase(),
      query: { page: page.value, page_size: pageSize },
      headers: authHeaders.value,
    })
    return res.data
  },
  { watch: [page] },
)

/** 本地维护一份列表：取消关注时直接移除，不必重新请求整页 */
const items = ref<FundListItem[]>([])
watch(
  data,
  (value) => {
    items.value = value?.items ?? []
  },
  { immediate: true },
)
watch(codes, (set) => {
  items.value = items.value.filter((item) => set.has(item.code))
})

const hasMore = computed(() => (data.value?.total ?? 0) > (data.value?.page ?? 1) * pageSize)

useSeoMeta({
  title: '我的关注',
  description: '我关注的基金列表，包含区间收益与风险指标。',
})
</script>

<template>
  <div class="page">
    <div class="container">
      <header class="head">
        <div>
          <h1 class="head__title">我的关注</h1>
          <p class="head__sub">
            <template v-if="isLoggedIn">
              共 {{ data?.total ?? 0 }} 只基金，按关注时间倒序
            </template>
            <template v-else>登录后可收藏基金，随时回来看</template>
          </p>
        </div>
        <NuxtLink to="/funds" class="link-more">去筛选基金 →</NuxtLink>
      </header>

      <!-- 未登录 -->
      <section v-if="!isLoggedIn" class="empty">
        <div class="empty__icon">☆</div>
        <h2 class="empty__title">还没有登录</h2>
        <p class="empty__desc">登录后可以把看中的基金加进关注，下次直接对比。</p>
        <button type="button" class="btn-primary" @click="openAuth('login')">登录 / 注册</button>
      </section>

      <!-- 已登录但为空 -->
      <section v-else-if="!pending && items.length === 0" class="empty">
        <div class="empty__icon">☆</div>
        <h2 class="empty__title">还没有关注任何基金</h2>
        <p class="empty__desc">在筛选列表点星标，或在基金详情页点「关注」，就会出现在这里。</p>
        <NuxtLink to="/funds" class="btn-primary">去挑几只</NuxtLink>
      </section>

      <!-- 列表 -->
      <section v-else class="list">
        <article v-for="item in items" :key="item.code" class="row">
          <FavoriteButton :code="item.code" variant="icon" />

          <NuxtLink :to="`/funds/${item.code}`" class="row__main">
            <span class="row__name">{{ item.name }}</span>
            <span class="row__meta">
              <span class="num">{{ item.code }}</span>
              <span class="dot">·</span>
              <span>{{ FUND_TYPE_MAP[item.type] }}</span>
              <template v-if="item.company_name">
                <span class="dot">·</span>
                <span>{{ item.company_name }}</span>
              </template>
            </span>
          </NuxtLink>

          <div class="row__metrics">
            <div class="metric">
              <span class="metric__label">近 1 年</span>
              <span class="metric__value num" :class="toneOf(item.return_rate)">
                {{ fmtPct(item.return_rate) }}
              </span>
            </div>
            <div class="metric">
              <span class="metric__label">回撤</span>
              <span class="metric__value num muted">{{ fmtMagnitude(item.max_drawdown) }}</span>
            </div>
            <div class="metric">
              <span class="metric__label">夏普</span>
              <span class="metric__value num">
                {{ item.sharpe == null ? '—' : item.sharpe.toFixed(2) }}
              </span>
            </div>
          </div>

          <NuxtLink :to="`/funds/${item.code}`" class="row__go" aria-label="查看详情">→</NuxtLink>
        </article>

        <div v-if="hasMore || page > 1" class="pager">
          <button type="button" class="pager__btn" :disabled="page <= 1" @click="page--">
            上一页
          </button>
          <span class="pager__now">第 {{ page }} 页</span>
          <button
            type="button"
            class="pager__btn"
            :disabled="!hasMore"
            @click="
              page++
              refresh()
            "
          >
            下一页
          </button>
        </div>
      </section>
    </div>
  </div>
</template>

<style scoped>
.page {
  min-height: 70vh;
  padding: 32px 0 72px;
}

.head {
  display: flex;
  flex-wrap: wrap;
  gap: 16px;
  align-items: flex-end;
  justify-content: space-between;
  padding-bottom: 22px;
  border-bottom: 1px solid var(--line);
}

.head__title {
  margin: 0;
  font-size: 26px;
  font-weight: 700;
  letter-spacing: -0.02em;
}

.head__sub {
  margin: 8px 0 0;
  font-size: 13px;
  color: var(--muted);
}

.link-more {
  font-size: 13px;
  font-weight: 600;
  color: var(--brand);
}

.link-more:hover {
  text-decoration: underline;
}

/* ---- 空态 ---- */
.empty {
  display: grid;
  gap: 12px;
  justify-items: center;
  padding: 80px 20px;
  text-align: center;
}

.empty__icon {
  display: grid;
  place-items: center;
  width: 64px;
  height: 64px;
  margin-bottom: 6px;
  font-size: 30px;
  color: var(--muted-2);
  background: var(--bg-soft);
  border: 1px solid var(--line);
  border-radius: 20px;
}

.empty__title {
  margin: 0;
  font-size: 17px;
  font-weight: 600;
}

.empty__desc {
  max-width: 420px;
  margin: 0;
  font-size: 13px;
  line-height: 1.8;
  color: var(--muted);
}

.btn-primary {
  display: inline-flex;
  gap: 6px;
  align-items: center;
  margin-top: 8px;
  padding: 10px 22px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  cursor: pointer;
  background: var(--brand);
  border: none;
  border-radius: 999px;
  transition: background 0.15s ease;
}

.btn-primary:hover {
  background: var(--brand-dark);
}

/* ---- 列表 ---- */
.list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 20px;
}

.row {
  display: flex;
  gap: 14px;
  align-items: center;
  padding: 16px 18px;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: var(--radius);
  transition:
    border-color 0.15s ease,
    box-shadow 0.15s ease;
}

.row:hover {
  border-color: var(--brand);
  box-shadow: var(--shadow-sm);
}

.row__main {
  flex: 1;
  min-width: 0;
}

.row__name {
  display: block;
  overflow: hidden;
  font-size: 15px;
  font-weight: 600;
  color: var(--ink);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.row__meta {
  display: flex;
  flex-wrap: wrap;
  gap: 5px;
  align-items: center;
  margin-top: 4px;
  font-size: 12px;
  color: var(--muted-2);
}

.dot {
  color: var(--line);
}

.row__metrics {
  display: flex;
  gap: 26px;
}

.metric {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  min-width: 62px;
}

.metric__label {
  font-size: 11px;
  color: var(--muted-2);
}

.metric__value {
  margin-top: 2px;
  font-size: 15px;
  font-weight: 700;
  color: var(--ink);
}

.muted {
  color: var(--muted);
}

.row__go {
  flex: none;
  font-size: 15px;
  color: var(--muted-2);
  transition: color 0.15s ease;
}

.row__go:hover {
  color: var(--brand);
}

/* ---- 分页 ---- */
.pager {
  display: flex;
  gap: 14px;
  align-items: center;
  justify-content: center;
  padding: 24px 0 0;
}

.pager__btn {
  padding: 8px 18px;
  font-size: 13px;
  font-weight: 600;
  color: var(--ink-2);
  cursor: pointer;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 999px;
}

.pager__btn:hover:not(:disabled) {
  color: var(--brand);
  border-color: var(--brand);
}

.pager__btn:disabled {
  color: var(--muted-2);
  cursor: default;
  opacity: 0.55;
}

.pager__now {
  font-size: 13px;
  color: var(--muted);
}

@media (max-width: 720px) {
  .row {
    flex-wrap: wrap;
  }

  .row__metrics {
    width: 100%;
    gap: 18px;
    justify-content: space-between;
    padding-top: 10px;
    border-top: 1px solid var(--line-soft);
  }

  .metric {
    align-items: flex-start;
  }
}
</style>
