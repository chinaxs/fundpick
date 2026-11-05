<script setup lang="ts">
/**
 * 关注按钮。
 *
 * 两处复用：详情页用 solid（带文字的按钮），列表页用 icon（行内小星标）。
 * 未登录时点击会唤起登录弹窗，不会静默失败。
 */
import { ElMessage } from 'element-plus'

const props = withDefaults(
  defineProps<{
    code: string
    variant?: 'solid' | 'icon'
  }>(),
  { variant: 'solid' },
)

const { isFavorited, toggle, pending } = useFavorites()

const favorited = computed(() => isFavorited(props.code))

async function onClick(event: Event) {
  // 列表页星标在可点击的行里，阻止跳转
  event.preventDefault()
  event.stopPropagation()

  try {
    const result = await toggle(props.code)
    if (result === true) ElMessage.success('已加入关注')
    else if (result === false) ElMessage.info('已取消关注')
  } catch {
    ElMessage.error('操作失败，请稍后重试')
  }
}
</script>

<template>
  <button
    v-if="variant === 'icon'"
    type="button"
    class="fav-icon"
    :class="{ 'fav-icon--on': favorited }"
    :disabled="pending"
    :title="favorited ? '取消关注' : '关注'"
    :aria-label="favorited ? '取消关注' : '关注'"
    :aria-pressed="favorited"
    @click="onClick"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 3.7l2.55 5.17 5.7.83-4.12 4.02.97 5.68L12 16.72l-5.1 2.68.97-5.68-4.12-4.02 5.7-.83z"
        :fill="favorited ? 'currentColor' : 'none'"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linejoin="round"
      />
    </svg>
  </button>

  <button
    v-else
    type="button"
    class="fav-btn"
    :class="{ 'fav-btn--on': favorited }"
    :disabled="pending"
    @click="onClick"
  >
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path
        d="M12 3.7l2.55 5.17 5.7.83-4.12 4.02.97 5.68L12 16.72l-5.1 2.68.97-5.68-4.12-4.02 5.7-.83z"
        :fill="favorited ? 'currentColor' : 'none'"
        stroke="currentColor"
        stroke-width="1.5"
        stroke-linejoin="round"
      />
    </svg>
    <span>{{ favorited ? '已关注' : '关注' }}</span>
    <span v-if="favorited" class="fav-btn__count" />
  </button>
</template>

<style scoped>
.fav-icon {
  display: grid;
  place-items: center;
  width: 28px;
  height: 28px;
  padding: 0;
  color: var(--muted-2);
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 8px;
  transition:
    color 0.15s ease,
    background 0.15s ease;
}

.fav-icon svg {
  width: 17px;
  height: 17px;
}

.fav-icon:hover {
  color: #f59e0b;
  background: #fffbeb;
}

.fav-icon--on {
  color: #f59e0b;
}

.fav-btn {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  padding: 9px 18px;
  font-size: 14px;
  font-weight: 600;
  color: var(--ink-2);
  cursor: pointer;
  background: var(--bg);
  border: 1px solid var(--line);
  border-radius: 999px;
  transition:
    color 0.15s ease,
    border-color 0.15s ease,
    background 0.15s ease;
}

.fav-btn svg {
  width: 17px;
  height: 17px;
}

.fav-btn:hover {
  color: #b45309;
  border-color: #f59e0b;
}

.fav-btn--on {
  color: #b45309;
  background: #fffbeb;
  border-color: #fcd34d;
}

.fav-btn__count {
  width: 6px;
  height: 6px;
  background: #f59e0b;
  border-radius: 50%;
}

button:disabled {
  cursor: default;
  opacity: 0.6;
}
</style>
