<script setup>
import { computed } from 'vue'

const props = defineProps({
  page: { type: Number, required: true },
  totalPages: { type: Number, required: true },
  total: { type: Number, required: true },
  loading: { type: Boolean, default: false },
  // 桌面端显示的页码按钮数量（奇数最居中）
  siblingCount: { type: Number, default: 1 },
})
const emit = defineEmits(['change'])

function go(p) {
  emit('change', p)
}

// 生成中间页码列表（带 … 省略）
const pageItems = computed(() => {
  const total = props.totalPages
  const cur = props.page
  if (total <= 7) return Array.from({ length: total }, (_, i) => i + 1)
  const left = Math.max(2, cur - props.siblingCount)
  const right = Math.min(total - 1, cur + props.siblingCount)
  const out = [1]
  if (left > 2) out.push('…')
  for (let i = left; i <= right; i++) out.push(i)
  if (right < total - 1) out.push('…')
  out.push(total)
  return out
})
</script>

<template>
  <div class="flex flex-wrap items-center justify-between gap-2 px-3 py-2 border-t border-slate-100 text-xs text-slate-500">
    <div>共 {{ total }} 条 · 第 {{ page }}/{{ totalPages }} 页</div>

    <div class="flex items-center gap-1">
      <button
        class="px-2 py-1 rounded border border-slate-200 hover:border-brand-400 hover:text-brand-600 disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-500"
        :disabled="loading || page <= 1"
        @click="go(page - 1)"
      >
        上一页
      </button>

      <!-- 桌面：显示页码 -->
      <template v-for="(it, idx) in pageItems" :key="idx">
        <span v-if="it === '…'" class="hidden sm:inline px-1 text-slate-400">…</span>
        <button
          v-else
          class="hidden sm:inline px-2 py-1 rounded border text-xs"
          :class="it === page
            ? 'bg-brand-600 border-brand-600 text-white'
            : 'border-slate-200 hover:border-brand-400 hover:text-brand-600'"
          :disabled="loading"
          @click="go(it)"
        >
          {{ it }}
        </button>
      </template>

      <button
        class="px-2 py-1 rounded border border-slate-200 hover:border-brand-400 hover:text-brand-600 disabled:opacity-40 disabled:hover:border-slate-200 disabled:hover:text-slate-500"
        :disabled="loading || page >= totalPages"
        @click="go(page + 1)"
      >
        下一页
      </button>
    </div>
  </div>
</template>
