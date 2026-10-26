import axios from 'axios'
import { apiClient } from '../../shared/api/client'
import type { LinkedInSessionResponse, ConnectStartResponse, ConnectStatusResponse } from './types'

/**
 * Returns the current LinkedIn session if one exists, or null if not
 * connected yet. A 404 from the backend is the CONFIRMED, expected
 * response when no session exists (verified against
 * LinkedInSessionService.get_session, which raises ValueError -> 404
 * when no row exists for this user). This is not an error state —
 * it's the normal "not connected yet" case.
 */
export async function getSession(): Promise<LinkedInSessionResponse | null> {
    try {
        const response = await apiClient.get<LinkedInSessionResponse>('/linkedin-session/')
        return response.data
    } catch (error) {
        if (axios.isAxiosError(error) && error.response?.status === 404) {
            return null
        }
        throw error
    }
}

export async function startConnect(): Promise<ConnectStartResponse> {
    const response = await apiClient.post<ConnectStartResponse>('/linkedin-session/connect/start')
    return response.data
}

export async function getConnectStatus(token: string): Promise<ConnectStatusResponse> {
    const response = await apiClient.get<ConnectStatusResponse>(`/linkedin-session/connect/status/${token}`)
    return response.data
}