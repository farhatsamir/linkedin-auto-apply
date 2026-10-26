export interface PersonalInfo {
    first_name?: string
    last_name?: string
    email?: string
    country_code?: string
    mobile_number?: string
    city?: string
    nationality?: string
    linkedin_url?: string
    current_salary?: string
    expected_salary?: string
    availability?: string
    notice_period_days?: number
    years_experience?: number
    mother_tongue?: string
    second_language?: string
}

// Matches CVSummaryResponse exactly (verified against app/schemas/cv_schema.py)
export interface WorkHistoryEntry {
    title: string
    company: string
    city: string
    start_month?: number | null
    start_year?: number | null
    end_month?: number | null
    end_year?: number | null
    description: string
    is_current: boolean
}

export interface CvSummary {
    summary: string
    core_skills: string[]
    experience_highlights: string[]
    technical_skills: string[]
    domains: string[]
    certifications: string[]
    work_history: WorkHistoryEntry[]
}

export interface SettingsData {
    keywords?: string
    locations?: string
    job_types?: string
    daily_limit?: number
    auto_apply_enabled?: boolean
    cv_summary?: CvSummary | null
    personal_info?: PersonalInfo | null
}