import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  { path: '/', component: () => import('../views/Home.vue'), meta: { title: '工作台' } },
  { path: '/gallery', component: () => import('../views/Gallery.vue'), meta: { title: '画廊' } },
  { path: '/admin', component: () => import('../views/Admin.vue'), meta: { title: '管理', adminOnly: true } },
  { path: '/auth/callback', component: () => import('../views/AuthCallback.vue'), meta: { title: '登录中' } },
]

const router = createRouter({
  history: createWebHistory(),
  routes,
})

router.afterEach((to) => {
  if (to.meta?.title) document.title = `${to.meta.title} · 喵的公益生图`
})

export default router
