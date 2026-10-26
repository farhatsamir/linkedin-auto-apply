import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { LoginPage } from './features/auth/LoginPage'
import { SettingsPage } from './features/settings/SettingsPage'
import { LinkedInConnectionPage } from './features/linkedin-connection/LinkedInConnectionPage'
import { AutoApplyPage } from './features/auto-apply/AutoApplyPage'
import { ApplicationsPage } from './features/applications/ApplicationsPage'
import { AdminPage } from './features/admin/AdminPage'
import { AdminRoute } from './shared/components/AdminRoute'
import { ProtectedRoute } from './shared/components/ProtectedRoute'
import { AppShell } from './shared/components/AppShell'

const queryClient = new QueryClient()

function App() {
    return (
        <QueryClientProvider client={queryClient}>
            <BrowserRouter>
                <Routes>
                    <Route path="/login" element={<LoginPage />} />

                    <Route
                        element={
                            <ProtectedRoute>
                                <AppShell />
                            </ProtectedRoute>
                        }
                    >
                        <Route path="/settings" element={<SettingsPage />} />
                        <Route path="/connect-linkedin" element={<LinkedInConnectionPage />} />
                        <Route path="/auto-apply" element={<AutoApplyPage />} />
                        <Route path="/applications" element={<ApplicationsPage />} />
                        <Route
                            path="/admin"
                            element={
                                <AdminRoute>
                                    <AdminPage />
                                </AdminRoute>
                            }
                        />
                    </Route>

                    <Route path="/" element={<Navigate to="/auto-apply" replace />} />
                </Routes>
            </BrowserRouter>
        </QueryClientProvider>
    )
}

export default App