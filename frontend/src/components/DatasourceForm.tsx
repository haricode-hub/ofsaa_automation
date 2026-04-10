'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { getApiUrl } from '@/lib/api'
import {
  ServerIcon,
  PlusIcon,
  TrashIcon,
  RocketLaunchIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'

// ─── Types ────────────────────────────────────────────────────────

export interface DatasourceEntry {
  ds_name: string
  jndi_name: string
  db_url: string
  db_user: string
  db_password: string
  targets: string  // comma-separated, split on submit
}

export interface DatasourceFormData {
  host: string
  username: string
  password: string
  admin_url: string
  weblogic_username: string
  weblogic_password: string
  datasources: DatasourceEntry[]
}

const DEFAULT_DATASOURCES: DatasourceEntry[] = [
  {
    ds_name: 'jdbc/ABORACLECLOUD',
    jndi_name: 'jdbc/ABORACLECLOUD',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSATOMIC',
    db_password: '',
    targets: 'AdminServer'
  },
  {
    ds_name: 'jdbc/ABORACLEREF',
    jndi_name: 'jdbc/ABOLRACLEREF',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSATOMIC',
    db_password: '',
    targets: 'AdminServer'
  },
  {
    ds_name: 'jdbc/CONFREF',
    jndi_name: 'jdbc/CONFREF',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSCONFIG',
    db_password: '',
    targets: 'AdminServer'
  },
  {
    ds_name: 'jdbc/FICABORACLECONF',
    jndi_name: 'jdbc/FICABORACLECONF',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSCONFIG',
    db_password: '',
    targets: 'AdminServer'
  },
  {
    ds_name: 'jdbc/FICMASTER',
    jndi_name: 'jdbc/FICMASTER',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSCONFIG',
    db_password: '',
    targets: 'AdminServer'
  }
]

const DS_FORM_STORAGE_KEY = 'ofsaa_datasource_form_v1'

// ─── Component ────────────────────────────────────────────────────

export function DatasourceForm() {
  const router = useRouter()

  const [formData, setFormData] = useState<DatasourceFormData>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(DS_FORM_STORAGE_KEY)
        if (saved) return JSON.parse(saved)
      } catch { /* ignore */ }
    }
    return {
      host: '',
      username: 'root',
      password: '',
      admin_url: 't3://localhost:7001',
      weblogic_username: 'weblogic',
      weblogic_password: '',
      datasources: DEFAULT_DATASOURCES.map(ds => ({ ...ds }))
    }
  })

  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  // Persist to localStorage on every change
  const updateForm = (next: DatasourceFormData) => {
    setFormData(next)
    try { localStorage.setItem(DS_FORM_STORAGE_KEY, JSON.stringify(next)) } catch { /* ignore */ }
  }

  const handleFieldChange = (field: keyof Omit<DatasourceFormData, 'datasources'>, value: string) => {
    updateForm({ ...formData, [field]: value })
  }

  // ── Datasource row helpers ──

  const addDatasource = () => {
    updateForm({ ...formData, datasources: [...formData.datasources, { ds_name: '', jndi_name: '', db_url: '', db_user: '', db_password: '', targets: '' }] })
  }

  const removeDatasource = (idx: number) => {
    if (formData.datasources.length <= 1) return
    updateForm({ ...formData, datasources: formData.datasources.filter((_, i) => i !== idx) })
  }

  const updateDatasource = (idx: number, field: keyof DatasourceEntry, value: string) => {
    const updated = formData.datasources.map((ds, i) => i === idx ? { ...ds, [field]: value } : ds)
    updateForm({ ...formData, datasources: updated })
  }

  // ── Submit ──

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg('')

    // Basic validation
    if (!formData.host || !formData.username || !formData.password) {
      setStatus('error'); setErrorMsg('SSH connection fields are required.'); return
    }
    if (!formData.admin_url || !formData.weblogic_username || !formData.weblogic_password) {
      setStatus('error'); setErrorMsg('WebLogic admin credentials are required.'); return
    }
    const validDs = formData.datasources.filter(ds => ds.ds_name && ds.jndi_name && ds.db_url && ds.db_user && ds.db_password)
    if (validDs.length === 0) {
      setStatus('error'); setErrorMsg('At least one complete datasource is required.'); return
    }

    setIsLoading(true)
    try {
      const response = await fetch(`${getApiUrl()}/api/installation/create-datasources`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          host: formData.host,
          username: formData.username,
          password: formData.password,
          admin_url: formData.admin_url,
          weblogic_username: formData.weblogic_username,
          weblogic_password: formData.weblogic_password,
          datasources: validDs.map(ds => ({
            ds_name: ds.ds_name,
            jndi_name: ds.jndi_name,
            db_url: ds.db_url,
            db_user: ds.db_user,
            db_password: ds.db_password,
            targets: ds.targets.split(',').map(t => t.trim()).filter(Boolean)
          }))
        })
      })

      if (!response.ok) {
        const err = await response.json().catch(() => ({}))
        throw new Error(err.detail || `HTTP ${response.status}`)
      }

      const result = await response.json()
      router.push(`/logs/${result.task_id}`)
    } catch (error) {
      console.error('Datasource creation failed:', error)
      setStatus('error')
      setErrorMsg(error instanceof Error ? error.message : 'Unknown error')
      setIsLoading(false)
      setTimeout(() => setStatus('idle'), 5000)
    }
  }

  // ── Render helpers ──

  const inputClass = 'w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-white focus:outline-none focus:ring-1 focus:ring-white/30 transition'
  const labelClass = 'block text-xs font-semibold text-text-muted uppercase tracking-wider mb-1.5'

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-6">

        {/* ── SSH Connection ── */}
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3 }}
        >
          <details open className="group">
            <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
                  <ServerIcon className="inline h-4 w-4 mr-1 -mt-0.5" />
                  App Server Connection
                </div>
                <div className="text-xs text-text-muted mt-1">SSH credentials for the target app server</div>
              </div>
              <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
              <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
            </summary>
            <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Host / IP</label>
                <input className={inputClass} value={formData.host} onChange={e => handleFieldChange('host', e.target.value)} placeholder="192.168.1.100" required />
              </div>
              <div>
                <label className={labelClass}>Username</label>
                <input className={inputClass} value={formData.username} onChange={e => handleFieldChange('username', e.target.value)} placeholder="root" required />
              </div>
              <div>
                <label className={labelClass}>Password</label>
                <input className={inputClass} type="password" value={formData.password} onChange={e => handleFieldChange('password', e.target.value)} placeholder="••••••" required />
              </div>
            </div>
          </details>
        </motion.div>

        {/* ── WebLogic Admin ── */}
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.1 }}
        >
          <details open className="group">
            <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-bold text-text-primary uppercase tracking-wider">WebLogic Admin</div>
                <div className="text-xs text-text-muted mt-1">Admin server URL and credentials for WLST connection</div>
              </div>
              <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
              <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
            </summary>
            <div className="mt-5 grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className={labelClass}>Admin URL</label>
                <input className={inputClass} value={formData.admin_url} onChange={e => handleFieldChange('admin_url', e.target.value)} placeholder="t3://localhost:7001" required />
              </div>
              <div>
                <label className={labelClass}>WebLogic Username</label>
                <input className={inputClass} value={formData.weblogic_username} onChange={e => handleFieldChange('weblogic_username', e.target.value)} placeholder="weblogic" required />
              </div>
              <div>
                <label className={labelClass}>WebLogic Password</label>
                <input className={inputClass} type="password" value={formData.weblogic_password} onChange={e => handleFieldChange('weblogic_password', e.target.value)} placeholder="••••••" required />
              </div>
            </div>
          </details>
        </motion.div>

        {/* ── Datasources ── */}
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.2 }}
        >
          <details open className="group">
            <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-bold text-text-primary uppercase tracking-wider">Datasources</div>
                <div className="text-xs text-text-muted mt-1">
                  Define JDBC datasources to create in WebLogic ({formData.datasources.length} configured)
                </div>
              </div>
              <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
              <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
            </summary>
            <div className="mt-5 space-y-5">
              {formData.datasources.map((ds, idx) => (
                <div key={idx} className="rounded-lg border border-border/60 bg-bg-primary/30 p-4 space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-xs font-bold text-accent uppercase tracking-wider">
                      Datasource #{idx + 1}
                    </span>
                    {formData.datasources.length > 1 && (
                      <button
                        type="button"
                        onClick={() => removeDatasource(idx)}
                        className="text-xs text-error hover:text-error/80 flex items-center gap-1 transition"
                      >
                        <TrashIcon className="h-3.5 w-3.5" />
                        Remove
                      </button>
                    )}
                  </div>

                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-3">
                    <div>
                      <label className={labelClass}>Datasource Name</label>
                      <input className={inputClass} value={ds.ds_name} onChange={e => updateDatasource(idx, 'ds_name', e.target.value)} placeholder="OFSAADataSource" />
                    </div>
                    <div>
                      <label className={labelClass}>JNDI Name</label>
                      <input className={inputClass} value={ds.jndi_name} onChange={e => updateDatasource(idx, 'jndi_name', e.target.value)} placeholder="jdbc/OFSAADataSource" />
                    </div>
                    <div>
                      <label className={labelClass}>DB URL</label>
                      <input className={inputClass} value={ds.db_url} onChange={e => updateDatasource(idx, 'db_url', e.target.value)} placeholder="jdbc:oracle:thin:@//host:1521/service" />
                    </div>
                    <div>
                      <label className={labelClass}>DB Username</label>
                      <input className={inputClass} value={ds.db_user} onChange={e => updateDatasource(idx, 'db_user', e.target.value)} placeholder="OFSCONFIG" />
                    </div>
                    <div>
                      <label className={labelClass}>DB Password</label>
                      <input className={inputClass} type="password" value={ds.db_password} onChange={e => updateDatasource(idx, 'db_password', e.target.value)} placeholder="••••••" />
                    </div>
                    <div>
                      <label className={labelClass}>Targets (comma-separated)</label>
                      <input className={inputClass} value={ds.targets} onChange={e => updateDatasource(idx, 'targets', e.target.value)} placeholder="AdminServer, ofsaa_server1" />
                    </div>
                  </div>
                </div>
              ))}

              <button
                type="button"
                onClick={addDatasource}
                className="flex items-center gap-2 text-xs font-semibold text-accent hover:text-accent/80 transition uppercase tracking-wider"
              >
                <PlusIcon className="h-4 w-4" />
                Add Datasource
              </button>
            </div>
          </details>
        </motion.div>

        {/* Error */}
        {errorMsg && (
          <p className="text-xs text-error flex items-center gap-1">
            <ExclamationCircleIcon className="h-4 w-4" />
            {errorMsg}
          </p>
        )}

        {/* Submit */}
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.3 }}
        >
          <button
            type="submit"
            disabled={isLoading}
            className={`w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-bold text-sm uppercase tracking-wider transition-all duration-300 ${
              isLoading
                ? 'bg-bg-tertiary text-text-muted cursor-not-allowed'
                : status === 'success'
                ? 'bg-success text-black'
                : status === 'error'
                ? 'bg-error text-white hover:bg-error/90'
                : 'bg-white text-black hover:bg-gray-200 hover:shadow-lg'
            }`}
          >
            {isLoading ? (
              <><ArrowPathIcon className="h-5 w-5 animate-spin" /><span>Creating Datasources...</span></>
            ) : status === 'success' ? (
              <><CheckCircleIcon className="h-5 w-5" /><span>Datasources Created</span></>
            ) : status === 'error' ? (
              <><ExclamationCircleIcon className="h-5 w-5" /><span>Retry Datasource Creation</span></>
            ) : (
              <><RocketLaunchIcon className="h-5 w-5" /><span>Create Datasources</span></>
            )}
          </button>
        </motion.div>
      </form>
    </div>
  )
}
