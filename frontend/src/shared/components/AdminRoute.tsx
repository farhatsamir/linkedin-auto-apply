import type { ReactNode } from 'react'
import { useQuery } from '@tanstack/react-query'
import { Navigate } from 'react-router-dom'
import { apiClient } from '../api/client'

interface AdminRouteProps {
    children: ReactNode
}

export function AdminRoute({ children }: AdminRouteProps) {
    const { data: currentUser, isLoading } = useQuery({
        queryKey: ['current-user'],
        queryFn: async () => {
            const res = await apiClient.get('/users/me')
            return res.data as { email: string; role: string }
        },
    })

    if (isLoading) {
        return null
    }

    if (currentUser?.role !== 'admin') {
        return <Navigate to="/auto-apply" replace />
    }

    return <>{children}</>
}