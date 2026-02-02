'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import {
  ServerIcon,
  UserIcon,
  KeyIcon,
  RocketLaunchIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'

interface InstallationData {
  host: string
  username: string
  password: string
}

export function InstallationForm() {
  const router = useRouter()
  const [formData, setFormData] = useState<InstallationData>({
    host: '',
    username: '',
    password: ''
  })
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    
    try {
      // Call backend API to start installation
      const response = await fetch('http://localhost:8000/api/installation/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          host: formData.host,
          username: formData.username,
          password: formData.password
        })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result = await response.json()
      console.log('Installation started:', result)
      
      // Navigate to logs page instead of showing inline logs
      router.push(`/logs/${result.task_id}`)
      
    } catch (error) {
      console.error('Installation failed:', error)
      setStatus('error')
      setIsLoading(false)
      
      setTimeout(() => {
        setStatus('idle')
      }, 5000)
    }
  }

  const handleInputChange = (field: keyof InstallationData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData(prev => ({ ...prev, [field]: e.target.value }))
  }

  const getButtonText = () => {
    if (isLoading) return 'Initializing...'
    if (status === 'success') return 'Installation Complete'
    if (status === 'error') return 'Connection Failed'
    return 'Deploy Installation'
  }

  const getButtonIcon = () => {
    if (isLoading) return <ArrowPathIcon className="w-4 h-4 animate-spin" />
    if (status === 'success') return <CheckCircleIcon className="w-4 h-4" />
    if (status === 'error') return <ExclamationCircleIcon className="w-4 h-4" />
    return <RocketLaunchIcon className="w-4 h-4" />
  }

  const getButtonClass = () => {
    const baseClass = "w-full relative overflow-hidden rounded-lg px-6 py-4 font-bold text-sm tracking-wide transition-all duration-300 disabled:cursor-not-allowed flex items-center justify-center gap-3"
    
    if (status === 'success') {
      return baseClass + ' bg-success text-black'
    }
    if (status === 'error') {
      return baseClass + ' bg-error text-white'
    }
    if (isLoading) {
      return baseClass + ' bg-bg-tertiary text-text-muted cursor-wait'
    }
    
    return baseClass + ' bg-white text-black hover:bg-gray-200 active:scale-98'
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Host Field */}
        <motion.div 
          className="space-y-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
            <ServerIcon className="w-4 h-4" />
            Target Host
          </label>
          <input
            type="text"
            value={formData.host}
            onChange={handleInputChange('host')}
            placeholder="192.168.1.100"
            className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            required
          />
        </motion.div>

        {/* Username Field */}
        <motion.div 
          className="space-y-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
          <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
            <UserIcon className="w-4 h-4" />
            SSH Username
          </label>
          <input
            type="text"
            value={formData.username}
            onChange={handleInputChange('username')}
            placeholder="oracle"
            className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            required
          />
        </motion.div>

        {/* Password Field */}
        <motion.div 
          className="space-y-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
            <KeyIcon className="w-4 h-4" />
            SSH Password
          </label>
          <input
            type="password"
            value={formData.password}
            onChange={handleInputChange('password')}
            placeholder="••••••••••••"
            className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            required
          />
        </motion.div>

        {/* Submit Button */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
        >
          <button
            type="submit"
            disabled={isLoading}
            className={getButtonClass()}
          >
            {getButtonIcon()}
            <span>{getButtonText()}</span>
          </button>
        </motion.div>
      </form>
    </div>
  )
}