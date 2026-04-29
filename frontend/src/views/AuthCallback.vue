<script setup>
import { onMounted, ref } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import { api } from '../api'
import { useUserStore } from '../stores/user'

const router = useRouter()
const route = useRoute()
const userStore = useUserStore()
const error = ref('')

onMounted(async () => {
  const code = route.query.code
  const state = route.query.state
  if (!code) {
    error.value = '缺少 code 参数'
    return
  }
  try {
    const resp = await api.authCallback(code, state)
    userStore.setToken(resp.token)
    userStore.user = resp.user
    router.replace('/')
  } catch (e) {
    error.value = e.message
  }
})
</script>

<template>
  <div class="max-w-md mx-auto py-20 text-center">
    <template v-if="error">
      <div class="text-red-600 mb-4">登录失败：{{ error }}</div>
      <RouterLink to="/" class="text-brand-600 hover:underline">返回首页</RouterLink>
    </template>
    <template v-else>
      <div class="text-slate-500">正在登录...</div>
    </template>
  </div>
</template>
