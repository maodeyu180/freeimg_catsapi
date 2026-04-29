<script setup>
import { onMounted, onUnmounted, ref, computed } from 'vue'
import { useRouter } from 'vue-router'
import { api } from '../api'
import { useUserStore } from '../stores/user'
import Pagination from '../components/Pagination.vue'
import { formatBeijingTime } from '../utils/time'

const userStore = useUserStore()
const router = useRouter()

const tab = ref('users')
const loading = ref(false)
const errorMsg = ref('')

// 用户分页
const PAGE_SIZE = 20
const users = ref([])
const usersTotal = ref(0)
const usersPage = ref(1)
const usersSearchInput = ref('')
const usersSearch = ref('')
const usersTotalPages = computed(() => Math.max(1, Math.ceil(usersTotal.value / PAGE_SIZE)))

// 任务分页
const tasks = ref([])
const tasksTotal = ref(0)
const tasksPage = ref(1)
const tasksTotalPages = computed(() => Math.max(1, Math.ceil(tasksTotal.value / PAGE_SIZE)))

// 用户任务弹窗
const userTasksOpen = ref(false)
const userTasksUser = ref(null)
const userTasks = ref([])
const userTasksTotal = ref(0)
const userTasksPage = ref(1)
const userTasksLoading = ref(false)
const USER_TASKS_PAGE_SIZE = 10
const userTasksTotalPages = computed(() =>
  Math.max(1, Math.ceil(userTasksTotal.value / USER_TASKS_PAGE_SIZE))
)

const STATUS_LABEL = {
  queued: '排队中',
  running: '生成中',
  completed: '已完成',
  failed: '失败',
  cancelled: '已取消',
}
const STATUS_CLASS = {
  queued: 'text-amber-600 bg-amber-50',
  running: 'text-brand-600 bg-brand-50',
  completed: 'text-emerald-600 bg-emerald-50',
  failed: 'text-red-600 bg-red-50',
  cancelled: 'text-slate-500 bg-slate-100',
}

