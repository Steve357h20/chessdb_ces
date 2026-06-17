import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { login as loginApi, register as registerApi, getProfile, updateProfile, logout as logoutApi } from '@/api/auth'

export const useUserStore = defineStore('user', () => {
  const user = ref(null)
  const token = ref(localStorage.getItem('token') || '')
  const isLoggedIn = computed(() => !!token.value)
  const isAdmin = computed(() => !!(user.value && (user.value.is_admin || user.value.role === 'admin')))

  async function login(credentials) {
    const res = await loginApi(credentials)
    const data = res.data || res
    if (data.token) {
      token.value = data.token
      localStorage.setItem('token', data.token)
    }
    if (data.user) {
      user.value = data.user
    }
    return data
  }

  async function register(data) {
    const res = await registerApi(data)
    return res.data || res
  }

  async function fetchUser() {
    if (!token.value) return null
    try {
      const res = await getProfile()
      const data = res.data || res
      user.value = data
      return data
    } catch {
      user.value = null
      return null
    }
  }

  async function updateUserData(data) {
    const res = await updateProfile(data)
    const updated = res.data || res
    user.value = updated
    return updated
  }

  async function logout() {
    try {
      await logoutApi()
    } catch {
      // ignore
    }
    token.value = ''
    user.value = null
    localStorage.removeItem('token')
  }

  async function checkAuth() {
    if (!token.value) {
      user.value = null
      return false
    }
    try {
      await fetchUser()
      return !!user.value
    } catch {
      token.value = ''
      localStorage.removeItem('token')
      user.value = null
      return false
    }
  }

  return {
    user,
    token,
    isLoggedIn,
    isAdmin,
    login,
    register,
    fetchUser,
    updateUserData,
    logout,
    checkAuth,
  }
})
