<script setup>
import { onMounted, onUnmounted, ref, computed, watch } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { api } from '../api'
import { useUserStore } from '../stores/user'
import TaskForm from '../components/TaskForm.vue'
import TaskCard from '../components/TaskCard.vue'

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()

const models = ref([])
const tasks = ref([])
const submitting = ref(false)
const errorMsg = ref('')
const prefill = ref(null)

const PAGE_SIZE = 10
const loadedLimit = ref(PAGE_SIZE) // 当前已加载的任务数；轮询时保持不变
const totalTasks = ref(0)
const loadingMore = ref(false)

let pollTimer = null

const hasActive = computed(() => tasks.value.some((t) => t.status === 'queued' || t.status === 'running'))
const hasMore = computed(() => tasks.value.length < totalTasks.value)

async function loadModels() {
  const { items } = await api.listModels()
  models.value = items
}

async function loadTasks() {
  try {
    const { items, total } = await api.listTasks(loadedLimit.value, 0)
    tasks.value = items
    totalTasks.value = total
  } catch (e) {
    // ignore transient
  }
}

async function loadMore() {
  if (loadingMore.value) return
  loadingMore.value = true
  try {
    loadedLimit.value += PAGE_SIZE
    await loadTasks()
  } finally {
    loadingMore.value = false
  }
}

function startPolling() {
  if (pollTimer) return
  pollTimer = setInterval(loadTasks, 3000)
}
function stopPolling() {
  if (pollTimer) clearInterval(pollTimer)
  pollTimer = null
}

// 只在存在 queued/running 任务时轮询，完结全部后自动停；新建任务会再次触发
watch(hasActive, (active) => {
  if (active) startPolling()
  else stopPolling()
})

async function onSubmit(payload) {
  if (!userStore.isLoggedIn) {
    alert('请先登录')
    return
  }
  submitting.value = true
  errorMsg.value = ''
  try {
    await api.createTask(payload)
    await loadTasks()
    await userStore.fetchMe()
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    submitting.value = false
  }
}

async function onCancel(task) {
  if (!confirm('确认取消该排队中的任务？')) return
  try {
    await api.cancelTask(task.id)
    await loadTasks()
  } catch (e) {
    alert(e.message)
  }
}

async function onPublish(work) {
  try {
    await api.togglePublish(work.id, !work.is_public)
    await loadTasks()
  } catch (e) {
    alert(e.message)
  }
}

async function handleRemix() {
  const id = route.query.remix
  if (!id) return
  try {
    const w = await api.remixWork(id)
    prefill.value = {
      model: w.model,
      prompt: w.prompt,
      num_images: w.params?.numImages ? Number(w.params.numImages) : 1,
      params: w.params,
    }
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    router.replace({ query: {} })
  }
}

onMounted(async () => {
  await loadModels()
  if (userStore.isLoggedIn) {
    await loadTasks()
    // 轮询由 watch(hasActive) 自己决定要不要起；这里不再无脑 startPolling
    handleRemix()
  }
})
onUnmounted(stopPolling)
</script>

<template>
  <div class="max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-6 grid lg:grid-cols-5 gap-4 sm:gap-6">
    <!-- 左：表单 -->
    <div class="lg:col-span-2 space-y-3">
      <h2 class="text-base sm:text-lg font-semibold text-slate-800">创作</h2>

      <div v-if="!userStore.isLoggedIn" class="bg-amber-50 border border-amber-200 text-amber-800 rounded-lg p-4 text-sm">
        请先使用 LinuxDo 账号登录（信任等级 ≥ 1）
      </div>

      <TaskForm
        v-if="models.length"
        :models="models"
        :disabled="!userStore.isLoggedIn || submitting || hasActive"
        :prefill="prefill"
        @submit="onSubmit"
      />

      <div v-if="errorMsg" class="text-red-600 text-sm bg-red-50 border border-red-200 rounded-lg p-3">
        {{ errorMsg }}
      </div>
    </div>

    <!-- 右：我的任务 -->
    <div class="lg:col-span-3 space-y-3">
      <div class="flex items-center justify-between">
        <h2 class="text-base sm:text-lg font-semibold text-slate-800">我的任务</h2>
        <RouterLink to="/gallery" class="text-sm text-brand-600 hover:underline">查看画廊 →</RouterLink>
      </div>

      <div v-if="!userStore.isLoggedIn" class="text-sm text-slate-400">
        登录后查看任务列表
      </div>
      <div v-else-if="!tasks.length" class="text-sm text-slate-400 bg-white rounded-xl border border-slate-200 p-8 text-center">
        还没有任务，去左边提交第一个吧 ✨
      </div>
      <div v-else class="space-y-3">
        <TaskCard v-for="t in tasks" :key="t.id" :task="t" @cancel="onCancel" @publish="onPublish" />

        <div class="flex items-center justify-center pt-2">
          <button
            v-if="hasMore"
            @click="loadMore"
            :disabled="loadingMore"
            class="text-sm px-4 py-2 rounded-lg border border-slate-200 bg-white hover:border-brand-400 hover:text-brand-600 disabled:opacity-60"
          >
            {{ loadingMore ? '加载中…' : `加载更多 (${tasks.length}/${totalTasks})` }}
          </button>
          <span v-else class="text-xs text-slate-400">已显示全部 {{ totalTasks }} 条任务</span>
        </div>
      </div>
    </div>
  </div>
</template>
