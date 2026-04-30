'use client'

import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { BackgroundMatrix } from '@/components/BackgroundMatrix'
import { getApiUrl, getWebSocketUrl } from '@/lib/api'

type StatusType = 'connecting' | 'running' | 'waiting_input' | 'failed' | 'completed'

type StatusPayload = {
  status: StatusType
  step?: string
  progress?: number
  module?: 'BD_PACK' | 'ECM_PACK' | 'SANC_PACK' | 'EAR_CREATION' | 'DATASOURCE_CREATION' | 'BACKUP' | 'RESTORE'
}

const BD_PACK_STEPS = [
  'Creating oracle user and oinstall group',
  'Creating mount point /u01',
  'Installing KSH and git',
  'Creating .profile file',
  'Installing Java and updating profile',
  'Creating OFSAA directory structure',
  'Checking Oracle client and updating profile',
  'Setting up OFSAA installer and running environment check',
  'Applying config XMLs/properties and running osc.sh',
  'Installing BD PACK with /setup.sh SILENT'
]

const ECM_PACK_STEPS = [
  'Downloading and extracting ECM installer kit',
  'Setting ECM kit permissions',
  'Applying ECM configuration files',
  'Running ECM schema creator (osc.sh)',
  'Running ECM setup (setup.sh SILENT)'
]

const SANC_PACK_STEPS = [
  'Downloading and extracting SANC installer kit',
  'Setting SANC kit permissions',
  'Applying SANC configuration files',
  'Running SANC schema creator (osc.sh)',
  'Running SANC setup (setup.sh SILENT)'
]

const EAR_CREATION_STEPS = [
  'Initializing EAR creation & exploding',
  'Granting database privileges',
  'Running EAR creation & exploding script',
  'Running startofsaa.sh',
  'Running checkofsaa.sh',
  'Datasources + App Deployment',
  'Deployment completed'
  // Dynamic datasource steps (e.g. "Creating ANALYST") are appended at runtime
]

const DATASOURCE_CREATION_STEPS = [
  'Initializing datasource creation'
  // Dynamic steps like "Creating ANALYST" are added at runtime
]

const BACKUP_STEPS: string[] = []

const RESTORE_STEPS: string[] = []

function buildBackupTrackerSteps(step: string, previousSteps: string[]): string[] {
  const normalized = step.trim()
  if (!normalized) return previousSteps

  if (normalized.startsWith('Validating backup before ')) {
    return [normalized]
  }

  const taggedAppMatch = normalized.match(/^Taking application backup \(tar\)(?: \[(.+)\])?$/)
  const taggedDbMatch = normalized.match(/^Taking DB schema backup(?: \[(.+)\])?$/)
  if (taggedAppMatch || taggedDbMatch) {
    const existingValidation = previousSteps.find(item => item.startsWith('Validating backup before '))
    const backupTag = (taggedAppMatch?.[1] || taggedDbMatch?.[1] || '').trim()
    const appStep = backupTag ? `Taking application backup (tar) [${backupTag}]` : 'Taking application backup (tar)'
    const dbStep = backupTag ? `Taking DB schema backup [${backupTag}]` : 'Taking DB schema backup'
    return existingValidation ? [existingValidation, appStep, dbStep] : [appStep, dbStep]
  }

  if (previousSteps.includes(normalized)) return previousSteps
  return [...previousSteps, normalized]
}

function buildRestoreTrackerSteps(step: string, previousSteps: string[]): string[] {
  const normalized = step.trim()
  if (!normalized) return previousSteps

  if (normalized.startsWith('Restoring to ') && normalized.includes(' state after ')) {
    return [normalized, 'Restoring application', 'Restoring DB schemas']
  }

  if (normalized === 'Restoring application' || normalized === 'Restoring DB schemas') {
    const restoreHeader = previousSteps.find(item => item.startsWith('Restoring to '))
    return restoreHeader
      ? [restoreHeader, 'Restoring application', 'Restoring DB schemas']
      : ['Restoring application', 'Restoring DB schemas']
  }

  if (previousSteps.includes(normalized)) return previousSteps
  return [...previousSteps, normalized]
}

