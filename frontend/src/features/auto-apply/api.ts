import { apiClient } from '../../shared/api/client'
import type { AutoApplyRunResponse, ApplicationResultResponse, StartRunResponse } from './types'

export async function startRun(): Promise<StartRunResponse> {
    const response = await apiClient.post<StartRunResponse>('/auto-apply/start')
    return response.data
}

export async function getRunStatus(runId: number): Promise<AutoApplyRunResponse> {
    const response = await apiClient.get<AutoApplyRunResponse>(`/auto-apply/runs/${runId}`)
    return response.data
}

export async function getRunResults(runId: number): Promise<ApplicationResultResponse[]> {
    const response = await apiClient.get<ApplicationResultResponse[]>(`/auto-apply/runs/${runId}/results`)
    return response.data
}