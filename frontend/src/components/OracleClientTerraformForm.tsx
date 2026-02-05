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
  ArrowPathIcon,
  CloudIcon
} from '@heroicons/react/24/outline'

interface OracleClientTerraformData {
  host: string
  username: string
  password: string
  target_host_ip: string
}

export function OracleClientTerraformForm() {
  const router = useRouter()
  const [formData, setFormData] = useState<OracleClientTerraformData>({
    host: '',
    username: '',
    password: '',
    target_host_ip: ''
  })
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setIsLoading(true)
    
    try {
      // Call backend API to start Oracle client terraform installation
      const response = await fetch('http://localhost:8000/api/installation/oracle-client-terraform', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          host: formData.host,
          username: formData.username,
          password: formData.password,
          target_host_ip: formData.target_host_ip
        })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result = await response.json()
      console.log('Oracle Client Terraform installation started:', result)
      
      // Navigate to logs page to track installation progress
      router.push(`/logs/${result.task_id}`)
      
    } catch (error) {
      console.error('Oracle Client Terraform installation failed:', error)
      setStatus('error')
      setIsLoading(false)
      
      setTimeout(() => {
        setStatus('idle')
      }, 5000)
    }
  }

  const handleInputChange = (field: keyof OracleClientTerraformData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    setFormData(prev => ({ ...prev, [field]: e.target.value }))
  }

  const getButtonText = () => {
    if (isLoading) return 'Deploying Oracle Client...'
    if (status === 'success') return 'Deployment Complete'
    if (status === 'error') return 'Deployment Failed'
    return 'Deploy Oracle Client with Terraform'
  }

  const getButtonIcon = () => {
    if (isLoading) return <ArrowPathIcon className="w-4 h-4 animate-spin" />
    if (status === 'success') return <CheckCircleIcon className="w-4 h-4" />
    if (status === 'error') return <ExclamationCircleIcon className="w-4 h-4" />
    return <CloudIcon className="w-4 h-4" />
  }

  const getButtonClass = () => {
    return clsx(
      "w-full px-6 py-4 rounded-lg font-medium transition-all duration-200",
      "flex items-center justify-center gap-2",
      "text-sm uppercase tracking-wider",
      "disabled:cursor-not-allowed",
      {
        'bg-gradient-to-r from-blue-500 to-blue-600 hover:from-blue-600 hover:to-blue-700 text-white shadow-lg hover:shadow-xl transform hover:scale-105 disabled:hover:scale-100 disabled:hover:shadow-lg': status === 'idle',
        'bg-green-500 text-white': status === 'success',
        'bg-red-500 text-white': status === 'error',
        'bg-blue-500 text-white cursor-wait': isLoading,
      }
    )
  }

  return (
    <div className="w-full max-w-md mx-auto">
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4 }}
          className="text-center space-y-2 mb-8"
        >
          <div className="inline-flex items-center justify-center w-12 h-12 bg-blue-500/20 rounded-xl mb-3">
            <CloudIcon className="w-6 h-6 text-blue-400" />
          </div>
          <h2 className="text-xl font-bold text-text-primary">Oracle Client Terraform</h2>
          <p className="text-sm text-text-muted">Deploy Oracle Client using Infrastructure as Code</p>
        </motion.div>

        {/* Form Fields */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
          className="space-y-4"
        >
          {/* Control Server Host Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider flex items-center gap-2">
              <ServerIcon className="w-3 h-3" />
              Control Server Host
            </label>
            <input
              type="text"
              value={formData.host}
              onChange={handleInputChange('host')}
              placeholder="192.168.1.100"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
            <p className="text-xs text-text-muted">Server where Terraform will run</p>
          </div>

          {/* Username Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider flex items-center gap-2">
              <UserIcon className="w-3 h-3" />
              Username
            </label>
            <input
              type="text"
              value={formData.username}
              onChange={handleInputChange('username')}
              placeholder="root"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
          </div>

          {/* Password Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider flex items-center gap-2">
              <KeyIcon className="w-3 h-3" />
              Password
            </label>
            <input
              type="password"
              value={formData.password}
              onChange={handleInputChange('password')}
              placeholder="••••••••••••"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
          </div>

          {/* Target Host IP Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider flex items-center gap-2">
              <ServerIcon className="w-3 h-3" />
              Target Host IP
            </label>
            <input
              type="text"
              value={formData.target_host_ip}
              onChange={handleInputChange('target_host_ip')}
              placeholder="192.168.1.101"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
            <p className="text-xs text-text-muted">IP where Oracle Client will be installed</p>
          </div>
        </motion.div>

        {/* Installation Info */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
          className="bg-blue-500/5 border border-blue-500/20 rounded-lg p-4"
        >
          <h4 className="text-sm font-semibold text-blue-400 mb-2">Terraform Deployment</h4>
          <ul className="text-xs text-text-muted space-y-1">
            <li>• Clones Oracle client terraform repository</li>
            <li>• Updates terraform.tfvars with target host IP</li>
            <li>• Executes terraform apply --auto-approve</li>
            <li>• Deploys Oracle 19c client to target host</li>
          </ul>
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