import { useState, useEffect, useRef } from 'react'
import { Search, Check, X, ChevronDown, ChevronUp, Database, ListFilter, Loader2 } from 'lucide-react'

interface SearchableTableSelectorProps {
  allTables: string[]
  selectedTables: string[]
  onChange: (selected: string[]) => void
  singleSelect?: boolean
  placeholder?: string
  isLoading?: boolean
  inlineDropdown?: boolean
}

export function SearchableTableSelector({
  allTables = [],
  selectedTables = [],
  onChange,
  singleSelect = false,
  placeholder = 'Select tables...',
  isLoading = false,
  inlineDropdown = false,
}: SearchableTableSelectorProps) {
  const [isOpen, setIsOpen] = useState(false)
  const [searchTerm, setSearchTerm] = useState('')
  const containerRef = useRef<HTMLDivElement>(null)

  // Click outside to close dropdown
  useEffect(() => {
    function handleClickOutside(event: MouseEvent) {
      if (containerRef.current && !containerRef.current.contains(event.target as Node)) {
        setIsOpen(false)
      }
    }
    document.addEventListener('mousedown', handleClickOutside)
    return () => document.removeEventListener('mousedown', handleClickOutside)
  }, [])

  // Reset search when opening/closing
  useEffect(() => {
    if (!isOpen) {
      setSearchTerm('')
    }
  }, [isOpen])

  // Filter tables based on search
  const filteredTables = allTables.filter(table =>
    table.toLowerCase().includes(searchTerm.toLowerCase())
  )

  const toggleTable = (tableName: string) => {
    if (singleSelect) {
      onChange([tableName])
      setIsOpen(false)
    } else {
      if (selectedTables.includes(tableName)) {
        onChange(selectedTables.filter(t => t !== tableName))
      } else {
        onChange([...selectedTables, tableName])
      }
    }
  }

  const selectFiltered = () => {
    const toAdd = filteredTables.filter(t => !selectedTables.includes(t))
    onChange([...selectedTables, ...toAdd])
  }

  const clearFiltered = () => {
    onChange(selectedTables.filter(t => !filteredTables.includes(t)))
  }

  const removeChip = (tableName: string) => {
    onChange(selectedTables.filter(t => t !== tableName))
  }

  // Format table name to highlight schema vs table
  const renderTableName = (name: string) => {
    const parts = name.split('.')
    if (parts.length > 1) {
      const tableName = parts.pop()
      const schemaName = parts.join('.')
      return (
        <span className="truncate">
          <span className="text-gray-400 font-normal text-xs">{schemaName}.</span>
          <span className="text-gray-900 font-medium text-sm">{tableName}</span>
        </span>
      )
    }
    return <span className="text-gray-900 font-medium text-sm truncate">{name}</span>
  }

  return (
    <div className="relative w-full" ref={containerRef}>
      {/* Trigger Button */}
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="w-full flex items-center justify-between px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm text-left shadow-sm hover:border-brand-500 hover:ring-1 hover:ring-brand-500 transition-all duration-200"
      >
        <div className="flex items-center gap-2 min-w-0 flex-1">
          <Database className="w-4 h-4 text-brand-500 flex-shrink-0" />
          {singleSelect ? (
            selectedTables.length > 0 ? (
              <span className="font-mono text-gray-900 truncate block">{selectedTables[0]}</span>
            ) : (
              <span className="text-gray-400">{placeholder}</span>
            )
          ) : (
            selectedTables.length > 0 ? (
              <span className="font-medium text-brand-700 bg-brand-50 px-2 py-0.5 rounded-full text-xs inline-flex items-center gap-1">
                {selectedTables.length} table{selectedTables.length > 1 ? 's' : ''} selected
              </span>
            ) : (
              <span className="text-gray-400">{placeholder}</span>
            )
          )}
        </div>
        {isLoading ? (
          <Loader2 className="w-4 h-4 text-brand-500 flex-shrink-0 animate-spin" />
        ) : isOpen ? (
          <ChevronUp className="w-4 h-4 text-gray-400 flex-shrink-0" />
        ) : (
          <ChevronDown className="w-4 h-4 text-gray-400 flex-shrink-0" />
        )}
      </button>

      {/* Dropdown Panel */}
      {isOpen && (
        <div className={`${inlineDropdown ? 'relative' : 'absolute'} z-50 mt-1.5 w-full bg-white border border-gray-200 rounded-xl shadow-xl overflow-hidden flex flex-col max-h-[min(24rem,45vh)] min-w-[280px]`}>
          {/* Search Box */}
          <div className="p-2 border-b border-gray-100 bg-gray-50 flex items-center gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-2.5 top-2.5 w-4 h-4 text-gray-400" />
              <input
                type="text"
                className="w-full pl-9 pr-8 py-2 bg-white border border-gray-300 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all duration-150"
                placeholder="Search tables..."
                value={searchTerm}
                onChange={e => setSearchTerm(e.target.value)}
                autoFocus
              />
              {searchTerm && (
                <button
                  type="button"
                  onClick={() => setSearchTerm('')}
                  className="absolute right-2.5 top-2.5 text-gray-400 hover:text-gray-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
          </div>

          {/* Quick Actions (only for multi-select) */}
          {!singleSelect && allTables.length > 0 && !isLoading && (
            <div className="px-3 py-1.5 bg-gray-50 border-b border-gray-100 flex justify-between items-center gap-2 text-xs">
              <div className="text-gray-500 font-medium">
                Matches: <span className="text-gray-900">{filteredTables.length}</span>
              </div>
              <div className="flex gap-2 items-center">
                <button
                  type="button"
                  onClick={selectFiltered}
                  className="text-brand-600 hover:text-brand-700 font-semibold transition-colors"
                  disabled={filteredTables.length === 0}
                >
                  Select Filtered
                </button>
                <span className="text-gray-300">|</span>
                <button
                  type="button"
                  onClick={clearFiltered}
                  className="text-gray-500 hover:text-red-500 font-semibold transition-colors"
                  disabled={filteredTables.length === 0}
                >
                  Clear Filtered
                </button>
                <span className="text-gray-300">|</span>
                <button
                  type="button"
                  onClick={() => setIsOpen(false)}
                  className="text-brand-600 hover:text-brand-700 font-semibold transition-colors"
                >
                  Done
                </button>
              </div>
            </div>
          )}

          {/* Scrollable List */}
          <div className="overflow-y-auto flex-1 divide-y divide-gray-50 max-h-64">
            {isLoading ? (
              <div className="p-8 text-center text-gray-500 text-sm flex flex-col items-center justify-center gap-2">
                <Loader2 className="w-6 h-6 text-brand-500 animate-spin" />
                <span>Loading tables...</span>
              </div>
            ) : allTables.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm">
                No tables available for this connector.
              </div>
            ) : filteredTables.length === 0 ? (
              <div className="p-8 text-center text-gray-400 text-sm flex flex-col items-center justify-center gap-2">
                <ListFilter className="w-8 h-8 text-gray-300" />
                <span>No matching tables found</span>
              </div>
            ) : (
              filteredTables.map(table => {
                const isSelected = selectedTables.includes(table)
                return (
                  <button
                    key={table}
                    type="button"
                    onClick={() => toggleTable(table)}
                    className={`w-full flex items-center justify-between px-3.5 py-2.5 text-left transition-all duration-150 ${
                      isSelected
                        ? 'bg-brand-50/50 hover:bg-brand-50'
                        : 'hover:bg-gray-50'
                    }`}
                  >
                    <div className="flex items-center gap-2.5 min-w-0 pr-2">
                      {!singleSelect && (
                        <div
                          className={`w-4 h-4 rounded flex items-center justify-center flex-shrink-0 transition-all duration-150 ${
                            isSelected
                              ? 'bg-brand-600 border-brand-600 text-white'
                              : 'border border-gray-300 bg-white'
                          }`}
                        >
                          {isSelected && <Check className="w-3 h-3 stroke-[3]" />}
                        </div>
                      )}
                      <span className="font-mono text-xs text-gray-700 flex-1 truncate">
                        {renderTableName(table)}
                      </span>
                    </div>
                    {singleSelect && isSelected && (
                      <Check className="w-4 h-4 text-brand-600 stroke-[2.5] flex-shrink-0" />
                    )}
                  </button>
                )
              })
            )}
          </div>

        </div>
      )}

      {/* Selected Items Chips (Multi-select only) */}
      {!singleSelect && selectedTables.length > 0 && (
        <div className="mt-2">
          <div className="flex justify-between items-center mb-1.5">
            <span className="text-xs font-semibold text-gray-500">Selected Tables ({selectedTables.length}):</span>
            <button
              type="button"
              onClick={() => onChange([])}
              className="text-xs text-red-500 hover:text-red-700 font-semibold"
            >
              Clear All
            </button>
          </div>
          <div className="flex flex-wrap gap-1.5 max-h-36 overflow-y-auto p-1.5 border border-gray-200 bg-gray-50/30 rounded-lg">
            {selectedTables.map(table => (
              <div
                key={table}
                className="inline-flex items-center gap-1 bg-white hover:bg-gray-50 text-xs font-mono text-gray-700 px-2 py-0.5 rounded-md border border-gray-200 shadow-sm transition-all duration-150"
              >
                <span className="truncate max-w-[200px]" title={table}>
                  {table}
                </span>
                <button
                  type="button"
                  onClick={() => removeChip(table)}
                  className="text-gray-400 hover:text-red-500 transition-colors p-0.5 rounded-full"
                >
                  <X className="w-3 h-3" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
