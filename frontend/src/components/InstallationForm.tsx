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
  // Profile variables
  fic_home: string
  java_home: string
  java_bin: string
  oracle_sid: string

  // OFS_BD_SCHEMA_IN.xml inputs
  schema_jdbc_host: string
  schema_jdbc_port: string
  schema_jdbc_service: string
  schema_host: string
  schema_setup_env: string
  schema_apply_same_for_all: string
  schema_default_password: string
  schema_datafile_dir: string
  schema_tablespace_autoextend: string
  schema_external_directory_value: string
  schema_config_schema_name: string
  schema_atomic_schema_name: string
}

export function InstallationForm() {
  const router = useRouter()
  const [formData, setFormData] = useState<InstallationData>({
    host: '',
    username: '',
    password: '',
    // Profile variables with defaults
    fic_home: '/u01/OFSAA/FICHOME',
    java_home: '', // Will be auto-detected if empty
    java_bin: '', // Will be auto-detected if empty
    oracle_sid: 'ORCL',

    schema_jdbc_host: '',
    schema_jdbc_port: '1521',
    schema_jdbc_service: '',
    schema_host: '',
    schema_setup_env: 'DEV',
    schema_apply_same_for_all: 'Y',
    schema_default_password: '',
    schema_datafile_dir: '/u01/app/oracle/oradata/OFSAA/OFSAADB',
    schema_tablespace_autoextend: 'OFF',
    schema_external_directory_value: '/u01/OFSAA/FICHOME/bdf/inbox',
    schema_config_schema_name: 'OFSCONFIG',
    schema_atomic_schema_name: 'OFSATOMIC'
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
          password: formData.password,
          fic_home: formData.fic_home,
          java_home: formData.java_home || null,
          java_bin: formData.java_bin || null,
          oracle_sid: formData.oracle_sid,

          schema_jdbc_host: formData.schema_jdbc_host || null,
          schema_jdbc_port: formData.schema_jdbc_port ? Number(formData.schema_jdbc_port) : null,
          schema_jdbc_service: formData.schema_jdbc_service || null,
          schema_host: formData.schema_host || null,
          schema_setup_env: formData.schema_setup_env || null,
          schema_apply_same_for_all: formData.schema_apply_same_for_all || null,
          schema_default_password: formData.schema_default_password || null,
          schema_datafile_dir: formData.schema_datafile_dir || null,
          schema_tablespace_autoextend: formData.schema_tablespace_autoextend || null,
          schema_external_directory_value: formData.schema_external_directory_value || null,
          schema_config_schema_name: formData.schema_config_schema_name || null,
          schema_atomic_schema_name: formData.schema_atomic_schema_name || null
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

        {/* Profile Variables Section */}
        <motion.div 
          className="border-t border-border pt-6 space-y-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
        >
          <div className="text-sm font-bold text-text-primary uppercase tracking-wider mb-4">
            📋 Profile Configuration
          </div>

          {/* FIC_HOME Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              FIC_HOME Path
            </label>
            <input
              type="text"
              value={formData.fic_home}
              onChange={handleInputChange('fic_home')}
              placeholder="/u01/OFSAA/FICHOME"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
          </div>

          {/* JAVA_HOME Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              JAVA_HOME (Optional - Auto-detected if empty)
            </label>
            <input
              type="text"
              value={formData.java_home}
              onChange={handleInputChange('java_home')}
              placeholder="Leave empty for auto-detection"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          {/* JAVA_BIN Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              JAVA_BIN (Optional - Auto-detected if empty)
            </label>
            <input
              type="text"
              value={formData.java_bin}
              onChange={handleInputChange('java_bin')}
              placeholder="Leave empty for auto-detection"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          {/* ORACLE_SID Field */}
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              Oracle SID
            </label>
            <input
              type="text"
              value={formData.oracle_sid}
              onChange={handleInputChange('oracle_sid')}
              placeholder="ORCL"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              required
            />
          </div>
        </motion.div>

        {/* Schema Config Section */}
        <motion.div
          className="border-t border-border pt-6 space-y-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.45 }}
        >
          <div className="text-sm font-bold text-text-primary uppercase tracking-wider mb-4">
            Schema Creator (OFS_BD_SCHEMA_IN.xml)
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              JDBC Host (DB)
            </label>
            <input
              type="text"
              value={formData.schema_jdbc_host}
              onChange={handleInputChange('schema_jdbc_host')}
              placeholder="192.168.3.42"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                JDBC Port
              </label>
              <input
                type="text"
                value={formData.schema_jdbc_port}
                onChange={handleInputChange('schema_jdbc_port')}
                placeholder="1521"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                JDBC Service/SID
              </label>
              <input
                type="text"
                value={formData.schema_jdbc_service}
                onChange={handleInputChange('schema_jdbc_service')}
                placeholder="OFSAAPDB"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              HOST Tag Value
            </label>
            <input
              type="text"
              value={formData.schema_host}
              onChange={handleInputChange('schema_host')}
              placeholder="192.168.3.41"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SETUPINFO Name
              </label>
              <input
                type="text"
                value={formData.schema_setup_env}
                onChange={handleInputChange('schema_setup_env')}
                placeholder="DEV"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ApplySameForAll (Y/N)
              </label>
              <input
                type="text"
                value={formData.schema_apply_same_for_all}
                onChange={handleInputChange('schema_apply_same_for_all')}
                placeholder="Y"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              Default Schema Password
            </label>
            <input
              type="password"
              value={formData.schema_default_password}
              onChange={handleInputChange('schema_default_password')}
              placeholder="Password1"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                DATAFILE Base Dir
              </label>
              <input
                type="text"
                value={formData.schema_datafile_dir}
                onChange={handleInputChange('schema_datafile_dir')}
                placeholder="/u01/app/oracle/oradata/OFSAA/OFSAADB"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                AUTOEXTEND (ON/OFF)
              </label>
              <input
                type="text"
                value={formData.schema_tablespace_autoextend}
                onChange={handleInputChange('schema_tablespace_autoextend')}
                placeholder="OFF"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              External Directory Value
            </label>
            <input
              type="text"
              value={formData.schema_external_directory_value}
              onChange={handleInputChange('schema_external_directory_value')}
              placeholder="/u01/OFSAA/FICHOME/bdf/inbox"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                CONFIG Schema Name
              </label>
              <input
                type="text"
                value={formData.schema_config_schema_name}
                onChange={handleInputChange('schema_config_schema_name')}
                placeholder="OFSCONFIG"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ATOMIC Schema Name
              </label>
              <input
                type="text"
                value={formData.schema_atomic_schema_name}
                onChange={handleInputChange('schema_atomic_schema_name')}
                placeholder="OFSATOMIC"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>
        </motion.div>

        {/* Submit Button */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
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
