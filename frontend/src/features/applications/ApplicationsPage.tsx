import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { getApplications } from './api'
import './applications.css'

const PAGE_SIZE = 10

export function ApplicationsPage() {
    const [skip, setSkip] = useState(0)

    const { data, isLoading, isError, refetch } = useQuery({
        queryKey: ['applications', skip],
        queryFn: () => getApplications(skip, PAGE_SIZE),
    })

    function formatDate(dateStr: string): string {
        const date = new Date(dateStr)
        const now = new Date()
        const diffMs = now.getTime() - date.getTime()
        const diffHours = diffMs / (1000 * 60 * 60)

        if (diffHours < 24) {
            if (diffHours < 1) return 'Just now'
            return `${Math.floor(diffHours)} hour${Math.floor(diffHours) !== 1 ? 's' : ''} ago`
        }
        if (diffHours < 48) return 'Yesterday'
        return date.toLocaleDateString([], { day: 'numeric', month: 'short' })
    }

    if (isLoading) {
        return (
            <div className="ap-card">
                <div className="ap-header">
                    <h1>Applications</h1>
                    <p className="ap-subtitle">Everything AutoApply has submitted for you.</p>
                </div>
                <div className="ap-skeleton-list">
                    {[1, 2, 3, 4, 5].map((i) => (
                        <div key={i} className="ap-skeleton-row">
                            <div className="ap-skeleton-line ap-skeleton-title" />
                            <div className="ap-skeleton-line ap-skeleton-sub" />
                        </div>
                    ))}
                </div>
            </div>
        )
    }

    if (isError) {
        return (
            <div className="ap-card">
                <div className="ap-header">
                    <h1>Applications</h1>
                    <p className="ap-subtitle">Everything AutoApply has submitted for you.</p>
                </div>
                <div className="ap-empty">
                    <strong>Couldn't load your applications</strong>
                    <p className="ap-text-muted">The list didn't come back. Nothing has been lost — your history is intact.</p>
                    <button className="ap-retry-btn" onClick={() => refetch()}>Try again</button>
                </div>
            </div>
        )
    }

    const items = data?.items || []
    const total = data?.total || 0

    return (
        <div className="ap-card">
            <div className="ap-header">
                <h1>Applications</h1>
                <p className="ap-subtitle">
                    {total > 0 ? `${total} application${total !== 1 ? 's' : ''}, newest first` : 'Everything AutoApply has submitted for you.'}
                </p>
            </div>

            {items.length === 0 ? (
                <div className="ap-empty">
                    <strong>No applications yet</strong>
                    <p className="ap-text-muted">Start a run to see results here.</p>
                </div>
            ) : (
                <>
                    <div className="ap-list">
                        {items.map((app) => (
                            <div key={app.id} className="ap-row">
                                <div className="ap-row-main">
                                    <strong>{app.job_title || 'Untitled role'}</strong>
                                    <p className="ap-text-muted">{app.company || 'Unknown company'}</p>
                                    {app.status === 'failed' && app.error_message && (
                                        <p className="ap-row-error">{app.error_message}</p>
                                    )}
                                </div>
                                <div className="ap-row-meta">
                                    <span className={`ap-badge ap-badge-${app.status}`}>{app.status.toUpperCase()}</span>
                                    <span className="ap-text-muted">{formatDate(app.created_at)}</span>
                                </div>
                            </div>
                        ))}
                    </div>

                    <div className="ap-footer">
                        <span className="ap-text-muted">
                            Showing {skip + 1}–{Math.min(skip + PAGE_SIZE, total)} of {total}
                        </span>
                        <div className="ap-pagination">
                            <button
                                className="ap-page-btn"
                                onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))}
                                disabled={skip === 0}
                            >
                                Previous
                            </button>
                            <button
                                className="ap-page-btn"
                                onClick={() => setSkip(skip + PAGE_SIZE)}
                                disabled={skip + PAGE_SIZE >= total}
                            >
                                Next
                            </button>
                        </div>
                    </div>
                </>
            )}
        </div>
    )
}