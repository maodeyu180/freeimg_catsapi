<script setup>
import { onMounted, computed } from 'vue'
import { RouterView, RouterLink, useRoute, useRouter } from 'vue-router'
import { useUserStore } from './stores/user'
import { api } from './api'

const userStore = useUserStore()
const route = useRoute()
const router = useRouter()

onMounted(async () => {
  await userStore.fetchMe()
})

const imgQuota = computed(() => {
  if (!userStore.user) return ''
  const u = userStore.user
  return `${u.used_today_images}/${u.daily_image_limit}`
})
const vidQuota = computed(() => {
  if (!userStore.user) return ''
  const u = userStore.user
  return `${u.used_today_videos}/${u.daily_video_limit}`
})

async function login() {
  const { url } = await api.authLogin()
  location.href = url
}
function logout() {
  userStore.clear()
  router.push('/')
}
</script>

<template>
  <div class="min-h-screen flex flex-col">
    <header class="bg-white border-b border-slate-200 sticky top-0 z-10 backdrop-blur bg-white/80">
      <div class="max-w-6xl mx-auto px-3 sm:px-4 h-14 flex items-center gap-2 sm:gap-6">
        <RouterLink to="/" class="font-bold text-brand-700 text-base sm:text-lg flex items-center gap-2 shrink-0">
          <img src="/cat_64.png" alt="喵的公益生图" class="w-7 h-7 rounded" />
          <span class="hidden sm:inline">喵的公益生图</span>
        </RouterLink>
        <nav class="flex gap-0.5 sm:gap-1 text-sm">
          <RouterLink
            to="/"
            class="px-2 sm:px-3 py-1.5 rounded-lg hover:bg-brand-50"
            :class="route.path === '/' ? 'text-brand-700 bg-brand-50 font-medium' : 'text-slate-600'"
          >
            工作台
          </RouterLink>
          <RouterLink
            to="/gallery"
            class="px-2 sm:px-3 py-1.5 rounded-lg hover:bg-brand-50"
            :class="route.path === '/gallery' ? 'text-brand-700 bg-brand-50 font-medium' : 'text-slate-600'"
          >
            画廊
          </RouterLink>
          <RouterLink
            v-if="userStore.isAdmin"
            to="/admin"
            class="px-2 sm:px-3 py-1.5 rounded-lg hover:bg-brand-50"
            :class="route.path === '/admin' ? 'text-brand-700 bg-brand-50 font-medium' : 'text-slate-600'"
          >
            管理
          </RouterLink>
        </nav>

        <div class="ml-auto flex items-center gap-2 sm:gap-4 min-w-0">
          <template v-if="userStore.isLoggedIn">
            <div class="hidden md:flex items-center gap-3 text-xs text-slate-500">
              <span>今日：图 {{ imgQuota }} / 视频 {{ vidQuota }}</span>
            </div>
            <div class="flex items-center gap-1.5 sm:gap-2 min-w-0">
              <img
                v-if="userStore.user.avatar_url"
                :src="userStore.user.avatar_url"
                class="w-7 h-7 sm:w-8 sm:h-8 rounded-full border border-slate-200 shrink-0"
              />
              <span class="text-sm text-slate-700 hidden sm:inline truncate max-w-[120px]">{{ userStore.user.username }}</span>
              <button @click="logout" class="text-xs text-slate-500 hover:text-brand-600 shrink-0">登出</button>
            </div>
          </template>
          <template v-else>
            <button
              @click="login"
              class="px-3 sm:px-4 py-1.5 bg-brand-600 hover:bg-brand-700 text-white rounded-lg text-xs sm:text-sm font-medium whitespace-nowrap"
            >
              LinuxDo 登录
            </button>
          </template>
        </div>
      </div>

      <!-- 手机端：顶部栏下方显示今日配额 -->
      <div
        v-if="userStore.isLoggedIn"
        class="md:hidden max-w-6xl mx-auto px-3 sm:px-4 pb-2 text-xs text-slate-500"
      >
        今日：图 {{ imgQuota }} · 视频 {{ vidQuota }}
      </div>
    </header>

    <main class="flex-1">
      <RouterView />
    </main>

    <footer class="text-center text-xs text-slate-400 py-4 border-t border-slate-100">
      仅限 LinuxDo 信任等级 ≥ 1 的用户使用 · 2 并发 · 每用户单任务
    </footer>
  </div>
</template>
