<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { ElMessage, ElMessageBox } from 'element-plus'

import { ARTICLE_STATUS_MAP, formatDateTime } from '@project/shared'
import type { ArticleVersionItem } from '@project/shared'

import { articleApi } from '@/api'

/** 历史版本：查看每次保存的快照，并可把内容恢复到某个版本。 */
const props = defineProps<{ modelValue: boolean; articleId: number | null }>()
const emit = defineEmits<{
  'update:modelValue': [value: boolean]
  restored: []
}>()

const visible = computed({
  get: () => props.modelValue,
  set: (value: boolean) => emit('update:modelValue', value),
})

const versions = ref<ArticleVersionItem[]>([])
const loading = ref(false)
const restoring = ref(false)

async function load() {
  if (!props.articleId) return
  loading.value = true
  try {
    versions.value = await articleApi.versions(props.articleId)
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '加载历史版本失败')
  } finally {
    loading.value = false
  }
}

async function restore(version: ArticleVersionItem) {
  if (!props.articleId) return
  try {
    await ElMessageBox.confirm(
      `把正文恢复到 v${version.version}（${formatDateTime(version.created_at)}）？\n当前内容会作为新版本保留，不会丢失。`,
      '恢复历史版本',
      { confirmButtonText: '恢复', cancelButtonText: '取消', type: 'warning' },
    )
  } catch {
    return
  }
  restoring.value = true
  try {
    await articleApi.restoreVersion(props.articleId, version.version)
    ElMessage.success(`已恢复到 v${version.version}`)
    visible.value = false
    emit('restored')
  } catch (error) {
    ElMessage.error(error instanceof Error ? error.message : '恢复失败')
  } finally {
    restoring.value = false
  }
}

function statusText(status: string) {
  const entry = (ARTICLE_STATUS_MAP as Record<string, { label: string }>)[status]
  return entry?.label ?? status
}

function preview(version: ArticleVersionItem) {
  const body = version.content ? version.content.slice(0, 400) : '（无正文）'
  void ElMessageBox.alert(body, `v${version.version} · ${version.title}`, {
    confirmButtonText: '关闭',
  })
}

watch(
  () => [props.modelValue, props.articleId],
  () => {
    if (props.modelValue) void load()
  },
)
</script>

<template>
  <el-drawer v-model="visible" title="历史版本" size="520px">
    <p class="hint">每次保存都会留下快照；恢复会追加一条新版本，历史不会被覆盖。</p>
    <el-timeline v-loading="loading">
      <el-timeline-item
        v-for="item in versions"
        :key="item.id"
        :timestamp="formatDateTime(item.created_at)"
        placement="top"
      >
        <div class="version">
          <div class="version__head">
            <strong>v{{ item.version }}</strong>
            <el-tag size="small" effect="light">{{ statusText(item.status) }}</el-tag>
            <span class="muted">{{ item.edited_by || '未知' }}</span>
          </div>
          <p class="version__title">{{ item.title }}</p>
          <div class="version__actions">
            <el-button link type="primary" size="small" @click="preview(item)">查看</el-button>
            <el-button
              link
              type="warning"
              size="small"
              :disabled="restoring"
              @click="restore(item)"
            >
              恢复此版本
            </el-button>
          </div>
        </div>
      </el-timeline-item>
    </el-timeline>
    <el-empty v-if="!loading && !versions.length" description="还没有历史版本" :image-size="60" />
  </el-drawer>
</template>

<style scoped lang="scss">
.hint {
  margin: 0 0 16px;
  font-size: 12.5px;
  line-height: 1.7;
  color: $text-secondary;
}

.version {
  &__head {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  &__title {
    margin: 6px 0 4px;
    font-size: 13.5px;
    color: $text-regular;
  }

  &__actions {
    display: flex;
    gap: 4px;
  }
}

.muted {
  font-size: 12px;
  color: $text-secondary;
}
</style>
