import { apiClient } from '../../shared/api/client'
import type { SettingsData, CvSummary } from './types'

export async function getSettings(): Promise<SettingsData> {
    const response = await apiClient.get<SettingsData>('/settings/')
    return response.data
}

export async function updateSettings(data: Partial<SettingsData>): Promise<SettingsData> {
    const response = await apiClient.put<SettingsData>('/settings/', data)
    return response.data
}

// Verified against app/routers/cv_router.py:
// POST /user/upload-cv, multipart/form-data, field name "file", PDF only.
// The backend saves the result into Settings.cv_summary automatically —
// no separate PUT /settings/ call is needed after this succeeds.
export async function uploadCv(file: File): Promise<CvSummary> {
    const formData = new FormData()
    formData.append('file', file)

    const response = await apiClient.post<CvSummary>('/user/upload-cv', formData, {
        headers: { 'Content-Type': 'multipart/form-data' },
    })
    return response.data
}