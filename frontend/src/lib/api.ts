import axios from 'axios'

export const API_BASE = (import.meta.env.VITE_API_URL || (import.meta.env.DEV ? 'http://localhost:8000' : '')).replace(/\/+$/, '')
export const WS_BASE = API_BASE.replace(/^http/, 'ws')

export const api = axios.create({
  baseURL: API_BASE,
  timeout: 15000,
})

api.interceptors.request.use((config) => {
  const token = localStorage.getItem('queueflow_token')
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      localStorage.removeItem('queueflow_token')
      if (window.location.pathname !== '/login') {
        window.location.href = '/login'
      }
    }
    return Promise.reject(error)
  }
)

export function extractErrorMessage(error: unknown): string {
  if (axios.isAxiosError(error)) {
    const detail = error.response?.data?.detail
    if (typeof detail === 'string') return detail
    if (Array.isArray(detail) && detail[0]?.msg) return detail[0].msg
    if (error.message === 'Network Error') return 'Could not reach the server. Is the backend running?'
  }
  return 'Something went wrong. Please try again.'
}
