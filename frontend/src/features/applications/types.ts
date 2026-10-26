// Matches ApplicationResponse and ApplicationListResponse exactly
// (verified directly by user pasting the real router + earlier-confirmed
// schema in the same session)
export interface ApplicationResponse {
    id: number
    user_id: number
    job_title: string | null
    company: string | null
    job_link: string | null
    job_description: string | null
    status: 'pending' | 'submitted' | 'failed'
    error_message: string | null
    created_at: string
}

export interface ApplicationListResponse {
    total: number
    skip: number
    limit: number
    items: ApplicationResponse[]
}