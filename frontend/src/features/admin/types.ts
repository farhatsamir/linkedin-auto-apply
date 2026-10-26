import type { AutoApplyRunResponse as BaseRunResponse } from '../auto-apply/types'

export type AutoApplyRunResponse = BaseRunResponse

// Matches the new AutoApplyRunListResponse (just added to the backend)
export interface AutoApplyRunListResponse {
    total: number
    skip: number
    limit: number
    items: AutoApplyRunResponse[]
}

export interface LogResponse {
    id: number
    user_id: number
    level: 'info' | 'warning' | 'error'
    message: string
    created_at: string
}

export interface LogListResponse {
    total: number
    skip: number
    limit: number
    items: LogResponse[]
}