import { apiClient } from '../../shared/api/client'
import type { UserLogin, UserCreate, TokenResponse, UserResponse } from './types'

export async function login(data: UserLogin): Promise<TokenResponse> {
    const response = await apiClient.post<TokenResponse>('/auth/login', data)
    return response.data
}

export async function register(data: UserCreate): Promise<UserResponse> {
    const response = await apiClient.post<UserResponse>('/users/', data)
    return response.data
}