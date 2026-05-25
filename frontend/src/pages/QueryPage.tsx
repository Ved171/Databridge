import { useState, useRef, useEffect } from 'react'
import {
  Send, Loader2, Bot, User, ChevronDown, ChevronRight,
  Wrench, Eye, Brain, Sparkles
} from 'lucide-react'
import api from '../lib/api'
import { useAuthStore } from '../store/auth'
import clsx from 'clsx'

interface AgentStep {
  type: 'action' | 'observation' | 'thought'
  tool?: string
  args?: any
  content?: string
}

interface ChatMessage {
  id: string
  role: 'user' | 'assistant' | 'error'
  content: string
  history?: AgentStep[]
  duration_ms?: number
  timestamp: Date
  isThinking?: boolean
}

function AgentTrace({ history, isThinking }: { history: AgentStep[], isThinking?: boolean }) {
  const [open, setOpen] = useState(false)
  
  useEffect(() => {
    if (isThinking && history.length > 0) {
      setOpen(true)
    }
  }, [isThinking, history.length])

  if (!history?.length) return null

  return (
    <div className="mt-3 rounded-lg overflow-hidden border border-white/10">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 bg-white/5 text-xs font-medium text-slate-400 hover:bg-white/10 transition-colors"
      >
        <Wrench className={clsx("w-3 h-3", isThinking && "animate-spin text-indigo-400")} />
        {isThinking ? 'Agent is thinking...' : 'Agent Trace'} - {history.length} steps
        {open ? <ChevronDown className="w-3 h-3 ml-auto" /> : <ChevronRight className="w-3 h-3 ml-auto" />}
      </button>
      {open && (
        <div className="p-3 space-y-2 max-h-72 overflow-y-auto bg-black/20">
          {history.map((step, i) => (
            <div key={i} className={clsx(
              'text-xs rounded-md px-3 py-2 font-mono',
              step.type === 'action'      && 'bg-blue-500/10 border border-blue-500/20 text-blue-300',
              step.type === 'observation'  && 'bg-emerald-500/10 border border-emerald-500/20 text-emerald-300',
              step.type === 'thought'      && 'bg-violet-500/10 border border-violet-500/20 text-violet-300',
            )}>
              <span className="font-semibold mr-2">
                {step.type === 'action'
                  ? `[Tool] ${step.tool}`
                  : step.type === 'observation'
                  ? '[Result]'
                  : '[Thought]'}
              </span>
              {step.type === 'action' && step.args && (
                <span className="opacity-70">
                  {JSON.stringify(step.args).slice(0, 150)}
                  {JSON.stringify(step.args).length > 150 ? '...' : ''}
                </span>
              )}
              {step.type !== 'action' && (
                <span className="opacity-80">
                  {String(step.content || '').slice(0, 300)}
                  {String(step.content || '').length > 300 ? '...' : ''}
                </span>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function MarkdownishText({ text }: { text: string }) {
  // Very lightweight: handle code blocks, bold, and newlines
  const parts = text.split(/(```[\s\S]*?```)/g)
  return (
    <div className="space-y-2">
      {parts.map((part, i) => {
        if (part.startsWith('```')) {
          const code = part.replace(/```\w*\n?/g, '').replace(/```$/g, '')
          return (
            <pre key={i} className="bg-black/30 rounded-lg p-3 text-xs font-mono text-emerald-300 overflow-x-auto border border-white/5">
              {code}
            </pre>
          )
        }
        return (
          <div key={i} className="whitespace-pre-wrap leading-relaxed">
            {part.split('\n').map((line, li) => (
              <span key={li}>
                {line.split(/(\*\*.*?\*\*)/g).map((seg, si) =>
                  seg.startsWith('**') && seg.endsWith('**')
                    ? <strong key={si} className="font-semibold text-white">{seg.slice(2, -2)}</strong>
                    : <span key={si}>{seg}</span>
                )}
                {li < part.split('\n').length - 1 && <br />}
              </span>
            ))}
          </div>
        )
      })}
    </div>
  )
}


export function QueryPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const bottomRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages, loading])

  useEffect(() => {
    inputRef.current?.focus()
  }, [])

  const token = useAuthStore(s => s.token)

  const sendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    const msg = input.trim()
    if (!msg || loading) return

    const userMsg: ChatMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content: msg,
      timestamp: new Date(),
    }

    const assistantId = crypto.randomUUID()
    const assistantMsg: ChatMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      history: [],
      timestamp: new Date(),
      isThinking: true,
    }

    setMessages(prev => [...prev, userMsg, assistantMsg])
    setInput('')
    setLoading(true)

    const startTime = Date.now()

    try {
      const url = `${api.defaults.baseURL}/api/query/chat/stream?message=${encodeURIComponent(msg)}`
      const response = await fetch(url, {
        headers: {
          'Authorization': `Bearer ${token}`
        }
      })

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}))
        throw new Error(errorData.detail || 'Failed to connect to agent')
      }

      const reader = response.body?.getReader()
      if (!reader) throw new Error('ReadableStream not supported')

      const decoder = new TextDecoder()
      let buffer = ''

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        buffer += decoder.decode(value, { stream: true })
        const lines = buffer.split('\n')
        buffer = lines.pop() || ''

        for (const line of lines) {
          const trimmed = line.trim()
          if (!trimmed || !trimmed.startsWith('data: ')) continue
          
          const data = trimmed.slice(6)
          if (data === '[DONE]') break

          try {
            const step = JSON.parse(data)
            setMessages(prev => prev.map(m => {
              if (m.id === assistantId) {
                const newHistory = [...(m.history || []), step]
                let newContent = m.content
                if (step.type === 'thought') {
                  newContent = step.content
                }
                return { ...m, history: newHistory, content: newContent }
              }
              return m
            }))
          } catch (e) {
            console.error('Error parsing SSE data', e)
          }
        }
      }

      // Final update to set duration and clear thinking state
      setMessages(prev => prev.map(m => {
        if (m.id === assistantId) {
          return { 
            ...m, 
            isThinking: false, 
            duration_ms: Date.now() - startTime,
            content: m.content || 'Analysis complete. Check the trace for details.'
          }
        }
        return m
      }))

    } catch (err: any) {
      setMessages(prev => prev.map(m => {
        if (m.id === assistantId) {
          return { 
            ...m, 
            role: 'error', 
            content: err.message || 'Something went wrong.',
            isThinking: false 
          }
        }
        return m
      }))
    } finally {
      setLoading(false)
      setTimeout(() => inputRef.current?.focus(), 100)
    }
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      sendMessage(e as any)
    }
  }

  return (
    <div className="flex flex-col h-full bg-[#0a0a0f]">
      {/* Header */}
      <div className="flex-shrink-0 border-b border-white/[0.06] bg-[#0d0d14]/80 backdrop-blur-xl px-6 py-4">
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-gradient-to-br from-indigo-500 to-violet-600 flex items-center justify-center shadow-lg shadow-indigo-500/20">
            <Sparkles className="w-5 h-5 text-white" />
          </div>
          <div>
            <h1 className="text-base font-semibold text-white tracking-tight">DataBridge AI</h1>
            <p className="text-xs text-slate-500">Ask anything about your databases - Powered by LangChain Agent</p>
          </div>
        </div>
      </div>

      {/* Chat area */}
      <div className="flex-1 overflow-y-auto">
        <div className="max-w-3xl mx-auto px-4 py-6 space-y-6">
          {/* Welcome state */}
          {messages.length === 0 && (
            <div className="flex flex-col items-center justify-center py-24 text-center">
              <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center mb-6">
                <Bot className="w-8 h-8 text-indigo-400" />
              </div>
              <h2 className="text-xl font-semibold text-white mb-2">What would you like to know?</h2>
              <p className="text-sm text-slate-500 mb-8 max-w-md">
                I can query databases, join data across sources, create/update/delete records, and analyze your data - all in natural language.
              </p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 w-full max-w-lg">
                {[
                  'Show me all employees in the Appraisal system',
                  'How many tables are in each database?',
                  'List all databases I have access to',
                  'Compare employee counts across databases',
                ].map(example => (
                  <button
                    key={example}
                    onClick={() => { setInput(example); inputRef.current?.focus() }}
                    className="text-left text-sm px-4 py-3 rounded-xl bg-white/[0.03] border border-white/[0.06] text-slate-400 hover:text-white hover:bg-white/[0.06] hover:border-white/[0.1] transition-all duration-200"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Messages */}
          {messages.map(msg => (
            <div key={msg.id} className={clsx(
              'flex gap-3',
              msg.role === 'user' ? 'justify-end' : 'justify-start'
            )}>
              {msg.role !== 'user' && (
                <div className={clsx(
                  'flex-shrink-0 w-8 h-8 rounded-lg flex items-center justify-center mt-0.5',
                  msg.role === 'assistant' && 'bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20',
                  msg.role === 'error'     && 'bg-red-500/10 border border-red-500/20',
                )}>
                  <Bot className={clsx(
                    'w-4 h-4',
                    msg.role === 'assistant' ? 'text-indigo-400' : 'text-red-400'
                  )} />
                </div>
              )}

              <div className={clsx(
                'max-w-[85%] rounded-2xl px-4 py-3 text-sm',
                msg.role === 'user'      && 'bg-indigo-600 text-white rounded-tr-md',
                msg.role === 'assistant'  && 'bg-white/[0.04] border border-white/[0.06] text-slate-300',
                msg.role === 'error'      && 'bg-red-500/10 border border-red-500/20 text-red-300',
              )}>
                {msg.role === 'assistant' ? (
                  <MarkdownishText text={msg.content} />
                ) : (
                  <p className="whitespace-pre-wrap">{msg.content}</p>
                )}

                {/* Agent trace */}
                {msg.history && msg.history.length > 0 && (
                  <AgentTrace history={msg.history} isThinking={msg.isThinking} />
                )}

                {/* Duration */}
                {msg.duration_ms && (
                  <p className="text-[10px] text-slate-600 mt-2 text-right">
                    {(msg.duration_ms / 1000).toFixed(1)}s
                  </p>
                )}
              </div>

              {msg.role === 'user' && (
                <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-indigo-600/20 border border-indigo-500/20 flex items-center justify-center mt-0.5">
                  <User className="w-4 h-4 text-indigo-400" />
                </div>
              )}
            </div>
          ))}

          {/* Loading indicator */}
          {loading && (
            <div className="flex gap-3">
              <div className="flex-shrink-0 w-8 h-8 rounded-lg bg-gradient-to-br from-indigo-500/20 to-violet-600/20 border border-indigo-500/20 flex items-center justify-center">
                <Bot className="w-4 h-4 text-indigo-400" />
              </div>
              <div className="bg-white/[0.04] border border-white/[0.06] rounded-2xl px-4 py-3 flex items-center gap-3">
                <Loader2 className="w-4 h-4 text-indigo-400 animate-spin" />
                <span className="text-sm text-slate-500">Thinking...</span>
              </div>
            </div>
          )}

          <div ref={bottomRef} />
        </div>
      </div>

      {/* Input area */}
      <div className="flex-shrink-0 border-t border-white/[0.06] bg-[#0d0d14]/80 backdrop-blur-xl px-4 py-4">
        <form onSubmit={sendMessage} className="max-w-3xl mx-auto">
          <div className="relative flex items-end gap-2 bg-white/[0.04] border border-white/[0.08] rounded-2xl px-4 py-3 focus-within:border-indigo-500/40 focus-within:ring-1 focus-within:ring-indigo-500/20 transition-all">
            <textarea
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="Ask anything about your data..."
              rows={1}
              className="flex-1 bg-transparent text-sm text-white placeholder-slate-600 resize-none outline-none min-h-[24px] max-h-32"
              style={{ lineHeight: '24px' }}
            />
            <button
              type="submit"
              disabled={loading || !input.trim()}
              className="flex-shrink-0 w-8 h-8 rounded-lg bg-indigo-600 hover:bg-indigo-500 disabled:bg-white/[0.06] disabled:text-slate-600 text-white flex items-center justify-center transition-colors"
            >
              {loading ? <Loader2 className="w-4 h-4 animate-spin" /> : <Send className="w-4 h-4" />}
            </button>
          </div>
          <p className="text-[10px] text-slate-600 text-center mt-2">
            Agent has access to all your databases - Cross-DB queries - CRUD operations
          </p>
        </form>
      </div>
    </div>
  )
}
