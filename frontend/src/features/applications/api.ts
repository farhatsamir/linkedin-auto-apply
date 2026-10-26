import { apiClient } from '../../shared/api/client'
import type { ApplicationListResponse } from './types'

export async function getApplications(skip: number, limit: number): Promise<ApplicationListResponse> {
    const response = await apiClient.get<ApplicationListResponse>('/applications/', {
        params: { skip, limit },
    })
    return response.data
}