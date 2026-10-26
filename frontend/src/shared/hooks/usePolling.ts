import { useQuery } from '@tanstack/react-query'

interface UsePollingOptions<T> {
    queryKey: unknown[]
    queryFn: () => Promise<T>
    intervalMs: number
    isDone: (data: T) => boolean
    enabled: boolean
}

/**
 * Polls queryFn at intervalMs, automatically stopping once isDone(data)
 * returns true. Used for both LinkedIn connection status and (later)
 * Auto Apply run status - both share this exact pattern:
 * repeatedly check a status endpoint until it reaches a terminal state.
 */
export function usePolling<T>({ queryKey, queryFn, intervalMs, isDone, enabled }: UsePollingOptions<T>) {
    return useQuery({
        queryKey,
        queryFn,
        enabled,
        refetchInterval: (query) => {
            const data = query.state.data
            if (data && isDone(data)) {
                return false // stop polling
            }
            return intervalMs
        },
    })
}