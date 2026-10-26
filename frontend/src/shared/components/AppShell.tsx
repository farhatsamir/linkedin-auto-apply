import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { apiClient } from '../api/client'
import './appshell.css'

export function AppShell() {
    const navigate = useNavigate()

    const { data: currentUser } = useQuery({
        queryKey: ['current-user'],
        queryFn: async () => {
            const res = await apiClient.get('/users/me')
            return res.data as { email: string; role: string }
        },
    })

    const isAdmin = currentUser?.role === 'admin'

    async function handleLogout() {
        try {
            await apiClient.post('/auth/logout')
        } catch {
            // Even if the server call fails, still clear local state and leave —
            // matches the backend's own logout endpoint, which always succeeds
            // locally regardless of token validity (verified earlier).
        }
        localStorage.removeItem('access_token')
        navigate('/login')
    }

    return (
        <div className="app-shell">
            <nav className="app-nav">
                <div className="app-nav-logo">
                    <span className="app-nav-logo-icon" />
                    <span className="app-nav-logo-text">AutoApply</span>
                </div>
                <div className="app-nav-links">
                    <NavLink to="/auto-apply" className={({ isActive }) => isActive ? 'app-nav-link active' : 'app-nav-link'}>
                        Auto Apply
                    </NavLink>
                    <NavLink to="/applications" className={({ isActive }) => isActive ? 'app-nav-link active' : 'app-nav-link'}>
                        Applications
                    </NavLink>
                    <NavLink to="/settings" className={({ isActive }) => isActive ? 'app-nav-link active' : 'app-nav-link'}>
                        Settings
                    </NavLink>
                    <NavLink to="/connect-linkedin" className={({ isActive }) => isActive ? 'app-nav-link active' : 'app-nav-link'}>
                        Connect LinkedIn
                    </NavLink>
                    {isAdmin && (
                        <NavLink to="/admin" className={({ isActive }) => isActive ? 'app-nav-link active' : 'app-nav-link'}>
                            Admin
                        </NavLink>
                    )}
                </div>
                <button className="app-nav-logout" onClick={handleLogout}>Log out</button>
            </nav>
            <main className="app-main">
                <Outlet />
            </main>
        </div>
    )
}