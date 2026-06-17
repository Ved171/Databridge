import { Database } from 'lucide-react'
import clsx from 'clsx'

interface Connector {
  id: string
  name: string
  type: string
  is_active?: boolean
  schema_cached_at?: string | null
}

interface ConnectorListPanelProps {
  connectors: Connector[]
  selectedId: string
  onSelect: (id: string) => void
}

export function ConnectorListPanel({ connectors, selectedId, onSelect }: ConnectorListPanelProps) {
  return (
    <aside className="w-60 flex-shrink-0 border-r border-border-default bg-surface-container-lowest flex flex-col">
      <div className="px-4 py-3 border-b border-border-default">
        <p className="label-sm text-text-muted">Connectors</p>
      </div>
      <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
        {connectors.length === 0 ? (
          <p className="text-xs text-text-muted px-2 py-4 text-center">No connectors</p>
        ) : (
          connectors.map(c => (
            <button
              key={c.id}
              type="button"
              onClick={() => onSelect(c.id)}
              className={clsx(
                'w-full flex items-center gap-2.5 px-3 py-2.5 rounded text-left text-sm transition-colors',
                selectedId === c.id
                  ? 'bg-sidebar-active text-on-surface font-medium'
                  : 'text-text-secondary hover:bg-surface-container-low hover:text-on-surface'
              )}
            >
              <Database className="w-4 h-4 flex-shrink-0 text-accent-500" />
              <div className="min-w-0 flex-1">
                <p className="truncate">{c.name}</p>
                <p className="text-[10px] text-text-muted capitalize truncate">{c.type}</p>
              </div>
              <span className={clsx(
                'w-1.5 h-1.5 rounded-full flex-shrink-0',
                c.is_active ? 'bg-success' : 'bg-text-muted'
              )} />
            </button>
          ))
        )}
      </div>
    </aside>
  )
}
