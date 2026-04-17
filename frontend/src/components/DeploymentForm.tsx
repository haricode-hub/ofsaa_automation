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
  ArrowPathIcon,
  CircleStackIcon,
  CubeIcon
} from '@heroicons/react/24/outline'

// ─── Types ────────────────────────────────────────────────────────

export interface DatasourceEntry {
  ds_name: string
  jndi_name: string
  db_url: string
  db_user: string
  db_password: string
  targets: string
}

export interface DeploymentFormData {
  // Shared SSH connection
  host: string
  username: string
  password: string

  // EAR Creation & Exploding fields
  ear_enabled: boolean
  db_sys_password: string
  db_jdbc_host: string
  db_jdbc_port: string
  db_jdbc_service: string
  config_schema_name: string
  atomic_schema_name: string
  schema_password: string
  weblogic_domain_home: string

  // Datasource creation fields
  ds_enabled: boolean
  admin_url: string
  weblogic_username: string
  weblogic_password: string
  datasources: DatasourceEntry[]

  // App deployment to WebLogic (STEP 5)
  deploy_app_enabled: boolean
  deploy_app_path: string
  deploy_app_target_server: string
}

const DEFAULT_DATASOURCES: DatasourceEntry[] = [
  {
    ds_name: 'ANALYST',
    jndi_name: 'jdbc/ANALYST',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSATOMIC',
    db_password: '',
    targets: 'AdminServer, OFSAA_MS1'
  },
  {
    ds_name: 'FCCMINFO',
    jndi_name: 'jdbc/FCCMINFO',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSATOMIC',
    db_password: '',
    targets: 'OFSAA_MS1'
  },
  {
    ds_name: 'FCCMINFOCNF',
    jndi_name: 'jdbc/FCCMINFOCNF',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSCONFIG',
    db_password: '',
    targets: 'AdminServer, OFSAA_MS1'
  },
  {
    ds_name: 'FICMASTER',
    jndi_name: 'jdbc/FICMASTER',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSCONFIG',
    db_password: '',
    targets: 'OFSAA_MS1'
  },
  {
    ds_name: 'MINER',
    jndi_name: 'jdbc/MINER',
    db_url: 'jdbc:oracle:thin:@//localhost:1521/FLEXPDB1',
    db_user: 'OFSATOMIC',
    db_password: '',
    targets: 'AdminServer, OFSAA_MS1'
  }
]

const DEPLOY_FORM_STORAGE_KEY = 'ofsaa_deployment_form_v1'

// ─── Component ────────────────────────────────────────────────────

