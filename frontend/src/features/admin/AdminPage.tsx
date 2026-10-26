import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { getAllRuns, getActiveRuns, cancelRun } from './api'
import './admin.css'

const PAGE_SIZE = 8
const STATUS_OPTIONS = ['', 'queued', 'running', 'completed', 'completed_with_errors', 'failed']
const STATUS_LABELS: Record<string, string> = {
  '': 'All',
  queued: 'Queued',
  running: 'Running',
  completed: 'Completed',
  completed_with_errors: 'Completed with errors',
  failed: 'Failed',
}

export function AdminPage() {
  const queryClient = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [skip, setSkip] = useState(0)

  const { data, isLoading } = useQuery({
    queryKey: ['admin-runs', statusFilter, skip],
    queryFn: () => getAllRuns(statusFilter || null, skip, PAGE_SIZE),
  })

  const { data: activeRuns } = useQuery({
    queryKey: ['admin-active-runs'],
    queryFn: getActiveRuns,
    refetchInterval: 5000,
  })

  const cancelMutation = useMutation({
    mutationFn: cancelRun,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['admin-runs'] })
      queryClient.invalidateQueries({ queryKey: ['admin-active-runs'] })
    },
  })

  function handleStatusChange(newStatus: string) {
    setStatusFilter(newStatus)
    setSkip(0)
  }

    function handleCancel(runId: number) {
        const confirmed = window.confirm(
            `Cancel run #${runId}? This will force-fail it and cannot be undone.`
        )
        if (confirmed) {
            cancelMutation.mutate(runId)
        }
    }

  function formatDate(dateStr: string): string {
    const date = new Date(dateStr)
    const now = new Date()
    const isToday = date.toDateString() === now.toDateString()
    if (isToday) return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    return date.toLocaleDateString([], { day: 'numeric', month: 'short' }) + ', ' + date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  }

  const items = data?.items || []
  const total = data?.total || 0
  const isCancellable = (status: string) => status === 'queued' || status === 'running'

  return (
    <div className="admin-layout">
      <div className="admin-main">
        <h1>Runs</h1>
        <p className="admin-subtitle">Every run across all users. Identified by numeric user ID only.</p>

        <div className="admin-table-card">
          <div className="admin-filter-row">
            <div>
              <label className="admin-filter-label">STATUS</label>
              <select
                className="admin-select"
                value={statusFilter}
                onChange={(e) => handleStatusChange(e.target.value)}
              >
                {STATUS_OPTIONS.map((opt) => (
                  <option key={opt} value={opt}>{STATUS_LABELS[opt]}</option>
                ))}
              </select>
            </div>
            <span className="admin-total">{isLoading ? '...' : `${total} run${total !== 1 ? 's' : ''}`}</span>
          </div>

          <div className="admin-table-scroll">
            <table className="admin-table">
              <thead>
                <tr>
                  <th>ID</th>
                  <th>USER</th>
                  <th>STATUS</th>
                  <th className="admin-th-num">FOUND</th>
                  <th className="admin-th-num">APPLIED</th>
                  <th className="admin-th-num">FAILED</th>
                  <th>STARTED</th>
                  <th></th>
                </tr>
              </thead>
              <tbody>
                {!isLoading && items.length === 0 && (
                  <tr>
                    <td colSpan={8} className="admin-empty-cell">No runs with this status.</td>
                  </tr>
                )}
                {items.map((run) => (
                  <tr key={run.id}>
                    <td>{run.id}</td>
                    <td>{run.user_id}</td>
                    <td>
                      <span className={`admin-badge admin-badge-${run.status}`}>
                        {run.status.replace(/_/g, ' ').toUpperCase()}
                      </span>
                    </td>
                    <td className="admin-num">{run.total_found}</td>
                    <td className="admin-num">{run.applied_count}</td>
                    <td className="admin-num">
                      <span className={run.failed_count > 0 ? 'admin-num-red' : ''}>{run.failed_count}</span>
                    </td>
                    <td>{formatDate(run.started_at)}</td>
                    <td>
                      {isCancellable(run.status) && (
                        <button
                          className="admin-cancel-btn"
                          onClick={() => handleCancel(run.id)}
                          disabled={cancelMutation.isPending}
                        >
                          Cancel
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="admin-footer">
            <span className="admin-text-muted">
             Showing {total === 0 ? 0 : skip + 1} to {Math.min(skip + PAGE_SIZE, total)} of {total}
            </span>
            <div className="admin-pagination">
              <button className="admin-page-btn" onClick={() => setSkip(Math.max(0, skip - PAGE_SIZE))} disabled={skip === 0}>
                Previous
              </button>
              <button className="admin-page-btn" onClick={() => setSkip(skip + PAGE_SIZE)} disabled={skip + PAGE_SIZE >= total}>
                Next
              </button>
            </div>
          </div>
        </div>

        <p className="admin-note">
          Cancelling force-fails the run and cannot be undone. The user sees the run as failed with the reason "Cancelled by admin."
        </p>
      </div>

      <div className="admin-sidebar">
        <div className="admin-active-card">
          <div className="admin-active-header">
            <span className="admin-active-dot" />
            <span>ACTIVE NOW</span>
            <span className="admin-active-count">{activeRuns?.length ?? 0}</span>
          </div>
          {(activeRuns || []).map((run) => (
            <div key={run.id} className="admin-active-row">
              <div>
                <strong>#{run.id} · user {run.user_id}</strong>
                <p className="admin-text-muted">{formatDate(run.started_at)}</p>
              </div>
              <span className={`admin-badge admin-badge-${run.status}`}>{run.status.toUpperCase()}</span>
            </div>
          ))}
          <p className="admin-active-footnote">Separate endpoint. Not filtered or paginated.</p>
        </div>
      </div>
    </div>
  )
}