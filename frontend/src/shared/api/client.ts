import axios from 'axios'

export const API_BASE_URL = 'http://127.0.0.1:8000'

export const apiClient = axios.create({
    baseURL: API_BASE_URL,
})

// Attach the JWT to every request, if we have one
apiClient.interceptors.request.use((config) => {
    const token = localStorage.getItem('access_token')
    if (token) {
        config.headers.Authorization = `Bearer ${token}`
    }
    return config
})

// Globally handle expired/revoked tokens
apiClient.interceptors.response.use(
    (response) => response,
    (error) => {
        if (error.response?.status === 401) {
            localStorage.removeItem('access_token')
            window.location.href = '/login'
        }
        return Promise.reject(error)
    }
)