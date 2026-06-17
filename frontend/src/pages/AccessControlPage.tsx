import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import { Bug, X } from 'lucide-react'
import { useAuthStore } from '../store/auth'
import { PageTabs } from '../components/PageTabs'
import { ConnectorListPanel } from '../components/ConnectorListPanel'
import { PermissionsPage } from './PermissionsPage'
import { RLSPage } from './RLSPage'
import { PackagesPage } from './PackagesPage'
import api from '../lib/api'

export function AccessControlPage() {
  const { user } = useAuthStore()
  const [searchParams, setSearchParams] = useSearchParams()
  const [showDebug, setShowDebug] = useState(false)

  const isSuperAdminOrAdmin = user?.is_superadmin || user?.role === 'admin' || user?.role === 'super_admin' || user?.role === 'superadmin'

  const tabs = useMemo(() => {
    const items = [
      { id: 'connector', label: 'Connector Access' },
      { id: 'table', label: 'Table Access' },
    ]
    if (isSuperAdminOrAdmin) {
      items.push({ id: 'rls', label: 'Row Level Security' })
    }
    if (user?.is_superadmin) {
      items.push({ id: 'packages', label: 'Access Packages' })
    }
    return items
  }, [isSuperAdminOrAdmin, user?.is_superadmin])

  const activeTab = tabs.some(t => t.id === searchParams.get('tab'))
    ? searchParams.get('tab')!
    : 'connector'

  const setTab = (id: string) => {
    const next = new URLSearchParams(searchParams)
    next.set('tab', id)
    setSearchParams(next)
  }

  const { data: connectors = [] } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => api.get('/api/connectors/').then(r => r.data),
  })

  const connectorFromUrl = searchParams.get('connector') ?? ''
  const [selectedConnector, setSelectedConnector] = useState(connectorFromUrl)

  useEffect(() => {
    if (connectorFromUrl && connectors.some((c: any) => c.id === connectorFromUrl)) {
      setSelectedConnector(connectorFromUrl)
    } else if (connectors.length > 0) {
      setSelectedConnector(prev => prev || connectors[0].id)
    }
  }, [connectors, connectorFromUrl])

  const handleSelectConnector = (id: string) => {
    setSelectedConnector(id)
    const next = new URLSearchParams(searchParams)
    next.set('connector', id)
    setSearchParams(next)
  }

  const needsConnector = activeTab !== 'packages'

  return (
    <div className="h-full flex flex-col">
      <div className="px-6 pt-6 pb-4 flex-shrink-0 border-b border-border-default bg-surface">
        <div className="flex items-start justify-between gap-4">
          <div>
            <h1 className="headline-lg mb-1">Access Control</h1>
            <p className="text-sm text-text-muted">
              Manage connector, table, and row-level permissions
            </p>
          </div>
          {user?.is_superadmin && (
            <button
              type="button"
              onClick={() => setShowDebug(v => !v)}
              className="flex items-center gap-2 px-3 py-2 text-sm border border-border-default rounded hover:border-accent-500/30 transition-colors"
              title="Debug access"
            >
              <Bug className="w-4 h-4 text-accent-500" />
              Check Permissions
            </button>
          )}
        </div>
      </div>

      <div className="flex flex-1 min-h-0">
        {needsConnector && (
          <ConnectorListPanel
            connectors={connectors}
            selectedId={selectedConnector}
            onSelect={handleSelectConnector}
          />
        )}

        <div className="flex-1 flex flex-col min-w-0">
          <PageTabs tabs={tabs} active={activeTab} onChange={setTab} />
          <div className="flex-1 overflow-y-auto min-h-0 bg-surface">
            {needsConnector && !selectedConnector && (
              <div className="flex items-center justify-center h-48 text-sm text-text-muted">
                Select a connector to manage access
              </div>
            )}
            {activeTab === 'connector' && selectedConnector && (
              <PermissionsPage
                embedded
                section="connector"
                selectedConnectorId={selectedConnector}
                hideDebug
              />
            )}
            {activeTab === 'table' && selectedConnector && (
              <PermissionsPage
                embedded
                section="table"
                selectedConnectorId={selectedConnector}
                hideDebug
              />
            )}
            {activeTab === 'rls' && selectedConnector && (
              <RLSPage embedded connectorId={selectedConnector} />
            )}
            {activeTab === 'packages' && (
              <PackagesPage embedded />
            )}
          </div>
        </div>
      </div>

      {showDebug && user?.is_superadmin && (
        <div className="fixed inset-0 z-50 flex justify-end">
          <div className="absolute inset-0 bg-black/30" onClick={() => setShowDebug(false)} />
          <div className="relative w-full max-w-4xl h-full bg-white shadow-xl flex flex-col">
            <div className="flex items-center justify-between px-5 py-4 border-b border-border-default">
              <h2 className="text-sm font-semibold text-on-surface">Check Permissions</h2>
              <button onClick={() => setShowDebug(false)} className="p-1.5 rounded hover:bg-surface-container-low">
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="flex-1 overflow-y-auto">
              <PermissionsPage debugOnly />
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
