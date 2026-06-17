import clsx from 'clsx'

export interface Tab {
  id: string
  label: string
}

interface PageTabsProps {
  tabs: Tab[]
  active: string
  onChange: (id: string) => void
}

export function PageTabs({ tabs, active, onChange }: PageTabsProps) {
  return (
    <div className="flex border-b border-border-default bg-white flex-shrink-0">
      {tabs.map(tab => (
        <button
          key={tab.id}
          type="button"
          onClick={() => onChange(tab.id)}
          className={clsx(
            'px-4 py-3 text-sm font-medium transition-colors relative',
            active === tab.id
              ? 'text-accent-500 after:absolute after:bottom-0 after:left-0 after:right-0 after:h-0.5 after:bg-accent-500'
              : 'text-text-muted hover:text-on-surface'
          )}
        >
          {tab.label}
        </button>
      ))}
    </div>
  )
}
