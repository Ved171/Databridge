import { useState, useEffect, useRef } from 'react'
import { ChevronDown, Search, X } from 'lucide-react'

export interface MultiSelectProps {
  options: { id: string; label: string }[]
  value: string[]
  onChange: (ids: string[]) => void
  placeholder?: string
  className?: string
}

export function MultiSelect({
  options,
  value,
  onChange,
  placeholder = 'Select...',
  className = '',
}: MultiSelectProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [search, setSearch] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  useEffect(() => {
    if (!isOpen) setSearch('')
  }, [isOpen])

  const filtered = options.filter(o =>
    o.label.toLowerCase().includes(search.toLowerCase())
  )

  const selectedLabels = value
    .map(id => options.find(o => o.id === id)?.label)
    .filter(Boolean) as string[]

  const toggle = (id: string) => {
    if (value.includes(id)) {
      onChange(value.filter(v => v !== id))
    } else {
      onChange([...value, id])
    }
  }

  const selectAll = () => {
    const filteredIds = filtered.map(o => o.id)
    const merged = [...new Set([...value, ...filteredIds])]
    onChange(merged)
  }

  const clearAll = () => onChange([])

  const pillText = () => {
    if (selectedLabels.length === 0) return null
    if (selectedLabels.length === 1) return selectedLabels[0]
    return `${selectedLabels[0]} +${selectedLabels.length - 1}`
  }

  return (
    <div ref={containerRef} className={`relative ${className}`}>
      <button
        type="button"
        onClick={() => setIsOpen(prev => !prev)}
        className="w-full flex items-center justify-between gap-2 px-3 py-2 bg-bg-card border border-border-default rounded-lg text-sm text-left transition-colors focus:outline-none focus:ring-2 focus:ring-accent-500 focus:border-accent-500"
      >
        <span className="flex-1 min-w-0 truncate">
          {selectedLabels.length > 0 ? (
            <span className="inline-flex items-center gap-1.5">
              <span className="inline-flex items-center px-2 py-0.5 rounded-md bg-accent-50 text-accent-700 text-xs font-medium border border-accent-100 truncate max-w-[180px]">
                {pillText()}
              </span>
              {selectedLabels.length > 1 && (
                <span className="text-xs text-text-muted">{selectedLabels.length} selected</span>
              )}
            </span>
          ) : (
            <span className="text-text-muted">{placeholder}</span>
          )}
        </span>
        <ChevronDown className={`w-4 h-4 text-text-muted flex-shrink-0 transition-transform ${isOpen ? 'rotate-180' : ''}`} />
      </button>

      {isOpen && (
        <div className="absolute z-50 mt-1 w-full bg-bg-card border border-border-default rounded-lg shadow-lg overflow-hidden">
          <div className="p-2 border-b border-border-muted">
            <div className="relative">
              <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-text-muted" />
              <input
                type="text"
                value={search}
                onChange={e => setSearch(e.target.value)}
                placeholder="Search..."
                className="w-full pl-8 pr-3 py-1.5 text-sm bg-bg-card border border-border-default rounded-md focus:outline-none focus:ring-2 focus:ring-accent-500"
                autoFocus
              />
            </div>
            <div className="flex items-center gap-3 mt-2 px-1">
              <button
                type="button"
                onClick={selectAll}
                className="text-xs text-accent-600 hover:text-accent-700 font-medium"
              >
                Select all
              </button>
              <span className="text-border-strong">|</span>
              <button
                type="button"
                onClick={clearAll}
                className="text-xs text-text-secondary hover:text-text-primary font-medium"
              >
                Clear
              </button>
              <span className="text-border-strong">|</span>
              <button
                type="button"
                onClick={() => setIsOpen(false)}
                className="ml-auto text-xs text-accent-600 hover:text-accent-700 font-semibold"
              >
                Done
              </button>
            </div>
          </div>

          <ul className="max-h-48 overflow-y-auto py-1">
            {filtered.length === 0 ? (
              <li className="px-3 py-2 text-sm text-text-muted italic">No options found</li>
            ) : (
              filtered.map(opt => (
                <li key={opt.id}>
                  <label className="flex items-center gap-2.5 px-3 py-2 hover:bg-bg-surface cursor-pointer text-sm">
                    <input
                      type="checkbox"
                      checked={value.includes(opt.id)}
                      onChange={() => toggle(opt.id)}
                      className="rounded border-border-strong text-accent-600 focus:ring-accent-500"
                    />
                    <span className="text-text-primary truncate">{opt.label}</span>
                  </label>
                </li>
              ))
            )}
          </ul>
        </div>
      )}

      {value.length > 0 && !isOpen && (
        <button
          type="button"
          onClick={clearAll}
          className="absolute right-8 top-1/2 -translate-y-1/2 p-0.5 text-text-muted hover:text-text-secondary"
          aria-label="Clear selection"
        >
          <X className="w-3.5 h-3.5" />
        </button>
      )}
    </div>
  )
}
