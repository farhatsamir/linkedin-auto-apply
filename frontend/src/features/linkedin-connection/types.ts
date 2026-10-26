// Matches LinkedInSessionResponse exactly (verified against
// app/schemas/linkedin_session.py, pasted directly by user)
export interface LinkedInSessionResponse {
    id: number
    user_id: number
    cookies: string | null
    csrf_token: string | null
    user_agent: string | null
    session_data: string | null  // encrypted blob — never usable client-side
}

// Matches POST /linkedin-session/connect/start response
export interface ConnectStartResponse {
    token: string
}

// Matches GET /linkedin-session/connect/status/{token} response
// (verified against connect_token_service.py get_status)
export interface ConnectStatusResponse {
    status: 'pending' | 'success' | 'failed' | 'unknown'
    detail: string
}