<script setup lang="ts">
import type { FilterOption } from '@project/shared'

/**
 * 自定义下拉：与筛选面板同风格的按钮 + 弹出菜单。
 * 选项不多（区间 9 项、排序 6 项），原生 select 的系统样式无法定制，故自行实现。
 */
const props = defineProps<{
  label: string
  options: FilterOption[]
  modelValue?: string
}>()

const emit = defineEmits<{ 'update:modelValue': [value: string] }>()

const open = ref(false)
const root = ref<HTMLElement | null>(null)

const current = computed(() => props.options.find((opt) => opt.value === props.modelValue))

function pick(value: string) {
  emit('update:modelValue', value)
  open.value = false
}

function onDocClick(event: MouseEvent) {
  if (root.value && !root.value.contains(event.target as Node)) open.value = false
}

onMounted(() => document.addEventListener('click', onDocClick))
onBeforeUnmount(() => document.removeEventListener('click', onDocClick))
</script>

<template>
  <div ref="root" class="dd" :class="{ 'dd--open': open }">
    <button type="button" class="dd__btn" @click="open = !open">
      <span class="dd__label">{{ label }}</span>
      <span class="dd__value" :class="{ 'dd__value--default': !current }">
        {{ current?.label ?? '默认' }}
      </span>
      <svg class="dd__chevron" viewBox="0 0 12 12" aria-hidden="true">
        <path
          d="M2.5 4.5 6 8l3.5-3.5"
          fill="none"
          stroke="currentColor"
          stroke-width="1.5"
          stroke-linecap="round"
          stroke-linejoin="round"
        />
      </svg>
    </button>

    <div v-if="open" class="dd__menu">
      <button
        v-for="opt in options"
        :key="opt.value"
        type="button"
        class="dd__opt"
        :class="{ 'dd__opt--active': opt.value === modelValue }"
        @click="pick(String(opt.value))"
      >
        {{ opt.label }}
        <svg
          v-if="opt.value === modelValue"
          class="dd__check"
          viewBox="0 0 12 12"
          aria-hidden="true"
        >
          <path
            d="M2 6.2 4.8 9 10 3.5"
            fill="none"
            stroke="currentColor"
            stroke-width="1.6"
            stroke-linecap="round"
            stroke-linejoin="round"
          />
        </svg>
      </button>
    </div>
  </div>
</template>

<style scoped>
.dd {
  position: relative;
}

.dd__btn {
  display: inline-flex;
  gap: 7px;
  align-items: center;
  height: 34px;
  padding: 0 10px 0 12px;
  font-size: 12.5px;
  color: var(--ink-2);
  cursor: pointer;
  background: var(--bg-soft);
  border: 1px solid transparent;
  border-radius: 8px;
  transition:
    background 0.15s ease,
    border-color 0.15s ease;
}

.dd__btn:hover,
.dd--open .dd__btn {
  background: #fff;
  border-color: var(--line);
}

.dd--open .dd__btn {
  border-color: rgb(37 99 235 / 35%);
}

.dd__label {
  color: var(--muted-2);
}

.dd__value {
  font-weight: 600;
  color: var(--ink);
}

.dd__value--default {
  color: var(--muted);
  font-weight: 500;
}

.dd__chevron {
  width: 11px;
  height: 11px;
  color: var(--muted-2);
  transition: transform 0.15s ease;
}

.dd--open .dd__chevron {
  transform: rotate(180deg);
}

.dd__menu {
  position: absolute;
  top: calc(100% + 6px);
  left: 0;
  z-index: 30;
  min-width: 132px;
  padding: 5px;
  background: #fff;
  border: 1px solid var(--line);
  border-radius: 10px;
  box-shadow: 0 10px 28px rgb(15 23 42 / 12%);
  animation: dd-in 0.12s ease;
}

@keyframes dd-in {
  from {
    opacity: 0;
    transform: translateY(-3px);
  }

  to {
    opacity: 1;
    transform: translateY(0);
  }
}

.dd__opt {
  display: flex;
  gap: 8px;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  padding: 7px 10px;
  font-size: 12.5px;
  color: var(--ink-2);
  text-align: left;
  cursor: pointer;
  background: transparent;
  border: none;
  border-radius: 7px;
  transition: background 0.12s ease;
}

.dd__opt:hover {
  background: var(--bg-soft);
}

.dd__opt--active {
  font-weight: 600;
  color: var(--brand);
}

.dd__check {
  width: 12px;
  height: 12px;
}
</style>