export function DeploymentForm() {
  const router = useRouter()

  const [formData, setFormData] = useState<DeploymentFormData>(() => {
    if (typeof window !== 'undefined') {
      try {
        const saved = localStorage.getItem(DEPLOY_FORM_STORAGE_KEY)
        if (saved) return JSON.parse(saved)
      } catch { /* ignore */ }
    }
    return {
      host: '',
      username: 'root',
      password: '',
      // EAR
      ear_enabled: true,
      db_sys_password: '',
      db_jdbc_host: '',
      db_jdbc_port: '1521',
      db_jdbc_service: 'FLEXPDB1',
      config_schema_name: 'OFSCONFIG',
      atomic_schema_name: 'OFSATOMIC',
      schema_password: '',
      weblogic_domain_home: '/u01/Oracle/user_projects/domains/ofsaa_domain',
      // Datasources
      ds_enabled: true,
      admin_url: 't3://localhost:7001',
      weblogic_username: 'weblogic',
      weblogic_password: '',
      datasources: DEFAULT_DATASOURCES.map(ds => ({ ...ds })),
      // App deployment
      deploy_app_enabled: true,
      deploy_app_path: '/u01/Oracle/user_projects/domains/ofsaa_domain/applications/FICHOME.ear',
      deploy_app_target_server: 'MS1'
    }
  })

  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [errorMsg, setErrorMsg] = useState('')

  const updateForm = (next: DeploymentFormData) => {
    setFormData(next)
    try { localStorage.setItem(DEPLOY_FORM_STORAGE_KEY, JSON.stringify(next)) } catch { /* ignore */ }
  }

  const handleFieldChange = (field: keyof DeploymentFormData, value: string | boolean) => {
    const next = { ...formData, [field]: value }

    // Auto-populate: when db_jdbc_service or db_jdbc_host changes, rebuild all datasource db_urls
    if (field === 'db_jdbc_service' || field === 'db_jdbc_host' || field === 'db_jdbc_port') {
      const host = field === 'db_jdbc_host' ? (value as string) : next.db_jdbc_host || next.host
      const port = field === 'db_jdbc_port' ? (value as string) : next.db_jdbc_port
      const svc  = field === 'db_jdbc_service' ? (value as string) : next.db_jdbc_service
      if (host && svc) {
        next.datasources = next.datasources.map(ds => ({
          ...ds,
          db_url: `jdbc:oracle:thin:@//${host}:${port || '1521'}/${svc}`
        }))
      }
    }

    // Auto-populate: when host changes and db_jdbc_host is empty, update datasource urls too
    if (field === 'host' && !next.db_jdbc_host && next.db_jdbc_service) {
      next.datasources = next.datasources.map(ds => ({
        ...ds,
        db_url: `jdbc:oracle:thin:@//${value as string}:${next.db_jdbc_port || '1521'}/${next.db_jdbc_service}`
      }))
    }

    // Auto-populate: when schema names change, update datasource db_user fields
    if (field === 'atomic_schema_name' || field === 'config_schema_name') {
      const oldAtomic = formData.atomic_schema_name
      const oldConfig = formData.config_schema_name
      const newAtomic = field === 'atomic_schema_name' ? (value as string) : next.atomic_schema_name
      const newConfig = field === 'config_schema_name' ? (value as string) : next.config_schema_name
      next.datasources = next.datasources.map(ds => {
        if (ds.db_user === oldAtomic || ds.db_user === 'OFSATOMIC') {
          return { ...ds, db_user: newAtomic }
        }
        if (ds.db_user === oldConfig || ds.db_user === 'OFSCONFIG') {
          return { ...ds, db_user: newConfig }
        }
        return ds
      })
    }

    // Auto-populate: when schema_password changes, fill ALL datasource db_password fields
    if (field === 'schema_password' && value) {
      next.datasources = next.datasources.map(ds => ({ ...ds, db_password: value as string }))
    }

    // Auto-populate app path when domain home changes
    if (field === 'weblogic_domain_home') {
      const newPath = `${value as string}/applications/FICHOME.ear`
      next.deploy_app_path = newPath
    }

    updateForm(next)
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
    let updated = formData.datasources.map((ds, i) => i === idx ? { ...ds, [field]: value } : ds)

    // Auto-populate: when any db_password changes, set same password on all datasources that have empty password
    if (field === 'db_password' && value) {
      updated = updated.map(ds => ds.db_password ? ds : { ...ds, db_password: value })
    }

    // Auto-populate: when any db_url changes, set same URL on all datasources that still have the old url
    if (field === 'db_url' && value) {
      const oldUrl = formData.datasources[idx].db_url
      if (oldUrl) {
        updated = updated.map(ds => ds.db_url === oldUrl ? { ...ds, db_url: value } : ds)
      }
    }

    updateForm({ ...formData, datasources: updated })
  }

  // ── Submit EAR (+ optional datasources) ──

  const submitEar = async (): Promise<string> => {
    const payload: Record<string, unknown> = {
      host: formData.host,
      username: formData.username,
      password: formData.password,
      db_sys_password: formData.db_sys_password,
      db_jdbc_host: formData.db_jdbc_host || null,
      db_jdbc_port: formData.db_jdbc_port ? Number(formData.db_jdbc_port) : 1521,
      db_jdbc_service: formData.db_jdbc_service,
      config_schema_name: formData.config_schema_name,
      atomic_schema_name: formData.atomic_schema_name,
      weblogic_domain_home: formData.weblogic_domain_home
    }

    // Include datasource config if enabled (runs sequentially after EAR)
    if (formData.ds_enabled) {
      const validDs = formData.datasources.filter(ds => ds.ds_name && ds.jndi_name && ds.db_url && ds.db_user && ds.db_password)
      payload.ds_enabled = true
      payload.admin_url = formData.admin_url
      payload.weblogic_username = formData.weblogic_username
      payload.weblogic_password = formData.weblogic_password
      payload.datasources = validDs.map(ds => ({
        ds_name: ds.ds_name,
        jndi_name: ds.jndi_name,
        db_url: ds.db_url,
        db_user: ds.db_user,
        db_password: ds.db_password,
        targets: ds.targets.split(',').map(t => t.trim()).filter(Boolean)
      }))
    }

    // Include app deployment config if enabled (STEP 5 - runs after checkofsaa)
    if (formData.deploy_app_enabled) {
      payload.deploy_app_enabled = true
      payload.deploy_app_path = formData.deploy_app_path || undefined
      payload.deploy_app_target_server = formData.deploy_app_target_server || undefined
      // Reuse WebLogic creds from DS section (or set them if DS not enabled)
      if (!payload.admin_url) payload.admin_url = formData.admin_url
      if (!payload.weblogic_username) payload.weblogic_username = formData.weblogic_username
      if (!payload.weblogic_password) payload.weblogic_password = formData.weblogic_password
    }

    const response = await fetch(`${getApiUrl()}/api/installation/deploy-fichome`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    })
    if (!response.ok) {
      const err = await response.json().catch(() => ({}))
      throw new Error(err.detail || `EAR deploy HTTP ${response.status}`)
    }
    const result = await response.json()
    return result.task_id
  }

  // ── Combined submit (single task: EAR → Datasources sequentially) ──

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setErrorMsg('')

    if (!formData.ear_enabled && !formData.ds_enabled && !formData.deploy_app_enabled) {
      setStatus('error'); setErrorMsg('Enable at least one section to deploy.'); return
    }
    if (!formData.host || !formData.username || !formData.password) {
      setStatus('error'); setErrorMsg('SSH connection fields are required.'); return
    }
    if (formData.ear_enabled) {
      if (!formData.db_sys_password) { setStatus('error'); setErrorMsg('DB SYS password is required for EAR deployment.'); return }
      if (!formData.db_jdbc_service) { setStatus('error'); setErrorMsg('DB JDBC service is required.'); return }
      if (!formData.weblogic_domain_home) { setStatus('error'); setErrorMsg('WebLogic domain home is required.'); return }
    }
    if (formData.deploy_app_enabled) {
      if (!formData.admin_url || !formData.weblogic_username || !formData.weblogic_password) {
        setStatus('error'); setErrorMsg('WebLogic admin credentials are required for app deployment.'); return
      }
      if (!formData.deploy_app_target_server) { setStatus('error'); setErrorMsg('Target server name is required for app deployment (e.g., MS1).'); return }
    }
    if (formData.ds_enabled) {
      if (!formData.admin_url || !formData.weblogic_username || !formData.weblogic_password) {
        setStatus('error'); setErrorMsg('WebLogic admin credentials are required for datasource creation.'); return
      }

      if (!formData.admin_url.match(/^t3s?:\/\/.+:\d+$/)) {
        setStatus('error'); setErrorMsg('Admin URL must be like t3://host:port (e.g., t3://192.168.0.39:7001)'); return
      }
      const validDs = formData.datasources.filter(ds => ds.ds_name && ds.jndi_name && ds.db_url && ds.db_user && ds.db_password)
      if (validDs.length === 0) { setStatus('error'); setErrorMsg('At least one complete datasource is required.'); return }
    }

    setIsLoading(true)
    try {
      // Single task: EAR runs first, then datasources (if enabled) — all sequential
      const taskId = await submitEar()
      router.push(`/logs/${taskId}`)
    } catch (error) {
      console.error('Deployment failed:', error)
      setStatus('error')
      setErrorMsg(error instanceof Error ? error.message : 'Unknown error')
      setIsLoading(false)
      setTimeout(() => setStatus('idle'), 5000)
    }
  }

  // ── Render helpers ──

  const inputClass = 'w-full rounded-lg border border-border bg-bg-secondary px-3 py-2 text-sm text-text-primary placeholder:text-text-muted focus:border-white focus:outline-none focus:ring-1 focus:ring-white/30 transition'
  const labelClass = 'block text-xs font-semibold text-text-muted uppercase tracking-wider mb-1.5'

  const buttonClass = () => {
    const base = 'w-full flex items-center justify-center gap-2 px-6 py-3 rounded-xl font-bold text-sm uppercase tracking-wider transition-all duration-300'
    if (isLoading) return base + ' bg-bg-tertiary text-text-muted cursor-not-allowed'
    if (status === 'error') return base + ' bg-error text-white hover:bg-error/90'
    return base + ' bg-white text-black hover:bg-gray-200 hover:shadow-lg'
  }

  const buttonLabel = () => {
    if (formData.ear_enabled && formData.ds_enabled) return 'EAR + Datasources'
    if (formData.ear_enabled) return 'EAR'
    if (formData.ds_enabled) return 'Datasources'
    return ''
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-6">

        {/* ── SSH Connection (shared) ── */}
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
                <div className="text-xs text-text-muted mt-1">SSH credentials for the target app server (shared by both sections)</div>
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

        {/* ══════════════════════════════════════════════════════════════ */}
        {/* ── SECTION 1: EAR Creation & Exploding ── */}
        {/* ══════════════════════════════════════════════════════════════ */}
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.1 }}
        >
          <details open className="group">
            <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.ear_enabled}
                  onChange={e => { e.stopPropagation(); handleFieldChange('ear_enabled', !formData.ear_enabled) }}
                  className="accent-white h-4 w-4"
                />
                <div>
                  <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
                    <CubeIcon className="inline h-4 w-4 mr-1 -mt-0.5" />
                    EAR Creation & Exploding
                  </div>
                  <div className="text-xs text-text-muted mt-1">Build FICHOME EAR/WAR and deploy to WebLogic domain</div>
                </div>
              </div>
              <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
              <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
            </summary>

            {formData.ear_enabled && (
              <div className="mt-5 space-y-4">
                {/* Database config */}
                <div className="text-xs font-bold text-text-muted uppercase tracking-wider">Database</div>
                <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-3">
                  <div>
                    <label className={labelClass}>SYS Password</label>
                    <input className={inputClass} type="password" value={formData.db_sys_password} onChange={e => handleFieldChange('db_sys_password', e.target.value)} placeholder="••••••" />
                  </div>
                  <div>
                    <label className={labelClass}>DB Host (optional)</label>
                    <input className={inputClass} value={formData.db_jdbc_host} onChange={e => handleFieldChange('db_jdbc_host', e.target.value)} placeholder="Same as app server" />
                  </div>
                  <div>
                    <label className={labelClass}>DB Port</label>
                    <input className={inputClass} value={formData.db_jdbc_port} onChange={e => handleFieldChange('db_jdbc_port', e.target.value)} placeholder="1521" />
                  </div>
                  <div>
                    <label className={labelClass}>JDBC Service</label>
                    <input className={inputClass} value={formData.db_jdbc_service} onChange={e => handleFieldChange('db_jdbc_service', e.target.value)} placeholder="FLEXPDB1" />
                  </div>
                </div>

                {/* Schema config */}
                <div className="text-xs font-bold text-text-muted uppercase tracking-wider mt-2">Schema</div>
                <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                  <div>
                    <label className={labelClass}>Config Schema Name</label>
                    <input className={inputClass} value={formData.config_schema_name} onChange={e => handleFieldChange('config_schema_name', e.target.value)} placeholder="OFSCONFIG" />
                  </div>
                  <div>
                    <label className={labelClass}>Atomic Schema Name</label>
                    <input className={inputClass} value={formData.atomic_schema_name} onChange={e => handleFieldChange('atomic_schema_name', e.target.value)} placeholder="OFSATOMIC" />
                  </div>
                  <div>
                    <label className={labelClass}>Schema Password</label>
                    <input className={inputClass} type="password" value={formData.schema_password} onChange={e => handleFieldChange('schema_password', e.target.value)} placeholder="BD Pack default password" />
                  </div>
                </div>

                {/* WebLogic domain */}
                <div className="text-xs font-bold text-text-muted uppercase tracking-wider mt-2">WebLogic</div>
                <div>
                  <label className={labelClass}>Domain Home</label>
                  <input className={inputClass} value={formData.weblogic_domain_home} onChange={e => handleFieldChange('weblogic_domain_home', e.target.value)} placeholder="/u01/Oracle/user_projects/domains/ofsaa_domain" />
                </div>
              </div>
            )}
          </details>
        </motion.div>

        {/* ══════════════════════════════════════════════════════════════ */}
        {/* ── SECTION 2: WebLogic Application Deployment ── */}
        {/* ══════════════════════════════════════════════════════════════ */}
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.12 }}
        >
          <details open className="group">
            <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.deploy_app_enabled}
                  onChange={e => { e.stopPropagation(); handleFieldChange('deploy_app_enabled', !formData.deploy_app_enabled) }}
                  className="accent-white h-4 w-4"
                />
                <div>
                  <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
                    <RocketLaunchIcon className="inline h-4 w-4 mr-1 -mt-0.5" />
                    WebLogic App Deployment
                  </div>
                  <div className="text-xs text-text-muted mt-1">Deploy FICHOME.ear to WebLogic via WLST (runs after checkofsaa)</div>
                </div>
              </div>
              <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
              <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
            </summary>

            {formData.deploy_app_enabled && (
              <div className="mt-5 space-y-3">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}>App Path</label>
                    <input className={inputClass} value={formData.deploy_app_path} onChange={e => handleFieldChange('deploy_app_path', e.target.value)} placeholder="/u01/Oracle/user_projects/domains/ofsaa_domain/applications/FICHOME.ear" />
                  </div>
                  <div>
                    <label className={labelClass}>Target Server</label>
                    <input className={inputClass} value={formData.deploy_app_target_server} onChange={e => handleFieldChange('deploy_app_target_server', e.target.value)} placeholder="MS1" />
                  </div>
                </div>
              </div>
            )}
          </details>
        </motion.div>

        {/* ══════════════════════════════════════════════════════════════ */}
        {/* ── SECTION 3: WebLogic Datasource Creation ── */}
        {/* ══════════════════════════════════════════════════════════════ */}
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.3, delay: 0.15 }}
        >
          <details open className="group">
            <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
              <div className="flex items-center gap-3">
                <input
                  type="checkbox"
                  checked={formData.ds_enabled}
                  onChange={e => { e.stopPropagation(); handleFieldChange('ds_enabled', !formData.ds_enabled) }}
                  className="accent-white h-4 w-4"
                />
                <div>
                  <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
                    <CircleStackIcon className="inline h-4 w-4 mr-1 -mt-0.5" />
                    WebLogic Datasource Creation
                  </div>
                  <div className="text-xs text-text-muted mt-1">Create JDBC datasources via WLST ({formData.datasources.length} configured)</div>
                </div>
              </div>
              <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
              <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
            </summary>

            {formData.ds_enabled && (
              <div className="mt-5 space-y-5">
                {/* WebLogic Admin */}
                <div className="text-xs font-bold text-text-muted uppercase tracking-wider">WebLogic Admin</div>
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                  <div>
                    <label className={labelClass}>Admin URL</label>
                    <input className={inputClass} value={formData.admin_url} onChange={e => handleFieldChange('admin_url', e.target.value)} placeholder="t3://localhost:7001" />
                  </div>
                  <div>
                    <label className={labelClass}>WebLogic Username</label>
                    <input className={inputClass} value={formData.weblogic_username} onChange={e => handleFieldChange('weblogic_username', e.target.value)} placeholder="weblogic" />
                  </div>
                  <div>
                    <label className={labelClass}>WebLogic Password</label>
                    <input className={inputClass} type="password" value={formData.weblogic_password} onChange={e => handleFieldChange('weblogic_password', e.target.value)} placeholder="••••••" />
                  </div>
                </div>

                {/* Datasource rows */}
                <div className="text-xs font-bold text-text-muted uppercase tracking-wider mt-2">Datasources</div>
                {formData.datasources.map((ds, idx) => (
                  <div key={idx} className="rounded-lg border border-border/60 bg-bg-primary/30 p-4 space-y-3">
                    <div className="flex items-center justify-between">
                      <span className="text-xs font-bold text-text-secondary uppercase tracking-wider">
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
                  className="flex items-center gap-2 text-xs font-semibold text-text-secondary hover:text-text-primary transition uppercase tracking-wider"
                >
                  <PlusIcon className="h-4 w-4" />
                  Add Datasource
                </button>
              </div>
            )}
          </details>
        </motion.div>

        {/* Error */}
        {errorMsg && (
          <p className="text-xs text-error flex items-center gap-1">
            <ExclamationCircleIcon className="h-4 w-4" />
            {errorMsg}
          </p>
        )}

        {/* ── Submit Button ── */}
        <motion.div
          initial={{ opacity: 0, y: 10 }} animate={{ opacity: 1, y: 0 }} transition={{ duration: 0.4, delay: 0.25 }}
        >
          {(formData.ear_enabled || formData.ds_enabled) ? (
            <button
              type="submit"
              disabled={isLoading}
              className={buttonClass()}
            >
              {isLoading ? (
                <><ArrowPathIcon className="h-5 w-5 animate-spin" /><span>Deploying...</span></>
              ) : (
                <><RocketLaunchIcon className="h-5 w-5" /><span>Start Deployment — {buttonLabel()}</span></>
              )}
            </button>
          ) : (
            <div className="text-center text-xs text-text-muted py-3">
              Enable at least one section above to deploy.
            </div>
          )}
        </motion.div>
      </form>
    </div>
  )
}
