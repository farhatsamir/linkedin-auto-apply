import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import axios from 'axios'
import { startRun, getRunStatus, getRunResults } from './api'
import { usePolling } from '../../shared/hooks/usePolling'
import './auto-apply.css'
import { getSettings } from '../settings/api'
import { getSession } from '../linkedin-connection/api'
import { useQuery as useReactQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

// Maps known backend error_message strings to clean, user-facing copy.
// Anything not in this list falls back to a generic message rather
// than showing a raw backend string to the user.
function friendlyErrorMessage(raw: string | null): string {
    if (!raw) return 'The run failed for an unknown reason.'
    if (raw.includes('No CV summary found')) return 'No CV uploaded — add one in Settings first.'
    if (raw.toLowerCase().includes('linkedin session')) return 'No LinkedIn session — reconnect LinkedIn to continue.'
    if (raw.includes('Daily application limit')) return "Today's application limit has already been reached."
    if (raw.includes('Auto Apply is disabled')) return 'Auto Apply is turned off in Settings.'
    return raw
}
const ACTIVE_RUN_STORAGE_KEY = 'auto_apply_active_run_id'

export function AutoApplyPage() {
    const { data: settingsData } = useReactQuery({
        queryKey: ['settings'],
        queryFn: getSettings,
    })

    const { data: linkedInSession } = useReactQuery({
        queryKey: ['linkedin-session'],
        queryFn: getSession,
    })

    const hasCv = Boolean(settingsData?.cv_summary)
    const hasLinkedIn = Boolean(linkedInSession)
    const isReadyToRun = hasCv && hasLinkedIn

    const [activeRunId, setActiveRunId] = useState<number | null>(() => {
        const saved = localStorage.getItem(ACTIVE_RUN_STORAGE_KEY)
        return saved ? Number(saved) : null
    })
    const [conflictMessage, setConflictMessage] = useState<string | null>(null)

    const startMutation = useMutation({
        mutationFn: startRun,
        onSuccess: (data) => {
            setConflictMessage(null)
            setActiveRunId(data.run_id)
            localStorage.setItem(ACTIVE_RUN_STORAGE_KEY, String(data.run_id))
        },
        onError: (error) => {
            if (axios.isAxiosError(error) && error.response?.status === 409) {
                const detail: string = error.response.data?.detail || ''
                const match = detail.match(/run_id=(\d+)/)
                if (match) {
                    const recoveredId = Number(match[1])
                    setActiveRunId(recoveredId)
                    localStorage.setItem(ACTIVE_RUN_STORAGE_KEY, String(recoveredId))
                } else {
                    setConflictMessage('A run is already in progress, but its ID could not be recovered.')
                }
            }
        },
    })

    const runQuery = usePolling({
        queryKey: ['auto-apply-run', activeRunId],
        queryFn: () => getRunStatus(activeRunId as number),
        intervalMs: 3000,
        enabled: Boolean(activeRunId),
        isDone: (data) => ['completed', 'completed_with_errors', 'failed'].includes(data.status),
    })

    if (runQuery.isError && activeRunId) {
        localStorage.removeItem(ACTIVE_RUN_STORAGE_KEY)
    }

    const resultsQuery = usePolling({
        queryKey: ['auto-apply-results', activeRunId],
        queryFn: () => getRunResults(activeRunId as number),
        intervalMs: 3000,
        enabled: Boolean(activeRunId),
        isDone: () => runQuery.data ? ['completed', 'completed_with_errors', 'failed'].includes(runQuery.data.status) : false,
    })

    function handleStart() {
        startMutation.mutate()
    }

    const run = runQuery.data
    const results = resultsQuery.data || []
    const isRunning = run && (run.status === 'queued' || run.status === 'running')
    const isTerminal = run && ['completed', 'completed_with_errors', 'failed'].includes(run.status)

    return (
        <div className="aa-card">
            <div className="aa-header">
                <div>
                    <h1>Auto apply</h1>
                    <p className="aa-subtitle">
                        {!run && 'Run the automation against your saved search settings.'}
                        {isRunning && 'A run is in progress.'}
                        {isTerminal && 'Your most recent run.'}
                    </p>
                </div>
                <button
                    className="aa-start-btn"
                    onClick={handleStart}
                    disabled={startMutation.isPending || Boolean(isRunning) || !isReadyToRun}
                >
                    {isRunning ? 'Run in progress' : 'Start run'}
                </button>
            </div>

            {conflictMessage && (
                <div className="aa-conflict-banner">{conflictMessage}</div>
            )}

            {!isReadyToRun && !conflictMessage && (
                <div className="aa-setup-banner">
                    <strong>Finish setup before your first run</strong>
                    <ul>
                        {!hasCv && <li>Upload your CV in <Link to="/settings">Settings</Link></li>}
                        {!hasLinkedIn && <li><Link to="/connect-linkedin">Connect LinkedIn</Link></li>}
                    </ul>
                </div>
            )}


            {!run && !conflictMessage && (
                <div className="aa-empty">
                    <strong>No runs yet</strong>
                    <p className="aa-text-muted">Start a run and applications will show up here as they are submitted.</p>
                </div>
            )}

            {run && (
                <>
                    <div className="aa-status-row">
                        <span className={`aa-badge aa-badge-${run.status}`}>
                            {run.status.replace(/_/g, ' ').toUpperCase()}
                        </span>
                        <span className="aa-text-muted">
                            {isRunning ? `Started ${new Date(run.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}` : ''}
                            {run.status === 'failed' && `Stopped ${run.completed_at ? new Date(run.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}`}
                            {(run.status === 'completed' || run.status === 'completed_with_errors') && `Finished ${run.completed_at ? new Date(run.completed_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : ''}`}
                        </span>
                    </div>

                    <div className="aa-counters">
                        <div className="aa-counter-box">
                            <span className="aa-counter-label">APPLIED</span>
                            <span className="aa-counter-value">{run.applied_count}</span>
                        </div>
                        <div className="aa-counter-box">
                            <span className="aa-counter-label">FAILED</span>
                            <span className={`aa-counter-value ${run.failed_count > 0 ? 'aa-counter-red' : ''}`}>{run.failed_count}</span>
                        </div>
                    </div>

                    {isRunning && (
                        <p className="aa-text-muted">Counters update as applications are submitted. You can leave this page.</p>
                    )}

                    {run.status === 'completed' && (
                        <p className="aa-text-muted">Every job we found matching your settings was applied to.</p>
                    )}

                    {run.status === 'completed_with_errors' && (
                        <p className="aa-text-muted">Some applications didn't go through. Failed jobs are listed below with the reason — this is normal when a posting closes or asks extra questions.</p>
                    )}

                    {run.status === 'failed' && (
                        <div className="aa-failed-banner">
                            <strong>The run stopped before applying</strong>
                            <p>{friendlyErrorMessage(run.error_message)}</p>
                        </div>
                    )}

                    {results.length > 0 && (
                        <div className="aa-results">
                            <div className="aa-results-header">
                                <span>APPLICATIONS</span>
                                <span>{results.length} job{results.length !== 1 ? 's' : ''}</span>
                            </div>
                            {results.map((app) => (
                                <div key={app.id} className="aa-result-row">
                                    <div>
                                        <strong>{app.job_title || 'Untitled role'}</strong>
                                        <p className="aa-text-muted">{app.company || 'Unknown company'}</p>
                                        {app.status === 'failed' && app.error_message && (
                                            <p className="aa-result-error">{app.error_message}</p>
                                        )}
                                    </div>
                                    <span className={`aa-mini-badge aa-mini-badge-${app.status}`}>
                                        {app.status.toUpperCase()}
                                    </span>
                                </div>
                            ))}
                        </div>
                    )}

                    {run.status === 'failed' && results.length === 0 && (
                        <p className="aa-center aa-text-muted">No applications were submitted.</p>
                    )}
                </>
            )}
        </div>
    )
}