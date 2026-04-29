<script setup>
import { computed } from 'vue'

const props = defineProps({
  task: { type: Object, required: true },
})
const emit = defineEmits(['cancel', 'publish'])

// 优先用 works（带 id/is_public），兼容老数据再退回 result_images/result_video
const imageWorks = computed(() => {
  const ws = (props.task.works || []).filter((w) => w.media_type === 'image')
  if (ws.length) return ws
  return (props.task.result_images || []).map((url) => ({ id: null, media_type: 'image', media_url: url, is_public: false }))
})
const videoWork = computed(() => {
  const ws = (props.task.works || []).filter((w) => w.media_type === 'video')
  if (ws.length) return ws[0]
  const url = props.task.result_video?.url
  return url ? { id: null, media_type: 'video', media_url: url, is_public: false } : null
})

const statusLabel = computed(() => {
  switch (props.task.status) {
    case 'queued': return `排队中（第 ${props.task.queue_position} 位）`
    case 'running': return '生成中...'
    case 'completed': return '已完成'
    case 'failed': return '失败'
    case 'cancelled': return '已取消'
    default: return props.task.status
  }
})
const statusColor = computed(() => {
  return {
    queued: 'text-amber-600 bg-amber-50',
    running: 'text-brand-600 bg-brand-50',
    completed: 'text-emerald-600 bg-emerald-50',
    failed: 'text-red-600 bg-red-50',
    cancelled: 'text-slate-500 bg-slate-100',
  }[props.task.status] || 'text-slate-500 bg-slate-100'
})
</script>

<template>
  <div class="bg-white rounded-xl border border-slate-200 p-4">
    <div class="flex items-start justify-between gap-3 mb-2">
      <div class="flex-1 min-w-0">
        <div class="flex items-center gap-2 text-xs">
          <span class="px-2 py-0.5 rounded" :class="statusColor">{{ statusLabel }}</span>
          <span class="text-slate-400">{{ task.model }}</span>
        </div>
        <p class="text-sm text-slate-700 mt-1 line-clamp-2">{{ task.prompt }}</p>
      </div>
      <button
        v-if="task.status === 'queued'"
        @click="emit('cancel', task)"
        class="text-xs text-red-500 hover:underline shrink-0"
      >
        取消
      </button>
    </div>

    <!-- running loading bar -->
    <div v-if="task.status === 'running'" class="h-1 bg-brand-100 rounded overflow-hidden mb-2">
      <div class="h-full bg-brand-500 animate-pulse w-1/2"></div>
    </div>

    <!-- 错误 -->
    <div v-if="task.status === 'failed' && task.error_message" class="text-xs text-red-500 mt-1">
      {{ task.error_message }}
    </div>

    <!-- 结果：图片 -->
    <div
      v-if="task.status === 'completed' && task.task_type === 'image' && imageWorks.length"
      class="grid gap-2 mt-2"
      :class="imageWorks.length > 1 ? 'grid-cols-2' : 'grid-cols-1'"
    >
      <div
        v-for="(w, i) in imageWorks"
        :key="w.id ?? i"
        class="relative group rounded-lg overflow-hidden bg-slate-100 border border-slate-200"
      >
        <a :href="w.media_url" target="_blank" class="block">
          <img :src="w.media_url" class="w-full h-full object-cover" loading="lazy" />
        </a>
        <button
          v-if="w.id"
          type="button"
          @click="emit('publish', w)"
          :class="[
            'absolute bottom-1 right-1 text-xs px-2 py-0.5 rounded-md shadow-sm transition',
            w.is_public
              ? 'bg-emerald-600 text-white hover:bg-emerald-700'
              : 'bg-white/90 text-slate-700 hover:bg-white',
          ]"
        >
          {{ w.is_public ? '已公开 · 取消' : '推到画廊' }}
        </button>
      </div>
    </div>

    <!-- 结果：视频 -->
    <div v-if="task.status === 'completed' && task.task_type === 'video' && videoWork" class="mt-2 relative">
      <video :src="videoWork.media_url" controls class="w-full rounded-lg bg-black" />
      <button
        v-if="videoWork.id"
        type="button"
        @click="emit('publish', videoWork)"
        :class="[
          'absolute bottom-2 right-2 text-xs px-2 py-0.5 rounded-md shadow-sm transition',
          videoWork.is_public
            ? 'bg-emerald-600 text-white hover:bg-emerald-700'
            : 'bg-white/90 text-slate-700 hover:bg-white',
        ]"
      >
        {{ videoWork.is_public ? '已公开 · 取消' : '推到画廊' }}
      </button>
    </div>
  </div>
</template>