export default function LogsPage() {
  const params = useParams()
  const router = useRouter()
  const taskId = String(params?.taskId || '')
  const redirectDelaySec = 120
  const [status, setStatus] = useState<StatusType>('connecting')
  const [currentStep, setCurrentStep] = useState<string>('Initializing connection')
  const [progress, setProgress] = useState<number>(0)
  const [prompt, setPrompt] = useState<string>('')
  const [promptQueue, setPromptQueue] = useState<string[]>([])
  const [inputText, setInputText] = useState('')
  const [outputLines, setOutputLines] = useState<string[]>([])
  const [autoFollowOutput, setAutoFollowOutput] = useState(true)
  const [redirectCountdown, setRedirectCountdown] = useState<number>(redirectDelaySec)
  const [currentModule, setCurrentModule] = useState<'BD_PACK' | 'ECM_PACK' | 'SANC_PACK' | 'EAR_CREATION' | 'DATASOURCE_CREATION' | 'BACKUP' | 'RESTORE'>('BD_PACK')
  const [dynamicDsSteps, setDynamicDsSteps] = useState<string[]>([...DATASOURCE_CREATION_STEPS])
  const [dynamicEarSteps, setDynamicEarSteps] = useState<string[]>([...EAR_CREATION_STEPS])
  const [dynamicBackupSteps, setDynamicBackupSteps] = useState<string[]>([...BACKUP_STEPS])
  const [dynamicRestoreSteps, setDynamicRestoreSteps] = useState<string[]>([...RESTORE_STEPS])
  const [maxStepReached, setMaxStepReached] = useState<number>(-1)
  const [isCancelling, setIsCancelling] = useState(false)
  const [previousModule, setPreviousModule] = useState<string>('')
  const socketRef = useRef<WebSocket | null>(null)
  const outputEndRef = useRef<HTMLDivElement>(null)
  const outputContainerRef = useRef<HTMLDivElement>(null)
  const pendingLinesRef = useRef<string[]>([])
  const rafIdRef = useRef<number | null>(null)
  const lineCounterRef = useRef(0)

  // Determine which module is active based on current step
  const activeSteps = useMemo(() => {
    if (currentModule === 'ECM_PACK') return ECM_PACK_STEPS
    if (currentModule === 'SANC_PACK') return SANC_PACK_STEPS
    if (currentModule === 'EAR_CREATION') return dynamicEarSteps
    if (currentModule === 'DATASOURCE_CREATION') return dynamicDsSteps
    if (currentModule === 'BACKUP') return dynamicBackupSteps
    if (currentModule === 'RESTORE') return dynamicRestoreSteps
    return BD_PACK_STEPS
  }, [currentModule, dynamicDsSteps, dynamicEarSteps, dynamicBackupSteps, dynamicRestoreSteps])

  // Reset maxStepReached when module changes
  useEffect(() => {
    setMaxStepReached(-1)
  }, [currentModule])

  // Track highest step index reached in the current module
  useEffect(() => {
    const idx = activeSteps.indexOf(currentStep)
    if (idx >= 0) {
      setMaxStepReached(prev => Math.max(prev, idx))
    }
  }, [currentStep, activeSteps])

  const moduleLabel = useMemo(() => {
    if (currentModule === 'ECM_PACK') return 'ECM Pack'
    if (currentModule === 'SANC_PACK') return 'SANC Pack'
    if (currentModule === 'EAR_CREATION') return 'Deployment'
    if (currentModule === 'DATASOURCE_CREATION') return 'Datasource Creation'
    if (currentModule === 'BACKUP') return 'Backup'
    if (currentModule === 'RESTORE') return 'Restore'
    return 'BD Pack'
  }, [currentModule])

  const statusLabel = useMemo(() => {
    if (status === 'waiting_input') return 'waiting for input'
    if (status === 'connecting') return 'connecting'
    return status
  }, [status])

  useEffect(() => {
    if (!taskId) return

    const ws = new WebSocket(`${getWebSocketUrl()}/ws/${taskId}`)
    socketRef.current = ws

    ws.onopen = () => {
      setStatus('running')
    }

    ws.onmessage = event => {
      try {
        const message = JSON.parse(event.data)
        if (message.type === 'historical_logs') {
          // On reconnect/refresh: load all previous logs from disk
          const logs = Array.isArray(message.data) ? message.data : [message.data]
          const lines = logs
            .flatMap((line: string) => String(line || '').split(/\r?\n/))
            .filter((l: string) => l.length > 0)
          if (lines.length) {
            lineCounterRef.current = lines.length
            setOutputLines(lines)
          }
        }
        if (message.type === 'output') {
          const chunk = String(message.data || '')
          const lines = chunk.split(/\r?\n/).filter(l => l.length > 0)
          if (lines.length) {
            // Batch into a pending buffer and flush once per animation frame
            pendingLinesRef.current.push(...lines)
            if (rafIdRef.current === null) {
              rafIdRef.current = requestAnimationFrame(() => {
                const batch = pendingLinesRef.current
                pendingLinesRef.current = []
                rafIdRef.current = null
                if (batch.length) {
                  lineCounterRef.current += batch.length
                  setOutputLines(prev => {
                    const merged = prev.concat(batch)
                    // Keep only the last 2000 lines in state to prevent memory bloat
                    return merged.length > 2000 ? merged.slice(-2000) : merged
                  })
                }
              })
            }
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
          if (data?.step) {
            setCurrentStep(data.step)
          }
          // Use authoritative module from backend if available, fallback to heuristic
          if (data?.module) {
            // Remember the module before BACKUP/RESTORE so we can return to it
            if (data.module !== 'BACKUP' && data.module !== 'RESTORE') {
              setPreviousModule(data.module)
            }
            setCurrentModule(data.module)
          } else if (data?.step) {
            if (EAR_CREATION_STEPS.some(s => s === data.step)) {
              setCurrentModule('EAR_CREATION')
            } else if (data.step.toLowerCase().includes('sanc')) {
              setCurrentModule('SANC_PACK')
            } else if (SANC_PACK_STEPS.some(s => s === data.step)) {
              setCurrentModule('SANC_PACK')
            } else if (data.step.toLowerCase().includes('ecm')) {
              setCurrentModule('ECM_PACK')
            } else if (ECM_PACK_STEPS.some(s => s === data.step)) {
              setCurrentModule('ECM_PACK')
            } else if (BD_PACK_STEPS.some(s => s === data.step)) {
              setCurrentModule('BD_PACK')
            }
          }
          // For datasource creation, dynamically add step names (e.g. "Creating ANALYST")
          if (data?.module === 'DATASOURCE_CREATION' && data?.step) {
            setDynamicDsSteps(prev => {
              if (prev.includes(data.step!)) return prev
              return [...prev, data.step!]
            })
          }
          // For BACKUP module, dynamically add step names (tag varies)
          if (data?.module === 'BACKUP' && data?.step) {
            setDynamicBackupSteps(prev => buildBackupTrackerSteps(data.step!, prev))
          }
          // For RESTORE module, dynamically add step names
          if (data?.module === 'RESTORE' && data?.step) {
            setDynamicRestoreSteps(prev => buildRestoreTrackerSteps(data.step!, prev))
          }
          // For EAR_CREATION module, dynamically add datasource steps (e.g. "Creating ANALYST")
          if (data?.module === 'EAR_CREATION' && data?.step) {
            const step = data.step
            // Add datasource steps that aren't in the base EAR list
            if (step.startsWith('Creating ') || step === 'Initializing datasource creation' || step === 'Deployment completed' || step.startsWith('Completed with')) {
              setDynamicEarSteps(prev => {
                if (prev.includes(step)) return prev
                // Insert before the last "completed" step, or append
                const completedIdx = prev.indexOf('EAR creation & exploding completed')
                if (completedIdx >= 0) {
                  const updated = [...prev]
                  updated.splice(completedIdx + 1, 0, step)
                  return updated
                }
                return [...prev, step]
              })
            }
          }
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
      if (rafIdRef.current !== null) cancelAnimationFrame(rafIdRef.current)
    }
  }, [taskId])

  useEffect(() => {
    // Only auto-scroll if user is at the bottom (autoFollowOutput is true)
    if (autoFollowOutput && outputContainerRef.current) {
      // Defer scroll until DOM is updated
      requestAnimationFrame(() => {
        if (outputContainerRef.current) {
          outputContainerRef.current.scrollTop = outputContainerRef.current.scrollHeight
        }
      })
    }
  }, [outputLines, autoFollowOutput])

  useEffect(() => {
    if (status !== 'failed') return
    setRedirectCountdown(redirectDelaySec)
    const tick = setInterval(() => {
      setRedirectCountdown(prev => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    const timer = setTimeout(() => {
      router.push('/')
    }, redirectDelaySec * 1000)
    return () => {
      clearTimeout(timer)
      clearInterval(tick)
    }
  }, [status, router, redirectDelaySec])

  const handleOutputScroll = () => {
    const el = outputContainerRef.current
    if (!el) return
    const threshold = 80
    const atBottom = el.scrollHeight - el.scrollTop - el.clientHeight <= threshold
    setAutoFollowOutput(atBottom)
  }

  const handleSendInput = () => {
    if (!inputText || !socketRef.current) return
    socketRef.current.send(JSON.stringify({ type: 'user_input', input: inputText }))
    setOutputLines(prev => prev.concat(`> ${inputText}`))
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

  const handleDownloadLogs = useCallback(async () => {
    // Try to fetch full logs from backend (disk-persisted, not capped)
    try {
      const resp = await fetch(`${getApiUrl()}/api/installation/logs/${taskId}/full`)
      if (resp.ok) {
        const blob = await resp.blob()
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = `installation-logs-${taskId.slice(0, 8)}.txt`
        a.click()
        URL.revokeObjectURL(url)
        return
      }
    } catch { /* fallback to local lines */ }
    // Fallback: use in-memory lines (may be capped)
    const content = outputLines.join('\n')
    const blob = new Blob([content], { type: 'text/plain' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `installation-logs-${taskId.slice(0, 8)}.txt`
    a.click()
    URL.revokeObjectURL(url)
  }, [taskId, outputLines])

  // Auto-download logs on completion or failure (including restore-then-fail scenarios)
  const autoDownloadedRef = useRef(false)
  useEffect(() => {
    if ((status === 'completed' || status === 'failed') && outputLines.length > 0 && !autoDownloadedRef.current) {
      autoDownloadedRef.current = true
      // Small delay to ensure final log lines are captured
      const timer = setTimeout(() => handleDownloadLogs(), 1500)
      return () => clearTimeout(timer)
    }
  }, [status, outputLines.length, handleDownloadLogs])

  // Warn user before leaving if task is running (browser close triggers backend grace timer)
  useEffect(() => {
    const isRunning = status === 'running' || status === 'waiting_input' || status === 'connecting'
    if (!isRunning) return
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault()
      e.returnValue = ''
    }
    window.addEventListener('beforeunload', handler)
    return () => window.removeEventListener('beforeunload', handler)
  }, [status])

  const handleCancelTask = async () => {
    if (!confirm('Are you sure you want to stop this process? This will kill all running commands on the remote server.')) return
    setIsCancelling(true)
    try {
      const resp = await fetch(`${getApiUrl()}/api/installation/tasks/${taskId}/cancel`, { method: 'DELETE' })
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({}))
        alert(err.detail || 'Failed to cancel task')
      }
    } catch (e) {
      alert('Failed to cancel: ' + (e instanceof Error ? e.message : 'unknown error'))
    } finally {
      setIsCancelling(false)
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
            {(status === 'running' || status === 'waiting_input' || status === 'connecting') && (
              <button
                onClick={handleCancelTask}
                disabled={isCancelling}
                className="px-3 py-1 rounded-md border border-red-500/60 text-red-400 hover:bg-red-500/20 hover:text-red-300 hover:border-red-400 transition-colors disabled:opacity-40 disabled:cursor-not-allowed font-semibold"
              >
                {isCancelling ? 'Stopping...' : 'Stop Process'}
              </button>
            )}
            <button
              onClick={handleDownloadLogs}
              disabled={outputLines.length === 0}
              className="px-3 py-1 rounded-md border border-border text-text-secondary hover:text-white hover:border-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Download Logs
            </button>
          </div>
        </div>

        {/* Main Layout */}
        <div className="flex-1 min-h-0 grid grid-cols-1 lg:grid-cols-[280px_1fr] gap-4 p-4 lg:p-8">
          {/* Left Panel - Steps */}
          <div className="glass-panel rounded-xl p-4 lg:p-6 shadow-panel h-[72vh] max-h-[72vh] min-h-[72vh] overflow-y-auto lg:h-[calc(100vh-10rem)] lg:max-h-[calc(100vh-10rem)] lg:min-h-[calc(100vh-10rem)]">
            <div className="text-xs font-bold uppercase tracking-widest text-text-secondary mb-2">
              {moduleLabel}
            </div>
            <div className="text-xs text-text-muted mb-4">
              Step Tracker
            </div>
            <div className="space-y-3 text-sm">
              {activeSteps.map((step, idx) => {
                const isActive = currentStep === step
                const isCompleted =
                  status === 'completed' ||
                  (maxStepReached >= 0 && idx < maxStepReached)
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
          <div className="flex h-[72vh] max-h-[72vh] min-h-[72vh] flex-col glass-panel rounded-xl shadow-panel overflow-hidden lg:h-[calc(100vh-10rem)] lg:max-h-[calc(100vh-10rem)] lg:min-h-[calc(100vh-10rem)]">
            <div className="px-4 py-3 border-b border-border bg-bg-secondary/50">
              <div className="text-xs uppercase tracking-widest text-text-secondary">Live Terminal Output</div>
              <div className="text-sm text-text-primary mt-1">{currentStep}</div>
            </div>
            <div
              ref={outputContainerRef}
              onScroll={handleOutputScroll}
              className="flex-1 min-h-0 max-h-full terminal overflow-y-auto overflow-x-hidden scrollbar-thin scrollbar-track-gray-900 scrollbar-thumb-gray-700"
            >
              {outputLines.map((line, idx) => (
                <div key={idx} className="whitespace-pre-wrap break-words leading-relaxed">
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
              {status === 'failed' && (
                <div className="text-xs text-warning mb-2">
                  Returning to form with saved inputs in {redirectCountdown}s...
                </div>
              )}
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
