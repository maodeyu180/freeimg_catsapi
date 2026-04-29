import { defineStore } from 'pinia'
import { api } from '../api'

export const useUserStore = defineStore('user', {
  state: () => ({
    user: null,
    loading: false,
  }),
  getters: {
    isLoggedIn: (s) => !!s.user,
    isAdmin: (s) => !!s.user?.is_admin,
  },
  actions: {
    setToken(token) {
      localStorage.setItem('token', token)
    },
    clear() {
      localStorage.removeItem('token')
      this.user = null
    },
    async fetchMe() {
      if (!localStorage.getItem('token')) {
        this.user = null
        return null
      }
      this.loading = true
      try {
        this.user = await api.me()
        return this.user
      } catch (_) {
        this.clear()
        return null
      } finally {
        this.loading = false
      }
    },
  },
})
