import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { useQuery as useReactQuery } from '@tanstack/react-query'
import { getSession, startConnect } from './api'
import { getConnectStatus } from './api'
import { usePolling } from '../../shared/hooks/usePolling'
import './linkedin-connection.css'

const MOBILE_BREAKPOINT = 768

export function LinkedInConnectionPage() {
    const queryClient = useQueryClient()
    const isMobile = window.innerWidth < MOBILE_BREAKPOINT

    const [activeToken, setActiveToken] = useState<string | null>(null)
    const [justConnected, setJustConnected] = useState(false)

    const { data: session, isLoading: sessionLoading } = useQuery({
        queryKey: ['linkedin-session'],
        queryFn: getSession,
    })

    const startMutation = useMutation({
        mutationFn: startConnect,
        onSuccess: (data) => {
            setActiveToken(data.token)
            window.location.href = `linkedinautoapply://connect?token=${data.token}`
        },
    })

    const statusQuery = usePolling({
        queryKey: ['connect-status', activeToken],
        queryFn: () => getConnectStatus(activeToken as string),
        intervalMs: 2000,
        enabled: Boolean(activeToken),
        isDone: (data) => data.status === 'success' || data.status === 'failed',
    })

    // Current logged-in AutoApply user's own email (verified: LinkedInSessionResponse
    // has no email field at all — this is the only real email we have access to).
    const { data: currentUser } = useReactQuery({
        queryKey: ['current-user'],
        queryFn: async () => {
            const { apiClient } = await import('../../shared/api/client')
            const res = await apiClient.get('/users/me')
            return res.data as { email: string }
        },
    })

    // React to a completed poll
    if (statusQuery.data?.status === 'success' && activeToken) {
        if (!justConnected) {
            setJustConnected(true)
            setActiveToken(null)
            queryClient.invalidateQueries({ queryKey: ['linkedin-session'] })
        }
    }

    function handleConnectClick() {
        startMutation.mutate()
    }

    function handleStopWaiting() {
        setActiveToken(null)
    }

    function handleReopenApp() {
        if (activeToken) {
            window.location.href = `linkedinautoapply://connect?token=${activeToken}`
        }
    }

    if (isMobile) {
        return (
            <div className="li-card">
                <div className="li-card-header">
                    <div className="li-logo">
                        <span className="li-logo-icon" />
                        <span>AutoApply</span>
                    </div>
                    <span className="li-badge li-badge-neutral">DESKTOP ONLY</span>
                </div>
                <div className="li-mobile-icon" />
                <h2>Connecting LinkedIn needs a desktop browser</h2>
                <p className="li-text">
                    The connection runs through the AutoApply desktop helper, currently packaged for Windows. Use a Windows computer for this step.
                </p>
                <p className="li-text">
                    Open AutoApply on your computer once to connect. After that you can manage everything from here.
                </p>
                <div className="li-divider" />
                <p className="li-label">STILL WORKS ON MOBILE</p>
                <p className="li-text">Settings, search terms, daily limit, and your application history.</p>
            </div>
        )
    }

    if (sessionLoading) {
        return <div className="li-card">Loading...</div>
    }

    const isWaiting = Boolean(activeToken) && statusQuery.data?.status === 'pending'
    const didTimeout = statusQuery.data?.status === 'failed' || statusQuery.data?.status === 'unknown'
    const isConnected = Boolean(session) && !isWaiting

    if (isWaiting) {
        return (
            <div className="li-card">
                <div className="li-card-header">
                    <div className="li-logo"><span className="li-logo-icon" /><span>AutoApply</span></div>
                    <span className="li-badge li-badge-waiting">WAITING</span>
                </div>
                <div className="li-waiting-dots"><span /><span /><span /></div>
                <h2>Waiting for the desktop app</h2>
                <p className="li-mono-hint">Waiting...</p>
                <div className="li-info-box">
                    <p>Finish logging in to LinkedIn in the AutoApply window. It may be behind this one.</p>
                    <p className="li-text-muted">This can take a few minutes if LinkedIn asks for a verification code. Leave this page open — it updates by itself.</p>
                </div>
                <div className="li-actions">
                    <button className="li-btn-secondary" onClick={handleReopenApp}>Open the app again</button>
                    <button className="li-btn-link" onClick={handleStopWaiting}>Stop waiting</button>
                </div>
            </div>
        )
    }

    if (didTimeout) {
        return (
            <div className="li-card">
                <div className="li-card-header">
                    <div className="li-logo"><span className="li-logo-icon" /><span>AutoApply</span></div>
                    <span className="li-badge li-badge-neutral">NOT CONNECTED</span>
                </div>
                <h2>The connection didn't finish</h2>
                <p className="li-text">
                    We stopped waiting after 5 minutes. This usually means the app window was closed, or the LinkedIn login was still open when we gave up. Nothing changed on your account.
                </p>
                <div className="li-checklist">
                    <p>Check the AutoApply app is installed and allowed to open.</p>
                    <p>Have your LinkedIn verification code ready before you start.</p>
                </div>
                <div className="li-actions">
                    <button className="li-btn-primary" onClick={handleConnectClick}>Try again</button>
                    <span className="li-text-muted">Everything else in AutoApply keeps working.</span>
                </div>
            </div>
        )
    }

    if (isConnected) {
        return (
            <div className="li-card">
                <div className="li-card-header">
                    <div className="li-logo"><span className="li-logo-icon" /><span>AutoApply</span></div>
                    <span className="li-badge li-badge-connected">CONNECTED</span>
                </div>
                <div className="li-check-circle">✓</div>
                <h2>LinkedIn connected</h2>
                <p className="li-text-muted">
                    {justConnected ? 'You can close the desktop app. Applications start on your next run.' : 'AutoApply is applying to jobs with your LinkedIn session.'}
                </p>
                <div className="li-details-box">
                    {currentUser?.email && (
                        <div className="li-detail-row"><span>Account</span><span>{currentUser.email}</span></div>
                    )}
                    {justConnected && (
                        <div className="li-detail-row"><span>Last connected</span><span>Just now</span></div>
                    )}
                    <div className="li-detail-row"><span>Session</span><span>Stored — reconnect if it expires</span></div>
                </div>
                <div className="li-actions">
                    <button className="li-btn-secondary" onClick={handleConnectClick}>Reconnect</button>
                    <span className="li-text-muted">Only needed if the session expires or you change your LinkedIn password.</span>
                </div>
            </div>
        )
    }

    return (
        <div className="li-card">
            <div className="li-card-header">
                <div className="li-logo"><span className="li-logo-icon" /><span>AutoApply</span></div>
                <span className="li-badge li-badge-neutral">NOT CONNECTED</span>
            </div>
            <h2>Connect LinkedIn</h2>
            <p className="li-text">
                AutoApply needs access to your LinkedIn session so it can open job posts and submit applications on your behalf. You stay logged in on LinkedIn as normal.
            </p>
            <div className="li-info-box">
                <p className="li-label">WHAT HAPPENS NEXT</p>
                <div className="li-step"><span className="li-step-num">1</span><span>The AutoApply desktop app opens in a separate window.</span></div>
                <div className="li-step"><span className="li-step-num">2</span><span>You log in to LinkedIn there, the same way you normally would.</span></div>
                <div className="li-step"><span className="li-step-num">3</span><span>This page updates on its own once the session is handed back.</span></div>
            </div>
            <button className="li-btn-primary li-btn-full" onClick={handleConnectClick} disabled={startMutation.isPending}>
                Connect LinkedIn ↗
            </button>
            <p className="li-text-muted li-center">Opens the desktop app. Your password is never entered here.</p>
        </div>
    )
}
