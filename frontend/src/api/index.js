function getToken() {
  return localStorage.getItem('token') || ''
}

async function request(path, { method = 'GET', body, params } = {}) {
  const qs = params
    ? '?' + new URLSearchParams(Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null))).toString()
    : ''
  const headers = { 'Content-Type': 'application/json' }
  const token = getToken()
  if (token) headers.Authorization = `Bearer ${token}`

  const resp = await fetch(path + qs, {
    method,
    headers,
    body: body ? JSON.stringify(body) : undefined,
  })

  if (resp.status === 401) {
    localStorage.removeItem('token')
    if (!location.pathname.startsWith('/auth/')) {
      location.href = '/'
    }
    throw new Error('未登录')
  }

  const text = await resp.text()
  const data = text ? JSON.parse(text) : {}
  if (!resp.ok) {
    throw new Error(data?.detail || `请求失败 (${resp.status})`)
  }
  return data
}

export const api = {
  authLogin: () => request('/api/auth/login'),
  authCallback: (code, state) => request('/api/auth/callback', { method: 'POST', body: { code, state } }),
  me: () => request('/api/auth/me'),

  listModels: () => request('/api/models'),

  createTask: (payload) => request('/api/tasks', { method: 'POST', body: payload }),
  listTasks: (limit = 50, offset = 0) => request('/api/tasks', { params: { limit, offset } }),
  getTask: (id) => request(`/api/tasks/${id}`),
  cancelTask: (id) => request(`/api/tasks/${id}/cancel`, { method: 'POST' }),

  myWorks: (offset = 0, limit = 60) => request('/api/gallery/mine', { params: { offset, limit } }),
  publicGallery: (offset = 0, limit = 24, sort = 'latest') =>
    request('/api/gallery/public', { params: { offset, limit, sort } }),
  togglePublish: (id, isPublic) => request(`/api/gallery/${id}/publish`, { method: 'PUT', body: { is_public: isPublic } }),
  deleteWork: (id) => request(`/api/gallery/${id}`, { method: 'DELETE' }),
  remixWork: (id) => request(`/api/gallery/${id}/remix`),
  toggleLike: (id) => request(`/api/gallery/${id}/like`, { method: 'POST' }),
  recordView: (id) => request(`/api/gallery/${id}/view`, { method: 'POST' }),

  adminUsers: (offset = 0, limit = 100, q) => request('/api/admin/users', { params: { offset, limit, q } }),
  adminUpdateUser: (id, patch) => request(`/api/admin/users/${id}`, { method: 'PUT', body: patch }),
  adminTasks: (offset = 0, limit = 100, status, userId) =>
    request('/api/admin/tasks', { params: { offset, limit, status, user_id: userId } }),
  adminForceCancel: (id) => request(`/api/admin/tasks/${id}/force-cancel`, { method: 'POST' }),
}
