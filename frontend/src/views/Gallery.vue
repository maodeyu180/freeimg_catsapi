<script setup>
import { computed, onMounted, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useUserStore } from '../stores/user'
import { formatBeijingTime } from '../utils/time'
import Pagination from '../components/Pagination.vue'

const userStore = useUserStore()
const router = useRouter()

const PAGE_SIZE = 24
const items = ref([])
const total = ref(0)
const page = ref(1)
const sort = ref('latest')
const loading = ref(false)
const errorMsg = ref('')

const detail = ref(null) // 当前打开的详情作品；为空表示关闭
const copied = ref(false)
const downloading = ref(false)
const deleting = ref(false)
const liking = ref(false)

const totalPages = computed(() => Math.max(1, Math.ceil(total.value / PAGE_SIZE)))

const SORT_OPTIONS = [
  { value: 'latest', label: '最新' },
  { value: 'likes', label: '点赞最多' },
  { value: 'views', label: '查看最多' },
]

async function load() {
  loading.value = true
  errorMsg.value = ''
  try {
    const offset = (page.value - 1) * PAGE_SIZE
    const { items: list, total: t } = await api.publicGallery(offset, PAGE_SIZE, sort.value)
    items.value = list
    total.value = t
    // 删除等情况导致当前页空了，自动回退
    if (!list.length && page.value > 1) {
      page.value = Math.max(1, page.value - 1)
      await load()
    }
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function gotoPage(p) {
  if (p < 1 || p > totalPages.value || p === page.value) return
  page.value = p
  load()
  window.scrollTo({ top: 0, behavior: 'smooth' })
}

watch(sort, () => {
  page.value = 1
  load()
})

async function openDetail(w) {
  detail.value = { ...w }
  copied.value = false
  document.body.style.overflow = 'hidden'
  try {
    const res = await api.recordView(w.id)
    if (detail.value && detail.value.id === w.id) {
      detail.value.view_count = res.view_count
    }
    const cached = items.value.find((it) => it.id === w.id)
    if (cached) cached.view_count = res.view_count
  } catch {
    // 忽略统计错误
  }
}
function closeDetail() {
  detail.value = null
  document.body.style.overflow = ''
  deleting.value = false
}

function remix(w) {
  if (!userStore.isLoggedIn) {
    alert('请先登录后使用一键同款')
    return
  }
  closeDetail()
  router.push({ path: '/', query: { remix: w.id } })
}

async function copyPrompt() {
  if (!detail.value?.prompt) return
  try {
    await navigator.clipboard.writeText(detail.value.prompt)
    copied.value = true
    setTimeout(() => (copied.value = false), 1600)
  } catch {
    const ta = document.createElement('textarea')
    ta.value = detail.value.prompt
    document.body.appendChild(ta)
    ta.select()
    try {
      document.execCommand('copy')
      copied.value = true
      setTimeout(() => (copied.value = false), 1600)
    } catch {
      alert('复制失败，请手动选择文本复制')
    } finally {
      document.body.removeChild(ta)
    }
  }
}

function fileExt(url, fallback) {
  try {
    const u = new URL(url, location.href)
    const m = u.pathname.match(/\.([a-zA-Z0-9]{1,5})$/)
    if (m) return m[1].toLowerCase()
  } catch {}
  return fallback
}

async function downloadMedia() {
  const w = detail.value
  if (!w) return
  downloading.value = true
  const ext = fileExt(w.media_url, w.media_type === 'video' ? 'mp4' : 'png')
  const filename = `gallery-${w.id || Date.now()}.${ext}`
  try {
    const res = await fetch(w.media_url, { mode: 'cors' })
    if (!res.ok) throw new Error('network')
    const blob = await res.blob()
    const blobUrl = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = blobUrl
    a.download = filename
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(blobUrl), 1000)
  } catch {
    window.open(w.media_url, '_blank', 'noopener')
  } finally {
    downloading.value = false
  }
}

async function adminDeleteWork() {
  const w = detail.value
  if (!w || !userStore.isAdmin) return
  if (!confirm(`确认从画廊删除 ${w.username || '该用户'} 的这个作品？`)) return
  deleting.value = true
  try {
    await api.deleteWork(w.id)
    items.value = items.value.filter((item) => item.id !== w.id)
    total.value = Math.max(0, total.value - 1)
    closeDetail()
  } catch (e) {
    alert(e.message)
    deleting.value = false
  }
}

async function toggleLike() {
  const w = detail.value
  if (!w) return
  if (!userStore.isLoggedIn) {
    alert('请先登录后再点赞')
    return
  }
  if (liking.value) return
  liking.value = true
  try {
    const res = await api.toggleLike(w.id)
    if (detail.value && detail.value.id === w.id) {
      detail.value.liked_by_me = res.liked_by_me
      detail.value.like_count = res.like_count
    }
    const cached = items.value.find((it) => it.id === w.id)
    if (cached) {
      cached.liked_by_me = res.liked_by_me
      cached.like_count = res.like_count
    }
  } catch (e) {
    alert(e.message)
  } finally {
    liking.value = false
  }
}

function onKeydown(e) {
  if (e.key === 'Escape' && detail.value) closeDetail()
}

onMounted(() => {
  load()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})

const createdAtLabel = computed(() => formatBeijingTime(detail.value?.created_at))

const HIDDEN_PARAM_KEYS = new Set(['quality', 'rewritePrompt', 'rewrite_prompt'])
const visibleParams = computed(() => {
  const p = detail.value?.params
  if (!p || typeof p !== 'object') return {}
  return Object.fromEntries(Object.entries(p).filter(([k]) => !HIDDEN_PARAM_KEYS.has(k)))
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-4 py-6">
    <div class="flex flex-wrap items-center gap-3 mb-5">
      <h1 class="text-xl font-semibold text-slate-800">画廊</h1>
      <span class="text-xs text-slate-400">· 社区公开作品</span>

      <div class="ml-auto flex items-center gap-2">
        <span class="text-xs text-slate-400 hidden sm:inline">排序</span>
        <div class="flex bg-white rounded-lg border border-slate-200 p-0.5">
          <button
            v-for="opt in SORT_OPTIONS"
            :key="opt.value"
            type="button"
            :disabled="loading"
            @click="sort = opt.value"
            :class="[
              'px-3 py-1 text-xs sm:text-sm rounded-md transition disabled:opacity-60',
              sort === opt.value ? 'bg-brand-600 text-white' : 'text-slate-600 hover:text-brand-600',
            ]"
          >
            {{ opt.label }}
          </button>
        </div>
      </div>
    </div>

    <div v-if="errorMsg" class="text-red-600 text-sm mb-4">{{ errorMsg }}</div>

    <div v-if="loading && !items.length" class="text-slate-400 text-sm">加载中…</div>
    <div
      v-else-if="!items.length"
      class="text-slate-400 text-sm bg-white rounded-xl border border-slate-200 p-12 text-center"
    >
      画廊空空如也，去「我的任务」里把作品推到画廊吧
    </div>

    <template v-else>
      <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-3">
        <button
          v-for="w in items"
          :key="w.id"
          type="button"
          @click="openDetail(w)"
          class="group relative text-left bg-white rounded-xl border border-slate-200 overflow-hidden hover:shadow-lg hover:border-brand-400 transition cursor-zoom-in"
        >
          <div class="aspect-square bg-slate-100 overflow-hidden relative">
            <img
              v-if="w.media_type === 'image'"
              :src="w.media_url"
              class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
              loading="lazy"
            />
            <video
              v-else
              :src="w.media_url"
              class="w-full h-full object-cover"
              muted
              loop
              preload="metadata"
              @mouseenter="(e) => e.target.play()"
              @mouseleave="(e) => e.target.pause()"
            />
            <span
              v-if="w.media_type === 'video'"
              class="absolute top-1.5 left-1.5 text-[10px] px-1.5 py-0.5 rounded bg-black/60 text-white"
            >视频</span>
            <div
              class="absolute bottom-1.5 right-1.5 flex items-center gap-1 text-[10px] text-white"
            >
              <span
                class="px-1.5 py-0.5 rounded bg-black/55 backdrop-blur-sm flex items-center gap-0.5"
                :class="w.liked_by_me ? 'text-rose-300' : ''"
              >
                <svg viewBox="0 0 24 24" class="w-3 h-3" :fill="w.liked_by_me ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 21s-7-4.35-9.5-8.5C.5 8.5 3 4 7 4c2 0 3.5 1 5 3 1.5-2 3-3 5-3 4 0 6.5 4.5 4.5 8.5C19 16.65 12 21 12 21z"/>
                </svg>
                {{ w.like_count || 0 }}
              </span>
              <span class="px-1.5 py-0.5 rounded bg-black/55 backdrop-blur-sm flex items-center gap-0.5">
                <svg viewBox="0 0 24 24" class="w-3 h-3" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z"/>
                  <circle cx="12" cy="12" r="3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                {{ w.view_count || 0 }}
              </span>
            </div>
          </div>

          <div class="p-2 text-xs">
            <div class="flex items-center gap-1.5 mb-1 text-slate-500">
              <img v-if="w.user_avatar" :src="w.user_avatar" class="w-4 h-4 rounded-full" />
              <span class="truncate">{{ w.username }}</span>
              <span class="ml-auto text-slate-400 truncate max-w-[50%]">{{ w.model }}</span>
            </div>
            <p class="line-clamp-2 text-slate-600 h-8">{{ w.prompt }}</p>
          </div>
        </button>
      </div>

      <div class="mt-4 bg-white rounded-xl border border-slate-200">
        <Pagination
          :page="page"
          :total-pages="totalPages"
          :total="total"
          :loading="loading"
          @change="gotoPage"
        />
      </div>
    </template>

    <!-- 详情弹窗 -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="detail"
        class="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6"
        @click.self="closeDetail"
      >
        <div
          class="relative bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[92vh] overflow-hidden flex flex-col md:flex-row"
          @click.stop
        >
          <!-- 关闭按钮 -->
          <button
            type="button"
            @click="closeDetail"
            class="absolute top-2 right-2 z-10 w-8 h-8 flex items-center justify-center rounded-full bg-black/40 hover:bg-black/60 text-white text-lg leading-none"
            aria-label="关闭"
          >
            ×
          </button>

          <!-- 左侧：媒体 -->
          <div class="bg-slate-900 flex items-center justify-center md:w-3/5 w-full md:max-h-[92vh] max-h-[55vh] overflow-auto">
            <img
              v-if="detail.media_type === 'image'"
              :src="detail.media_url"
              class="max-w-full max-h-[92vh] object-contain select-none"
            />
            <video
              v-else
              :src="detail.media_url"
              class="max-w-full max-h-[92vh]"
              controls
              autoplay
              loop
            />
          </div>

          <!-- 右侧：信息 -->
          <div class="md:w-2/5 w-full flex flex-col md:max-h-[92vh] max-h-[45vh]">
            <div class="p-4 border-b border-slate-100 flex items-center gap-2">
              <img
                v-if="detail.user_avatar"
                :src="detail.user_avatar"
                class="w-8 h-8 rounded-full border border-slate-200"
              />
              <div class="min-w-0 flex-1">
                <div class="text-sm font-medium text-slate-800 truncate">{{ detail.username }}</div>
                <div class="text-[11px] text-slate-400 truncate">{{ createdAtLabel }}</div>
              </div>
              <span class="text-[11px] px-2 py-0.5 rounded bg-brand-50 text-brand-700 shrink-0">{{ detail.model }}</span>
            </div>

            <div class="px-4 py-2 border-b border-slate-100 flex items-center gap-3 text-xs text-slate-500">
              <button
                type="button"
                @click="toggleLike"
                :disabled="liking"
                class="inline-flex items-center gap-1 px-2 py-1 rounded-md border transition disabled:opacity-60"
                :class="detail.liked_by_me
                  ? 'border-rose-200 bg-rose-50 text-rose-600 hover:bg-rose-100'
                  : 'border-slate-200 hover:border-rose-300 hover:text-rose-500'"
              >
                <svg viewBox="0 0 24 24" class="w-4 h-4" :fill="detail.liked_by_me ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M12 21s-7-4.35-9.5-8.5C.5 8.5 3 4 7 4c2 0 3.5 1 5 3 1.5-2 3-3 5-3 4 0 6.5 4.5 4.5 8.5C19 16.65 12 21 12 21z"/>
                </svg>
                {{ detail.liked_by_me ? '已点赞' : '点赞' }} · {{ detail.like_count || 0 }}
              </button>
              <span class="inline-flex items-center gap-1">
                <svg viewBox="0 0 24 24" class="w-4 h-4" fill="none" stroke="currentColor" stroke-width="2">
                  <path stroke-linecap="round" stroke-linejoin="round" d="M2.5 12s3.5-7 9.5-7 9.5 7 9.5 7-3.5 7-9.5 7-9.5-7-9.5-7z"/>
                  <circle cx="12" cy="12" r="3" stroke-linecap="round" stroke-linejoin="round"/>
                </svg>
                {{ detail.view_count || 0 }} 次查看
              </span>
            </div>

            <div class="flex-1 overflow-y-auto p-4 space-y-3">
              <div>
                <div class="flex items-center justify-between mb-1.5">
                  <div class="text-xs font-medium text-slate-500">Prompt</div>
                  <button
                    type="button"
                    @click="copyPrompt"
                    class="text-xs px-2 py-0.5 rounded-md border border-slate-200 hover:border-brand-400 hover:text-brand-600 text-slate-600 transition"
                  >
                    {{ copied ? '已复制 ✓' : '复制' }}
                  </button>
                </div>
                <p
                  class="text-sm text-slate-700 whitespace-pre-wrap break-words bg-slate-50 rounded-lg p-3 border border-slate-100"
                >{{ detail.prompt || '(无)' }}</p>
              </div>

              <div v-if="Object.keys(visibleParams).length">
                <div class="text-xs font-medium text-slate-500 mb-1.5">参数</div>
                <div class="text-xs bg-slate-50 rounded-lg p-3 border border-slate-100 space-y-1 text-slate-600">
                  <div v-for="(v, k) in visibleParams" :key="k" class="flex gap-2">
                    <span class="text-slate-400 shrink-0">{{ k }}</span>
                    <span class="break-all">{{ typeof v === 'object' ? JSON.stringify(v) : v }}</span>
                  </div>
                </div>
              </div>
            </div>

            <div
              class="p-4 border-t border-slate-100 grid gap-2"
              :class="userStore.isAdmin ? 'grid-cols-3' : 'grid-cols-2'"
            >
              <button
                v-if="userStore.isAdmin"
                type="button"
                @click="adminDeleteWork"
                :disabled="deleting"
                class="text-sm py-2 rounded-lg bg-red-600 hover:bg-red-700 text-white transition disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {{ deleting ? '删除中…' : '删除作品' }}
              </button>
              <button
                type="button"
                @click="downloadMedia"
                :disabled="downloading"
                class="text-sm py-2 rounded-lg border border-slate-200 hover:border-brand-400 hover:text-brand-600 text-slate-700 transition disabled:opacity-60 disabled:cursor-not-allowed"
              >
                {{ downloading ? '下载中…' : '下载' }}
              </button>
              <button
                type="button"
                @click="remix(detail)"
                class="text-sm py-2 rounded-lg bg-brand-600 hover:bg-brand-700 text-white transition"
              >
                一键同款
              </button>
            </div>
          </div>
        </div>
      </div>
    </Transition>
  </div>
</template>
