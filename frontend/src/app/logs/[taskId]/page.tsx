'use client'

import { useEffect, useMemo, useRef, useState } from 'react'
import { useParams } from 'next/navigation'
import { BackgroundMatrix } from '@/components/BackgroundMatrix'

type StatusType = 'connecting' | 'running' | 'waiting_input' | 'failed' | 'completed'

type StatusPayload = {
  status: StatusType
  step?: string
  progress?: number
}

const STEPS = [
  'Creating oracle user and oinstall group',
  'Creating mount point /u01',
  'Installing KSH and git',
  'Creating .profile file',
  'Installing Java and updating profile',
  'Creating OFSAA directory structure',
  'Checking Oracle client and updating profile',
  'Setting up OFSAA installer and running environment check',
  'Applying config XMLs/properties and running osc.sh'
]

export default function LogsPage() {
  const params = useParams()
  const taskId = String(params?.taskId || '')
  const [status, setStatus] = useState<StatusType>('connecting')
  const [currentStep, setCurrentStep] = useState<string>('Initializing connection')
  const [progress, setProgress] = useState<number>(0)
  const [prompt, setPrompt] = useState<string>('')
  const [promptQueue, setPromptQueue] = useState<string[]>([])
  const [inputText, setInputText] = useState('')
  const [outputLines, setOutputLines] = useState<string[]>([])
  const socketRef = useRef<WebSocket | null>(null)
  const outputEndRef = useRef<HTMLDivElement>(null)

  const statusLabel = useMemo(() => {
    if (status === 'waiting_input') return 'waiting for input'
    if (status === 'connecting') return 'connecting'
    return status
  }, [status])

  useEffect(() => {
    if (!taskId) return

    const ws = new WebSocket(`ws://localhost:8000/ws/${taskId}`)
    socketRef.current = ws

    ws.onopen = () => {
      setStatus('running')
      setOutputLines(prev => [...prev, '[CONNECTED] Live log stream started'])
    }

    ws.onmessage = event => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'output') {
          const chunk = String(message.data || '')
          const lines = chunk.split(/\r?\n/).filter(l => l.length > 0)
          if (lines.length) {
            setOutputLines(prev => [...prev, ...lines])
          }
        }
        if (message.type === 'prompt') {
          const promptText = String(message.data || '')
          const lines = promptText.split(/\r?\n/).map(l => l.trim()).filter(Boolean)
          if (lines.length <= 1) {
            setPrompt(lines[0] || promptText)
            setStatus('waiting_input')
          } else {
            setPrompt(lines[0])
            setPromptQueue(lines.slice(1))
            setStatus('waiting_input')
          }
        }
        if (message.type === 'status') {
          const data = message.data as StatusPayload
          if (data?.status) setStatus(data.status)
          if (data?.step) setCurrentStep(data.step)
          if (typeof data?.progress === 'number') setProgress(data.progress)
        }
      } catch {
        // Ignore malformed frames
      }
    }

    ws.onclose = () => {
      if (status !== 'completed' && status !== 'failed') {
        setStatus('connecting')
      }
    }

    return () => {
      ws.close()
    }
  }, [taskId])

  useEffect(() => {
    outputEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [outputLines])

  const handleSendInput = () => {
    if (!inputText || !socketRef.current) return
    socketRef.current.send(JSON.stringify({ type: 'user_input', input: inputText }))
    setOutputLines(prev => [...prev, `> ${inputText}`])
    setInputText('')
    if (promptQueue.length > 0) {
      const [nextPrompt, ...rest] = promptQueue
      setPrompt(nextPrompt)
      setPromptQueue(rest)
      setStatus('waiting_input')
    } else {
      setPrompt('')
      setStatus('running')
    }
  }

  const statusColor = (() => {
    if (status === 'failed') return 'text-error'
    if (status === 'completed') return 'text-success'
    if (status === 'waiting_input') return 'text-warning'
    return 'text-text-primary'
  })()

  return (
    <div className="relative min-h-screen bg-bg-primary">
      <BackgroundMatrix />

      <div className="relative z-10 min-h-screen flex flex-col">
        {/* Top Status Bar */}
        <div className="px-4 lg:px-8 py-4 border-b border-border flex items-center justify-between bg-bg-secondary/60 backdrop-blur">
          <div className="flex items-center gap-4">
            <div className={`text-sm font-bold uppercase tracking-widest ${statusColor}`}>
              {statusLabel}
            </div>
            <div className="text-xs text-text-muted">Task: {taskId.slice(0, 8)}...</div>
          </div>
          <div className="text-xs text-text-secondary flex items-center gap-3">
            <span>Progress</span>
            <div className="w-40 h-1 bg-bg-tertiary rounded">
              <div
                className="h-1 bg-white rounded"
                style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
              />
            </div>
            <span>{progress}%</span>
          </div>
        </div>

        {/* Main Layout */}
        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4 p-4 lg:p-8">
          {/* Left Panel - Steps */}
          <div className="glass-panel rounded-xl p-4 lg:p-6 shadow-panel">
            <div className="text-xs font-bold uppercase tracking-widest text-text-secondary mb-4">
              Step Tracker
            </div>
            <div className="space-y-3 text-sm">
              {STEPS.map(step => {
                const isActive = currentStep === step
                const isCompleted =
                  progress >= 100 ||
                  (progress > 0 && STEPS.indexOf(step) < STEPS.indexOf(currentStep))
                return (
                  <div
                    key={step}
                    className={`flex items-start gap-3 ${
                      isActive ? 'text-white' : isCompleted ? 'text-text-secondary' : 'text-text-muted'
                    }`}
                  >
                    <div
                      className={`mt-1 h-2 w-2 rounded-full ${
                        isActive ? 'bg-white' : isCompleted ? 'bg-success' : 'bg-border'
                      }`}
                    />
                    <div className="leading-snug">{step}</div>
                  </div>
                )
              })}
            </div>
          </div>

          {/* Center Panel - Live Terminal */}
          <div className="flex min-h-0 flex-col glass-panel rounded-xl shadow-panel overflow-hidden">
            <div className="px-4 py-3 border-b border-border bg-bg-secondary/50">
              <div className="text-xs uppercase tracking-widest text-text-secondary">Live Terminal Output</div>
              <div className="text-sm text-text-primary mt-1">{currentStep}</div>
            </div>
            <div className="flex-1 min-h-0 terminal overflow-auto scrollbar-thin scrollbar-track-gray-900 scrollbar-thumb-gray-700">
              {outputLines.map((line, idx) => (
                <div key={`${idx}-${line}`} className="whitespace-pre leading-relaxed min-w-max">
                  {line}
                </div>
              ))}
              <div ref={outputEndRef} />
            </div>

            {/* Bottom Input */}
            <div className="border-t border-border bg-bg-secondary/70 px-4 py-3">
              <div className="text-xs text-text-secondary mb-2">
                {prompt ? `Prompt: ${prompt}` : 'Waiting for prompt...'}
              </div>
              <div className="flex gap-3">
                <textarea
                  value={inputText}
                  onChange={e => setInputText(e.target.value)}
                  onKeyDown={e => {
                    if (e.key === 'Enter' && !e.shiftKey) {
                      e.preventDefault()
                      handleSendInput()
                    }
                  }}
                  placeholder="Type response. Use Shift+Enter for multi-line. Press Enter to send."
                  rows={2}
                  className="flex-1 bg-bg-tertiary border border-border rounded-md px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-white resize-none"
                  disabled={status !== 'waiting_input'}
                />
                <button
                  onClick={handleSendInput}
                  disabled={status !== 'waiting_input' || !inputText}
                  className="px-4 py-2 rounded-md bg-white text-black text-sm font-bold disabled:opacity-50"
                >
                  Send
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