async function loadUsers() {
  loading.value = true
  errorMsg.value = ''
  try {
    const offset = (usersPage.value - 1) * PAGE_SIZE
    const { items, total } = await api.adminUsers(offset, PAGE_SIZE, usersSearch.value || undefined)
    users.value = items
    usersTotal.value = total
    if (!items.length && usersPage.value > 1) {
      usersPage.value = Math.max(1, usersPage.value - 1)
      await loadUsers()
    }
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

async function loadTasks() {
  loading.value = true
  errorMsg.value = ''
  try {
    const offset = (tasksPage.value - 1) * PAGE_SIZE
    const { items, total } = await api.adminTasks(offset, PAGE_SIZE)
    tasks.value = items
    tasksTotal.value = total
    if (!items.length && tasksPage.value > 1) {
      tasksPage.value = Math.max(1, tasksPage.value - 1)
      await loadTasks()
    }
  } catch (e) {
    errorMsg.value = e.message
  } finally {
    loading.value = false
  }
}

function switchTab(next) {
  tab.value = next
  if (next === 'users') {
    usersPage.value = 1
    loadUsers()
  } else {
    tasksPage.value = 1
    loadTasks()
  }
}

function searchUsers() {
  usersSearch.value = usersSearchInput.value.trim()
  usersPage.value = 1
  loadUsers()
}

function clearUserSearch() {
  if (!usersSearchInput.value && !usersSearch.value) return
  usersSearchInput.value = ''
  usersSearch.value = ''
  usersPage.value = 1
  loadUsers()
}

function gotoUsersPage(p) {
  if (p < 1 || p > usersTotalPages.value || p === usersPage.value) return
  usersPage.value = p
  loadUsers()
}
function gotoTasksPage(p) {
  if (p < 1 || p > tasksTotalPages.value || p === tasksPage.value) return
  tasksPage.value = p
  loadTasks()
}

async function toggleBan(u) {
  try {
    const updated = await api.adminUpdateUser(u.id, { is_banned: !u.is_banned })
    Object.assign(u, updated)
  } catch (e) {
    alert(e.message)
  }
}

async function updateQuota(u, field) {
  const label = field === 'daily_image_limit' ? '图片' : '视频'
  const input = prompt(`设置 ${u.username} 每日${label}配额`, String(u[field]))
  if (input === null) return
  const n = Number(input)
  if (!Number.isFinite(n) || n < 0) {
    alert('必须是非负数字')
    return
  }
  try {
    const updated = await api.adminUpdateUser(u.id, { [field]: n })
    Object.assign(u, updated)
  } catch (e) {
    alert(e.message)
  }
}

async function forceCancel(t) {
  if (!confirm('强制取消该任务？')) return
  try {
    await api.adminForceCancel(t.id)
    await loadTasks()
  } catch (e) {
    alert(e.message)
  }
}

function lockBodyScroll() {
  document.body.style.overflow = 'hidden'
}
function maybeUnlockBodyScroll() {
  if (!userTasksOpen.value) {
    document.body.style.overflow = ''
  }
}

async function openUserTasks(u) {
  userTasksUser.value = u
  userTasksOpen.value = true
  userTasksPage.value = 1
  userTasks.value = []
  userTasksTotal.value = 0
  lockBodyScroll()
  await loadUserTasks()
}
function closeUserTasks() {
  userTasksOpen.value = false
  userTasksUser.value = null
  userTasks.value = []
  userTasksTotal.value = 0
  maybeUnlockBodyScroll()
}
async function loadUserTasks() {
  if (!userTasksUser.value) return
  userTasksLoading.value = true
  try {
    const offset = (userTasksPage.value - 1) * USER_TASKS_PAGE_SIZE
    const { items, total } = await api.adminTasks(
      offset,
      USER_TASKS_PAGE_SIZE,
      undefined,
      userTasksUser.value.id,
    )
    userTasks.value = items
    userTasksTotal.value = total
    if (!items.length && userTasksPage.value > 1) {
      userTasksPage.value = Math.max(1, userTasksPage.value - 1)
      await loadUserTasks()
    }
  } catch (e) {
    alert(e.message)
  } finally {
    userTasksLoading.value = false
  }
}
function gotoUserTasksPage(p) {
  if (p < 1 || p > userTasksTotalPages.value || p === userTasksPage.value) return
  userTasksPage.value = p
  loadUserTasks()
}

function onKeydown(e) {
  if (e.key !== 'Escape') return
  if (userTasksOpen.value) {
    closeUserTasks()
  }
}

onMounted(async () => {
  await userStore.fetchMe()
  if (!userStore.isAdmin) {
    router.replace('/')
    return
  }
  loadUsers()
  window.addEventListener('keydown', onKeydown)
})
onUnmounted(() => {
  window.removeEventListener('keydown', onKeydown)
  document.body.style.overflow = ''
})
</script>

<template>
  <div class="max-w-6xl mx-auto px-3 sm:px-4 py-4 sm:py-6">
    <div class="flex flex-wrap items-center gap-3 mb-4">
      <h1 class="text-lg sm:text-xl font-semibold">管理后台</h1>
      <div class="flex bg-white rounded-lg border border-slate-200 p-0.5">
        <button
          @click="switchTab('users')"
          :class="['px-3 py-1 text-sm rounded-md',
                   tab === 'users' ? 'bg-brand-600 text-white' : 'text-slate-600']"
        >
          用户
        </button>
        <button
          @click="switchTab('tasks')"
          :class="['px-3 py-1 text-sm rounded-md',
                   tab === 'tasks' ? 'bg-brand-600 text-white' : 'text-slate-600']"
        >
          任务
        </button>
      </div>
    </div>

    <div v-if="errorMsg" class="text-red-600 text-sm mb-4">{{ errorMsg }}</div>

    <!-- 用户 -->
    <div v-if="tab === 'users'" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <form
        class="p-3 border-b border-slate-100 flex flex-col sm:flex-row gap-2 sm:items-center"
        @submit.prevent="searchUsers"
      >
        <input
          v-model="usersSearchInput"
          type="search"
          placeholder="搜索用户名"
          class="w-full sm:max-w-xs px-3 py-2 text-sm rounded-lg border border-slate-200 focus:outline-none focus:ring-2 focus:ring-brand-100 focus:border-brand-400"
        />
        <div class="flex gap-2">
          <button
            type="submit"
            class="px-3 py-2 text-sm rounded-lg bg-brand-600 hover:bg-brand-700 text-white disabled:opacity-60"
            :disabled="loading"
          >
            搜索
          </button>
          <button
            type="button"
            class="px-3 py-2 text-sm rounded-lg border border-slate-200 text-slate-600 hover:border-brand-400 hover:text-brand-600 disabled:opacity-60"
            :disabled="loading || (!usersSearchInput && !usersSearch)"
            @click="clearUserSearch"
          >
            清空
          </button>
        </div>
        <span v-if="usersSearch" class="text-xs text-slate-400 sm:ml-auto">
          当前搜索：{{ usersSearch }}
        </span>
      </form>
      <div class="overflow-x-auto">
        <table class="w-full text-sm min-w-[640px]">
          <thead class="bg-slate-50 text-slate-500 text-xs">
            <tr>
              <th class="text-left px-3 py-2">用户</th>
              <th class="text-left px-3 py-2">LinuxDo ID</th>
              <th class="text-left px-3 py-2">信任等级</th>
              <th class="text-left px-3 py-2">图配额/天</th>
              <th class="text-left px-3 py-2">视频配额/天</th>
              <th class="text-left px-3 py-2">状态</th>
              <th class="text-right px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="u in users"
              :key="u.id"
              class="border-t border-slate-100 hover:bg-slate-50 cursor-pointer"
              @click="openUserTasks(u)"
            >
              <td class="px-3 py-2">
                <div class="flex items-center gap-2">
                  <img v-if="u.avatar_url" :src="u.avatar_url" class="w-6 h-6 rounded-full shrink-0" />
                  <span class="truncate max-w-[120px]">{{ u.username }}</span>
                  <span v-if="u.is_admin" class="text-xs text-brand-600 shrink-0">(admin)</span>
                </div>
              </td>
              <td class="px-3 py-2 text-slate-400">{{ u.linuxdo_id }}</td>
              <td class="px-3 py-2">{{ u.trust_level }}</td>
              <td class="px-3 py-2" @click.stop>
                <button @click="updateQuota(u, 'daily_image_limit')" class="hover:text-brand-600 underline decoration-dotted">{{ u.daily_image_limit }}</button>
              </td>
              <td class="px-3 py-2" @click.stop>
                <button @click="updateQuota(u, 'daily_video_limit')" class="hover:text-brand-600 underline decoration-dotted">{{ u.daily_video_limit }}</button>
              </td>
              <td class="px-3 py-2">
                <span v-if="u.is_banned" class="text-red-600">已封禁</span>
                <span v-else class="text-emerald-600">正常</span>
              </td>
              <td class="px-3 py-2 text-right whitespace-nowrap" @click.stop>
                <button
                  @click="toggleBan(u)"
                  class="text-xs px-2 py-1 rounded"
                  :class="u.is_banned ? 'bg-emerald-100 text-emerald-700 hover:bg-emerald-200' : 'bg-red-100 text-red-700 hover:bg-red-200'"
                >
                  {{ u.is_banned ? '解封' : '封禁' }}
                </button>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!users.length && !loading" class="text-slate-400 text-sm p-6 text-center">暂无用户</div>

      <Pagination
        v-if="usersTotal > 0"
        :page="usersPage"
        :total-pages="usersTotalPages"
        :total="usersTotal"
        :loading="loading"
        @change="gotoUsersPage"
      />
    </div>

    <!-- 任务 -->
    <div v-if="tab === 'tasks'" class="bg-white rounded-xl border border-slate-200 overflow-hidden">
      <div class="overflow-x-auto">
        <table class="w-full text-sm min-w-[720px]">
          <thead class="bg-slate-50 text-slate-500 text-xs">
            <tr>
              <th class="text-left px-3 py-2">用户</th>
              <th class="text-left px-3 py-2">模型</th>
              <th class="text-left px-3 py-2">提示词</th>
              <th class="text-left px-3 py-2">状态</th>
              <th class="text-left px-3 py-2">时间</th>
              <th class="text-right px-3 py-2">操作</th>
            </tr>
          </thead>
          <tbody>
            <tr
              v-for="t in tasks"
              :key="t.id"
              class="border-t border-slate-100"
            >
              <td class="px-3 py-2 whitespace-nowrap">{{ t.username }}</td>
              <td class="px-3 py-2 text-slate-400 whitespace-nowrap">{{ t.model }}</td>
              <td class="px-3 py-2 max-w-[260px] truncate" :title="t.prompt">{{ t.prompt }}</td>
              <td class="px-3 py-2 whitespace-nowrap">
                <span class="text-xs px-2 py-0.5 rounded" :class="STATUS_CLASS[t.status] || 'text-slate-500 bg-slate-100'">
                  {{ STATUS_LABEL[t.status] || t.status }}
                </span>
              </td>
              <td class="px-3 py-2 text-slate-400 text-xs whitespace-nowrap">{{ formatBeijingTime(t.created_at) }}</td>
              <td class="px-3 py-2 text-right whitespace-nowrap">
                <button
                  v-if="t.status === 'queued' || t.status === 'running'"
                  @click="forceCancel(t)"
                  class="text-xs px-2 py-1 rounded bg-red-100 text-red-700 hover:bg-red-200"
                >
                  强制取消
                </button>
                <span v-else class="text-xs text-slate-400">—</span>
              </td>
            </tr>
          </tbody>
        </table>
      </div>
      <div v-if="!tasks.length && !loading" class="text-slate-400 text-sm p-6 text-center">暂无任务</div>

      <Pagination
        v-if="tasksTotal > 0"
        :page="tasksPage"
        :total-pages="tasksTotalPages"
        :total="tasksTotal"
        :loading="loading"
        @change="gotoTasksPage"
      />
    </div>

    <!-- 用户任务弹窗 -->
    <Transition
      enter-active-class="transition duration-150 ease-out"
      enter-from-class="opacity-0"
      enter-to-class="opacity-100"
      leave-active-class="transition duration-150 ease-in"
      leave-from-class="opacity-100"
      leave-to-class="opacity-0"
    >
      <div
        v-if="userTasksOpen"
        class="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm flex items-center justify-center p-3 sm:p-6"
        @click.self="closeUserTasks"
      >
        <div
          class="relative bg-white rounded-2xl shadow-2xl w-full max-w-3xl max-h-[88vh] overflow-hidden flex flex-col"
          @click.stop
        >
          <div class="flex items-center gap-3 p-4 border-b border-slate-100">
            <img v-if="userTasksUser?.avatar_url" :src="userTasksUser.avatar_url" class="w-8 h-8 rounded-full border border-slate-200" />
            <div class="min-w-0 flex-1">
              <div class="text-sm font-semibold text-slate-800 truncate">
                {{ userTasksUser?.username }}
                <span v-if="userTasksUser?.is_admin" class="text-xs text-brand-600 ml-1">(admin)</span>
              </div>
              <div class="text-[11px] text-slate-400">
                LinuxDo ID {{ userTasksUser?.linuxdo_id }} ·
                信任等级 {{ userTasksUser?.trust_level }} ·
                共 {{ userTasksTotal }} 条任务
              </div>
            </div>
            <button
              type="button"
              @click="closeUserTasks"
              class="w-8 h-8 flex items-center justify-center rounded-full bg-slate-100 hover:bg-slate-200 text-slate-500 text-lg leading-none"
              aria-label="关闭"
            >
              ×
            </button>
          </div>

          <div class="flex-1 overflow-y-auto">
            <div v-if="userTasksLoading && !userTasks.length" class="p-8 text-center text-sm text-slate-400">加载中…</div>
            <div v-else-if="!userTasks.length" class="p-8 text-center text-sm text-slate-400">该用户暂无任务</div>
            <ul v-else class="divide-y divide-slate-100">
              <li
                v-for="t in userTasks"
                :key="t.id"
                class="p-3"
              >
                <div class="flex items-center gap-2 mb-1 text-xs">
                  <span class="px-2 py-0.5 rounded" :class="STATUS_CLASS[t.status] || 'text-slate-500 bg-slate-100'">
                    {{ STATUS_LABEL[t.status] || t.status }}
                  </span>
                  <span class="text-slate-400 truncate">{{ t.model }}</span>
                  <span class="ml-auto text-slate-400 shrink-0">{{ formatBeijingTime(t.created_at) }}</span>
                </div>
                <p class="text-sm text-slate-700 line-clamp-2 break-words">{{ t.prompt }}</p>
                <div v-if="t.status === 'failed' && t.error_message" class="mt-1 text-xs text-red-500 line-clamp-1">
                  {{ t.error_message }}
                </div>
              </li>
            </ul>
          </div>

          <Pagination
            v-if="userTasksTotal > 0"
            :page="userTasksPage"
            :total-pages="userTasksTotalPages"
            :total="userTasksTotal"
            :loading="userTasksLoading"
            @change="gotoUserTasksPage"
          />
        </div>
      </div>
    </Transition>

  </div>
</template>
