<script setup lang="ts">
import type { FundListItem } from '@project/shared'
import { FUND_TYPE_MAP, fmtMagnitude, fmtPct, toneOf } from '@project/shared'
defineProps<{ item: FundListItem; detailed: boolean }>()
</script>
<template>
  <article class="favorite-row" :class="{ 'favorite-row--detailed': detailed }">
    <FavoriteButton :code="item.code" variant="icon" />
    <NuxtLink :to="`/funds/${item.code}`" class="favorite-row__fund"
      ><strong>{{ item.name }}</strong
      ><span class="favorite-row__meta"
        ><span class="num">{{ item.code }}</span
        ><span>{{ FUND_TYPE_MAP[item.type] }}</span
        ><HoldingBadge :code="item.code" /></span
    ></NuxtLink>
    <div class="favorite-row__return">
      <span>近1年收益</span
      ><strong class="num" :class="toneOf(item.return_rate)">{{ fmtPct(item.return_rate) }}</strong>
    </div>
    <div v-if="detailed" class="favorite-row__risk">
      <span
        >最大回撤 <b class="num">{{ fmtMagnitude(item.max_drawdown) }}</b></span
      ><span
        >夏普 <b class="num">{{ item.sharpe?.toFixed(2) ?? '—' }}</b></span
      >
    </div>
    <FundBuyButton
      class="favorite-row__buy"
      :code="item.code"
      :name="item.name"
      :nav-date="item.latest_nav_date"
      compact
    />
  </article>
</template>
<style scoped>
.favorite-row {
  display: grid;
  grid-template-columns: 28px minmax(0, 1fr) 100px 56px;
  gap: 18px;
  align-items: center;
  padding: 15px 18px;
  border-bottom: 1px solid var(--line-soft);
}
.favorite-row:last-child {
  border-bottom: 0;
}
.favorite-row--detailed {
  grid-template-columns: 28px minmax(0, 1fr) 100px 180px 56px;
}
.favorite-row__fund {
  min-width: 0;
}
.favorite-row__fund > strong {
  display: block;
  font-size: 14px;
  font-weight: 500;
  color: var(--ink);
  overflow-wrap: anywhere;
}
.favorite-row__fund:hover > strong {
  color: var(--brand);
}
.favorite-row__meta {
  display: flex;
  flex-wrap: wrap;
  align-items: center;
  gap: 8px;
  margin-top: 4px;
  font-size: 11px;
  color: var(--muted);
}
.favorite-row__return {
  display: flex;
  flex-direction: column;
  align-items: flex-end;
  gap: 3px;
}
.favorite-row__return > span {
  font-size: 11px;
  color: var(--muted);
}
.favorite-row__return > strong {
  font-size: 15px;
}
.favorite-row__risk {
  display: flex;
  gap: 16px;
  align-items: center;
  justify-content: flex-end;
  color: var(--muted);
  font-size: 11px;
}
.favorite-row__risk > span {
  display: flex;
  flex-direction: column;
  gap: 3px;
}
.favorite-row__risk b {
  color: var(--ink-2);
  font-weight: 500;
  font-size: 13px;
}
.favorite-row :focus-visible {
  outline: 2px solid var(--brand);
  outline-offset: 3px;
}
@media (max-width: 768px) {
  .favorite-row,
  .favorite-row--detailed {
    grid-template-columns: 28px minmax(0, 1fr) auto;
    gap: 12px;
    padding: 14px;
  }
  .favorite-row__fund {
    grid-column: 2 / -1;
  }
  .favorite-row__return {
    grid-column: 2;
    align-items: flex-start;
  }
  .favorite-row__buy {
    grid-column: 3;
    justify-self: end;
  }
  .favorite-row__risk {
    grid-column: 2 / -1;
    grid-row: 3;
    justify-content: flex-start;
    gap: 22px;
  }
  .favorite-row__risk > span {
    flex-direction: row;
    align-items: center;
    gap: 8px;
  }
}
</style>
