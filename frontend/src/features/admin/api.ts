import { apiClient } from '../../shared/api/client'
import type { AutoApplyRunResponse, AutoApplyRunListResponse, LogListResponse } from './types'

export async function getAllRuns(status: string | null, skip: number, limit: number): Promise<AutoApplyRunListResponse> {
    const response = await apiClient.get<AutoApplyRunListResponse>('/auto-apply/admin/runs', {
        params: { status: status || undefined, skip, limit },
    })
    return response.data
}

export async function getActiveRuns(): Promise<AutoApplyRunResponse[]> {
    const response = await apiClient.get<AutoApplyRunResponse[]>('/auto-apply/admin/runs/active')
    return response.data
}

export async function cancelRun(runId: number): Promise<{ message: string; run_id: number }> {
    const response = await apiClient.post(`/auto-apply/admin/runs/${runId}/cancel`)
    return response.data
}

export async function getAllLogs(level: string | null, skip: number, limit: number): Promise<LogListResponse> {
    const response = await apiClient.get<LogListResponse>('/logs/admin/all', {
        params: { level: level || undefined, skip, limit },
    })
    return response.data
}