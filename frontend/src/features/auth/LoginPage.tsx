import { useState } from 'react'
import { useMutation } from '@tanstack/react-query'
import { login, register } from './api'
import './auth.css'

type Mode = 'login' | 'register'

export function LoginPage() {
    const [mode, setMode] = useState<Mode>('login')
    const [email, setEmail] = useState('')
    const [password, setPassword] = useState('')

    const loginMutation = useMutation({
        mutationFn: login,
        onSuccess: (data) => {
            localStorage.setItem('access_token', data.access_token)
            window.location.href = '/settings'
        },
    })

    const registerMutation = useMutation({
        mutationFn: register,
        onSuccess: () => {
            // After successful registration, log them in immediately
            loginMutation.mutate({ email, password })
        },
    })

    const activeMutation = mode === 'login' ? loginMutation : registerMutation
    const isLoading = activeMutation.isPending || (mode === 'register' && loginMutation.isPending)

    function handleSubmit(e: React.FormEvent) {
        e.preventDefault()
        if (mode === 'login') {
            loginMutation.mutate({ email, password })
        } else {
            registerMutation.mutate({ email, password })
        }
    }

    function switchMode(newMode: Mode) {
        setMode(newMode)
        loginMutation.reset()
        registerMutation.reset()
    }

    // Error classification — matches the three distinct error states
    // we verified against the backend: invalid credentials (400),
    // disabled account (403), and duplicate email (400, email-specific)
    const loginError = loginMutation.error as { response?: { status: number } } | undefined
    const isDisabledAccount = loginError?.response?.status === 403
    const isInvalidCredentials = mode === 'login' && loginMutation.isError && !isDisabledAccount

    const registerError = registerMutation.error as { response?: { status: number } } | undefined
    const isDuplicateEmail = mode === 'register' && registerError?.response?.status === 400

    const showSigningIn = mode === 'register' && registerMutation.isSuccess && loginMutation.isPending

    if (showSigningIn) {
        return (
            <div className="auth-card">
                <div className="auth-logo">
                    <span className="auth-logo-icon" />
                    <span className="auth-logo-text">AutoApply</span>
                </div>
                <div className="auth-signing-in">
                    <div className="auth-check-circle">✓</div>
                    <h2>Signing you in</h2>
                    <p className="auth-muted">Taking you to your dashboard</p>
                </div>
            </div>
        )
    }

    return (
        <div className="auth-card">
            <div className="auth-logo">
                <span className="auth-logo-icon" />
                <span className="auth-logo-text">AutoApply</span>
            </div>

            <div className="auth-tabs">
                <button
                    className={mode === 'login' ? 'auth-tab active' : 'auth-tab'}
                    onClick={() => switchMode('login')}
                    type="button"
                >
                    Log in
                </button>
                <button
                    className={mode === 'register' ? 'auth-tab active' : 'auth-tab'}
                    onClick={() => switchMode('register')}
                    type="button"
                >
                    Create account
                </button>
            </div>

            {mode === 'login' ? (
                <>
                    <h1>Welcome back</h1>
                    <p className="auth-subtitle">Sign in to run and monitor your applications.</p>
                </>
            ) : (
                <>
                    <h1>Create your account</h1>
                    <p className="auth-subtitle">Start applying automatically in a few minutes.</p>
                </>
            )}

            {isDisabledAccount && (
                <div className="auth-banner auth-banner-disabled">
                    <strong>This account has been disabled</strong>
                    <span>Contact the person who manages your account.</span>
                </div>
            )}

            <form onSubmit={handleSubmit}>
                <label className="auth-label">Email</label>
                <input
                    type="email"
                    className={isInvalidCredentials || isDuplicateEmail ? 'auth-input error' : 'auth-input'}
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder={mode === 'login' ? 'maya@company.com' : 'you@company.com'}
                    disabled={isLoading}
                    required
                />
                {isDuplicateEmail && (
                    <p className="auth-field-error">
                        Email already registered. <a href="#" onClick={(e) => { e.preventDefault(); switchMode('login') }}>Log in instead</a>
                    </p>
                )}

                <label className="auth-label">Password</label>
                <input
                    type="password"
                    className={isInvalidCredentials ? 'auth-input error' : 'auth-input'}
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    placeholder={mode === 'register' ? 'Choose a password' : undefined}
                    disabled={isLoading}
                    required
                />

                {isInvalidCredentials && (
                    <p className="auth-banner-inline">Invalid email or password</p>
                )}

                <button type="submit" className="auth-submit" disabled={isLoading}>
                    {isLoading
                        ? (mode === 'login' ? 'Logging in' : 'Creating account')
                        : (mode === 'login' ? 'Log in' : 'Create account')}
                </button>
            </form>

            <p className="auth-footer">Your LinkedIn session is encrypted before it's stored.</p>
        </div>
    )
}