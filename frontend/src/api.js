import axios from 'axios'

const BASE_URL = import.meta.env.VITE_API_URL || 'https://darffx-production.up.railway.app'

const api = axios.create({
  baseURL: BASE_URL,
})

// injeta token automaticamente
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token')
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

// redireciona para login se 401
api.interceptors.response.use(
  (r) => r,
  (err) => {
    if (err.response?.status === 401) {
      localStorage.removeItem('token')
      window.location.href = '/login'
    }
    return Promise.reject(err)
  }
)

export default api
