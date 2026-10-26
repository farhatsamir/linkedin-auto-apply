import { useEffect, useRef, useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useNavigate } from 'react-router-dom'
import { getSettings, updateSettings, uploadCv } from './api'
import { getSession } from '../linkedin-connection/api'
import type { SettingsData, PersonalInfo } from './types'
import './settings.css'


export function SettingsPage() {
    const queryClient = useQueryClient()
    const fileInputRef = useRef<HTMLInputElement>(null)

    const { data, isLoading, isError } = useQuery({
        queryKey: ['settings'],
        queryFn: getSettings,
    })

    const navigate = useNavigate()

    const { data: linkedInSession } = useQuery({
        queryKey: ['linkedin-session'],
        queryFn: getSession,
    })


    const [form, setForm] = useState<SettingsData>({})
    const [showCvRequiredError, setShowCvRequiredError] = useState(false)

    useEffect(() => {
        if (data) {
            setForm(data)
        }
    }, [data])

    const saveMutation = useMutation({
        mutationFn: updateSettings,
        onSuccess: (updated) => {
            queryClient.setQueryData(['settings'], updated)
            if (linkedInSession === null) {
                navigate('/connect-linkedin')
            }
        },
    })

    const uploadMutation = useMutation({
        mutationFn: uploadCv,
        onSuccess: (cvSummary) => {
            setForm((prev) => ({ ...prev, cv_summary: cvSummary }))
            setShowCvRequiredError(false)
        },
    })

    function updatePersonal(field: keyof PersonalInfo, value: string | number) {
        setForm((prev) => ({
            ...prev,
            personal_info: { ...prev.personal_info, [field]: value },
        }))
    }

    function updateField(field: keyof SettingsData, value: string | number | boolean) {
        setForm((prev) => ({ ...prev, [field]: value }))
    }

    function handleSave(e: React.FormEvent) {
        e.preventDefault()
        if (!hasCv) {
            setShowCvRequiredError(true)
            return
        }
        setShowCvRequiredError(false)
        saveMutation.mutate(form)
    }

    function handleUploadClick() {
        fileInputRef.current?.click()
    }

    function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
        const file = e.target.files?.[0]
        if (file) {
            uploadMutation.mutate(file)
        }
        e.target.value = ''
    }

    const hasCv = Boolean(form.cv_summary)
    const isSaving = saveMutation.isPending
    const isUploading = uploadMutation.isPending
    const personal = form.personal_info || {}
    const cv = form.cv_summary

    if (isLoading) {
        return <div className="settings-card">Loading...</div>
    }

    if (isError) {
        return <div className="settings-card">Couldn't load your settings.</div>
    }

    return (
        <div className="settings-card">
            <div className="settings-logo">
                <span className="settings-logo-icon" />
                <span className="settings-logo-text">AutoApply</span>
            </div>

            <h1>Settings</h1>
            <p className="settings-subtitle">What we search for, and how many applications we send each day.</p>

            <form onSubmit={handleSave}>
                <section className="settings-section">
                    <h2>Personal details</h2>
                    <p className="settings-section-desc">Used to fill in application forms.</p>

                    <div className="settings-row">
                        <div>
                            <label className="settings-label">First name</label>
                            <input className="settings-input" value={personal.first_name || ''} disabled={isSaving}
                                placeholder="Maya"
                                onChange={(e) => updatePersonal('first_name', e.target.value)} />
                        </div>
                        <div>
                            <label className="settings-label">Last name</label>
                            <input className="settings-input" value={personal.last_name || ''} disabled={isSaving}
                                placeholder="Oduya"
                                onChange={(e) => updatePersonal('last_name', e.target.value)} />
                        </div>
                    </div>

                    <label className="settings-label">Email</label>
                    <input className="settings-input" value={personal.email || ''} disabled={isSaving}
                        placeholder="maya@company.com"
                        onChange={(e) => updatePersonal('email', e.target.value)} />

                    <div className="settings-row">
                        <div>
                            <label className="settings-label">Country code</label>
                            <input className="settings-input" value={personal.country_code || ''} disabled={isSaving}
                                placeholder="+971"
                                onChange={(e) => updatePersonal('country_code', e.target.value)} />
                        </div>
                        <div>
                            <label className="settings-label">Mobile number</label>
                            <input className="settings-input" value={personal.mobile_number || ''} disabled={isSaving}
                                placeholder="50 123 4567"
                                onChange={(e) => updatePersonal('mobile_number', e.target.value)} />
                        </div>
                    </div>

                    <div className="settings-row">
                        <div>
                            <label className="settings-label">City</label>
                            <input className="settings-input" value={personal.city || ''} disabled={isSaving}
                                placeholder="Dubai"
                                onChange={(e) => updatePersonal('city', e.target.value)} />
                        </div>
                        <div>
                            <label className="settings-label">Nationality</label>
                            <input className="settings-input" value={personal.nationality || ''} disabled={isSaving}
                                placeholder="Kenyan"
                                onChange={(e) => updatePersonal('nationality', e.target.value)} />
                        </div>
                    </div>

                    <div className="settings-row">
                        <div>
                            <label className="settings-label">Mother tongue</label>
                            <input className="settings-input" value={personal.mother_tongue || ''} disabled={isSaving}
                                placeholder="Arabic"
                                onChange={(e) => updatePersonal('mother_tongue', e.target.value)} />
                        </div>
                        <div>
                            <label className="settings-label">Second language</label>
                            <input className="settings-input" value={personal.second_language || ''} disabled={isSaving}
                                placeholder="English"
                                onChange={(e) => updatePersonal('second_language', e.target.value)} />
                        </div>
                    </div>

                    <label className="settings-label">LinkedIn profile URL</label>
                    <input className="settings-input" value={personal.linkedin_url || ''} disabled={isSaving}
                        placeholder="https://linkedin.com/in/mayaoduya"
                        onChange={(e) => updatePersonal('linkedin_url', e.target.value)} />

                    <div className="settings-row">
                        <div>
                            <label className="settings-label">Current salary</label>
                            <input className="settings-input" value={personal.current_salary || ''} disabled={isSaving}
                                placeholder="Numbers only, e.g. 32000"
                                onChange={(e) => updatePersonal('current_salary', e.target.value)} />
                        </div>
                        <div>
                            <label className="settings-label">Expected salary</label>
                            <input className="settings-input" value={personal.expected_salary || ''} disabled={isSaving}
                                placeholder="Numbers only, e.g. 40000"
                                onChange={(e) => updatePersonal('expected_salary', e.target.value)} />
                        </div>
                    </div>

                    <div className="settings-row-three">
                        <div>
                            <label className="settings-label">Availability</label>
                            <input className="settings-input" value={personal.availability || ''} disabled={isSaving}
                                placeholder="Immediate"
                                onChange={(e) => updatePersonal('availability', e.target.value)} />
                        </div>
                        <div>
                            <label className="settings-label">Notice (days)</label>
                            <input type="number" className="settings-input" value={personal.notice_period_days ?? ''} disabled={isSaving}
                                placeholder="30"
                                onChange={(e) => updatePersonal('notice_period_days', Number(e.target.value))} />
                        </div>
                        <div>
                            <label className="settings-label">Experience (yrs)</label>
                            <input type="number" className="settings-input" value={personal.years_experience ?? ''} disabled={isSaving}
                                placeholder="8"
                                onChange={(e) => updatePersonal('years_experience', Number(e.target.value))} />
                        </div>
                    </div>
                </section>

                <section className="settings-section">
                    <h2>Search</h2>
                    <p className="settings-section-desc">Which jobs we look for.</p>

                    <label className="settings-label">Keywords</label>
                    <input className="settings-input" value={form.keywords || ''} disabled={isSaving}
                        placeholder="Information Security, SOC Analysis"
                        onChange={(e) => updateField('keywords', e.target.value)} />
                    <p className="settings-hint">Comma-separated.</p>

                    <div className="settings-row">
                        <div>
                            <label className="settings-label">Locations</label>
                            <input className="settings-input" value={form.locations || ''} disabled={isSaving}
                                placeholder="UAE"
                                onChange={(e) => updateField('locations', e.target.value)} />
                        </div>
                        <div>
                            <label className="settings-label">Job types</label>
                            <input className="settings-input" value={form.job_types || ''} disabled={isSaving}
                                placeholder="full-time, Part Time , Remote"
                                onChange={(e) => updateField('job_types', e.target.value)} />
                        </div>
                    </div>

                    <label className="settings-label">Daily limit</label>
                    <div className="settings-daily-limit">
                        <input type="number" className="settings-input settings-input-small" value={form.daily_limit ?? ''} disabled={isSaving}
                            onChange={(e) => updateField('daily_limit', Number(e.target.value))} />
                        <span className="settings-hint">applications per day</span>
                    </div>
                </section>

                <section className="settings-section">
                    <div className="settings-cv-header">
                        <span>CV</span>
                        {hasCv && (
                            <a href="#" className="settings-replace-cv" onClick={(e) => { e.preventDefault(); handleUploadClick() }}>
                                Replace CV
                            </a>
                        )}
                    </div>

                    <input
                        ref={fileInputRef}
                        type="file"
                        accept="application/pdf"
                        style={{ display: 'none' }}
                        onChange={handleFileSelected}
                    />

                    {showCvRequiredError && (
                        <p className="settings-field-error">
                            Please upload your CV before saving — we need it to fill in your applications.
                        </p>
                    )}
                    {uploadMutation.isPending && (
                        <div className="settings-cv-processing">
                            <span className="settings-cv-processing-dot" />
                            <span>Reading your CV and extracting your experience — this can take a minute or two. No need to refresh or leave this page.</span>
                        </div>
                    )}
                    {uploadMutation.isError && (
                        <p className="settings-field-error">
                            {(uploadMutation.error as { response?: { data?: { detail?: string } } })?.response?.data?.detail
                                || 'Upload failed. Please try again.'}
                        </p>
                    )}

                    {uploadMutation.isSuccess && (
                        <p className="settings-cv-success">✓ CV processed successfully.</p>
                    )}

                    {hasCv && cv ? (
                        <div className="settings-cv-card">
                            <div className="settings-cv-card-header">
                                <div className="settings-cv-icon" />
                                <div>
                                    <strong>CV uploaded</strong>
                                </div>
                                <span className="settings-readonly-badge">READ ONLY</span>
                            </div>
                            <p className="settings-cv-footnote settings-cv-footnote-standalone">
                                Your CV has been processed. All your information and experience are being used to write applications on your behalf.
                            </p>
                        </div>
                    ) : (
                        <div className="settings-cv-empty">
                            <strong>No CV uploaded</strong>
                            <p className="settings-hint">We read your CV once to fill in your details and write applications. PDF only.</p>
                            <button type="button" className="settings-upload-btn" onClick={handleUploadClick} disabled={isUploading}>
                                {isUploading ? 'Uploading...' : 'Upload CV'}
                            </button>
                        </div>
                    )}
                </section>

                <section className="settings-toggle-row">
                    <div>
                        <strong>Auto apply enabled</strong>
                        <p className="settings-hint">
                            {hasCv ? 'Applying to matching jobs every day, up to your daily limit.' : "Upload a CV first — we can't apply without one."}
                        </p>
                    </div>
                    <label className="settings-switch">
                        <input
                            type="checkbox"
                            checked={Boolean(form.auto_apply_enabled)}
                            disabled={!hasCv || isSaving}
                            onChange={(e) => updateField('auto_apply_enabled', e.target.checked)}
                        />
                        <span className="settings-switch-slider" />
                    </label>
                </section>

                <div className="settings-footer">
                    <span className="settings-save-status">
                        {saveMutation.isSuccess && '✓ Changes saved'}
                        {saveMutation.isError && "• Couldn't save changes, try again"}
                        {isUploading && 'Waiting for CV processing to finish...'}
                    </span>
                    <button type="submit" className="settings-save-btn" disabled={isSaving || isUploading}>
                        {isSaving ? 'Saving' : 'Save changes'}
                    </button>
                </div>
            </form>
        </div>
    )
}