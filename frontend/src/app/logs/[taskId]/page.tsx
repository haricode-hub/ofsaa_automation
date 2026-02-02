'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeftIcon,
  CommandLineIcon,
  SignalIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  ServerIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  PlayIcon,
  PauseIcon,
  EyeIcon,
  ClockIcon
} from '@heroicons/react/24/outline'

interface LogEntry {
  timestamp: string
  level: 'INFO' | 'ERROR' | 'SUCCESS' | 'WARNING'
  message: string
}

export default function LogsPage() {
  const params = useParams()
  const router = useRouter()
  const taskId = params?.taskId as string
  
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [currentStep, setCurrentStep] = useState<string>('')
  const [progress, setProgress] = useState<number>(0)
  const [status, setStatus] = useState<'idle' | 'running' | 'success' | 'error'>('running')
  const [filterLevel, setFilterLevel] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isAutoScroll, setIsAutoScroll] = useState(true)
  const [isPaused, setIsPaused] = useState(false)
  
  const logsEndRef = useRef<HTMLDivElement>(null)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const formatLogEntry = (logText: string): LogEntry => {
    const timestamp = new Date().toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
    
    let level: LogEntry['level'] = 'INFO'
    if (logText.includes('❌') || logText.includes('ERROR') || logText.includes('failed') || logText.includes('Failed')) {
      level = 'ERROR'
    } else if (logText.includes('✅') || logText.includes('SUCCESS') || logText.includes('successful') || logText.includes('Complete')) {
      level = 'SUCCESS'
    } else if (logText.includes('⚠️') || logText.includes('WARNING')) {
      level = 'WARNING'
    }
    
    return { timestamp, level, message: logText }
  }

  useEffect(() => {
    if (!taskId) return

    const pollStatus = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/installation/status/${taskId}`)
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const statusData = await response.json()
        
        setCurrentStep(statusData.current_step || '')
        setProgress(statusData.progress || 0)
        
        // Format and update logs - only add new logs to prevent blinking
        if (statusData.logs && statusData.logs.length > 0) {
          const formattedLogs = statusData.logs.map(formatLogEntry)
          setLogs(prevLogs => {
            // Compare the actual content to avoid unnecessary updates
            const prevContent = prevLogs.map((log: LogEntry) => log.message).join('|')
            const newContent = formattedLogs.map((log: LogEntry) => log.message).join('|')
            
            if (prevContent !== newContent) {
              return formattedLogs
            }
            return prevLogs
          })
        }
        
        if (statusData.status === 'completed') {
          setStatus('success')
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
          }
          
          const successEntry = formatLogEntry('System preparation completed - Ready for OFSAA installation!')
          setLogs(prev => [...prev, successEntry])
        } else if (statusData.status === 'failed') {
          setStatus('error')
          if (pollIntervalRef.current) {
            clearInterval(pollIntervalRef.current)
          }
          
          const errorEntry = formatLogEntry(`Installation failed: ${statusData.error || 'Unknown error'}`)
          setLogs(prev => [...prev, errorEntry])
        }
      } catch (error) {
        console.error('Failed to poll status:', error)
        setStatus('error')
        if (pollIntervalRef.current) {
          clearInterval(pollIntervalRef.current)
        }
        
        const errorEntry = formatLogEntry('Connection to backend lost')
        setLogs(prev => [...prev, errorEntry])
      }
    }

    // Start polling immediately
    pollStatus()
    
    // Continue polling every 1.5 seconds
    pollIntervalRef.current = setInterval(pollStatus, 1500)

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [taskId])

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isAutoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, isAutoScroll])

  const filteredLogs = logs.filter(log => {
    const matchesFilter = filterLevel === 'all' || log.level === filterLevel
    const matchesSearch = searchQuery === '' || 
      log.message.toLowerCase().includes(searchQuery.toLowerCase())
    return matchesFilter && matchesSearch
  })

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <ArrowPathIcon className="w-5 h-5 text-warning animate-spin" />
      case 'success':
        return <CheckCircleIcon className="w-5 h-5 text-success" />
      case 'error':
        return <ExclamationCircleIcon className="w-5 h-5 text-error" />
      default:
        return <CommandLineIcon className="w-5 h-5 text-text-muted" />
    }
  }

  const getStatusText = () => {
    switch (status) {
      case 'running':
        return 'Installation in Progress'
      case 'success':
        return 'System Preparation Complete'
      case 'error':
        return 'Installation Failed'
      default:
        return 'Initializing...'
    }
  }

  return (
    <div className="relative min-h-screen bg-bg-primary">
      <div className="h-screen flex flex-col">
        
        {/* Header */}
        <div className="flex items-center justify-between p-4 lg:p-6 border-b border-border bg-bg-secondary">
          <div className="flex items-center gap-4">
            <button
              onClick={() => router.push('/')}
              className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors"
            >
              <ArrowLeftIcon className="w-5 h-5 text-text-muted hover:text-text-primary" />
            </button>
            
            <div className="flex items-center gap-3">
              {getStatusIcon()}
              <div>
                <h1 className="text-xl lg:text-2xl font-bold text-text-primary tracking-tight">
                  {getStatusText()}
                </h1>
                <p className="text-sm text-text-muted font-mono">Task ID: {taskId}</p>
              </div>
            </div>
            
            {status === 'running' && (
              <div className="flex items-center gap-2 text-sm text-text-secondary">
                <SignalIcon className="w-4 h-4 text-success animate-pulse" />
                <span className="font-mono">LIVE</span>
              </div>
            )}
          </div>
          
          <div className="text-xs font-mono text-text-muted">
            Task: {taskId}
          </div>
        </div>

        {/* Status Bar */}
        {currentStep && (
          <div className="px-4 lg:px-6 py-4 bg-bg-secondary border-b border-border">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ServerIcon className="w-4 h-4 text-text-secondary" />
                <span className="text-sm font-medium text-text-primary">{currentStep}</span>
              </div>
              {progress > 0 && (
                <span className="text-sm font-mono text-text-secondary">{progress}%</span>
              )}
            </div>
            {progress > 0 && (
              <div className="w-full bg-bg-tertiary rounded-full h-3 overflow-hidden">
                <motion.div 
                  className="h-full bg-gradient-to-r from-white to-gray-300 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>
            )}
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center gap-3 px-4 lg:px-6 py-3 bg-bg-secondary border-b border-border">
          {/* Search */}
          <div className="relative flex-1 max-w-sm">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input
              type="text"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-white"
            />
          </div>

          {/* Filter */}
          <div className="relative">
            <FunnelIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="pl-9 pr-8 py-2 text-sm bg-bg-tertiary border border-border rounded-lg text-text-primary focus:outline-none focus:border-white appearance-none cursor-pointer"
            >
              <option value="all">All Levels</option>
              <option value="INFO">Info</option>
              <option value="SUCCESS">Success</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
            </select>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors"
              title={isPaused ? "Resume" : "Pause"}
            >
              {isPaused ? 
                <PlayIcon className="w-4 h-4 text-text-muted hover:text-text-primary" /> :
                <PauseIcon className="w-4 h-4 text-text-muted hover:text-text-primary" />
              }
            </button>
            <button
              onClick={() => setIsAutoScroll(!isAutoScroll)}
              className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors"
              title={isAutoScroll ? "Disable auto-scroll" : "Enable auto-scroll"}
            >
              <EyeIcon className={`w-4 h-4 transition-colors ${
                isAutoScroll ? "text-success" : "text-text-muted hover:text-text-primary"
              }`} />
            </button>
          </div>
        </div>

        {/* Log Content - Scrollable Area */}
        <div className="flex-1 min-h-0 bg-gray-950 relative">
          <div className="h-full overflow-y-auto scrollbar-thin scrollbar-track-gray-900 scrollbar-thumb-gray-700 hover:scrollbar-thumb-gray-600">
            <div className="p-4 lg:p-6">
              {/* Terminal header */}
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-gray-800 sticky top-0 bg-gray-950 z-10">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-error" />
                  <div className="w-3 h-3 rounded-full bg-warning" />
                  <div className="w-3 h-3 rounded-full bg-success" />
                </div>
                <DocumentTextIcon className="w-4 h-4 text-text-muted ml-2" />
                <span className="text-sm font-mono text-text-muted">installation.log</span>
                <div className="flex-1" />
                <div className="flex items-center gap-2 text-sm font-mono text-text-muted">
                  <ClockIcon className="w-4 h-4" />
                  <span>{new Date().toLocaleTimeString()}</span>
                </div>
              </div>
          
          {/* Log entries */}
          <div className="space-y-2 text-sm lg:text-base font-mono">
            {filteredLogs.length === 0 ? (
              <div className="flex items-center justify-center py-16 text-text-muted">
                <div className="text-center">
                  <CommandLineIcon className="w-16 h-16 mx-auto mb-6 opacity-50" />
                  <p className="text-xl mb-3 font-medium">No logs to display</p>
                  {searchQuery && (
                    <p className="text-sm opacity-75">Try adjusting your search or filter criteria</p>
                  )}
                </div>
              </div>
            ) : (
              filteredLogs.map((log, index) => (
                <motion.div 
                  key={`${log.message}-${log.timestamp}`}
                  className="flex items-start gap-4 py-3 px-4 rounded-lg hover:bg-bg-secondary/30 transition-all duration-200 group border-l-2 border-transparent hover:border-text-muted/20"
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{ duration: 0.2 }}
                >
                  <span className="text-text-muted/80 shrink-0 w-20 text-xs font-medium tracking-wide">
                    {log.timestamp}
                  </span>
                  <span className={`shrink-0 w-18 text-center rounded-md px-2 py-1 text-xs font-bold uppercase tracking-wider shadow-sm ${
                    log.level === 'INFO' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                    log.level === 'ERROR' ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
                    log.level === 'SUCCESS' ? 'bg-green-500/20 text-green-300 border border-green-500/30' :
                    'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30'
                  }`}>
                    {log.level}
                  </span>
                  <span className="text-text-primary flex-1 leading-relaxed break-words group-hover:text-white transition-colors duration-200">
                    {log.message}
                  </span>
                </motion.div>
              ))
            )}
            
            {/* Live cursor when active */}
            {status === 'running' && !isPaused && (
              <motion.div 
                className="flex items-center gap-4 py-2 px-3"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
              >
                <span className="text-text-muted shrink-0 w-24 text-sm">
                  {new Date().toLocaleTimeString('en-US', { 
                    hour12: false, 
                    hour: '2-digit', 
                    minute: '2-digit', 
                    second: '2-digit' 
                  })}
                </span>
                <div className="w-3 h-5 bg-success animate-blink ml-20" />
                <span className="text-text-muted text-sm animate-pulse">Waiting for output...</span>
              </motion.div>
            )}
            
            <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}