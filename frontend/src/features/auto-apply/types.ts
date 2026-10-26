// Matches AutoApplyRunResponse exactly (verified against
// app/schemas/auto_apply_schema.py directly, just now)
export interface AutoApplyRunResponse {
    id: number
    user_id: number
    status: 'queued' | 'running' | 'completed' | 'completed_with_errors' | 'failed'
    total_found: number
    applied_count: number
    failed_count: number
    error_message: string | null
    started_at: string
    completed_at: string | null
}

// Matches ApplicationResultResponse exactly
export interface ApplicationResultResponse {
    id: number
    job_title: string | null
    company: string | null
    job_link: string | null
    status: 'pending' | 'submitted' | 'failed'
    error_message: string | null
    created_at: string
}

// Matches POST /auto-apply/start's 202 response body
export interface StartRunResponse {
    run_id: number
    status: string
    message: string
}