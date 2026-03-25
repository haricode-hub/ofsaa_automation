'use client'

import { ChangeEvent } from 'react'

export interface FichomeDeploymentFormData {
  fichome_enable_deployment: boolean
  fichome_weblogic_host: string
  fichome_weblogic_port: string
  fichome_ant_timeout_minutes: number
}

interface FichomeDeploymentFormProps {
  data: FichomeDeploymentFormData
  onChange: (updates: Partial<FichomeDeploymentFormData>) => void
}

export function FichomeDeploymentForm({ data, onChange }: FichomeDeploymentFormProps) {
  const handleChange = (field: keyof FichomeDeploymentFormData, value: any) => {
    onChange({ [field]: value })
  }

  const handleInputChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target
    const field = name as keyof FichomeDeploymentFormData
    const finalValue = field === 'fichome_ant_timeout_minutes' ? parseInt(value) || 20 : value
    handleChange(field, finalValue)
  }

  const handleCheckboxChange = (e: ChangeEvent<HTMLInputElement>) => {
    const { name, checked } = e.target
    handleChange(name as keyof FichomeDeploymentFormData, checked)
  }

  return (
    <div className="space-y-6">
      {/* Deployment Enable */}
      <div className="space-y-3">
        <label className="text-xs font-bold uppercase tracking-wider text-text-secondary">
          Deployment Configuration
        </label>
        <div className="flex items-center gap-3 p-3 rounded-lg border border-border bg-bg-tertiary/30">
          <input
            type="checkbox"
            name="fichome_enable_deployment"
            checked={data.fichome_enable_deployment}
            onChange={handleCheckboxChange}
            className="w-4 h-4 rounded"
          />
          <label className="text-sm text-text-primary cursor-pointer">
            Deploy FICHOME after installation completes
          </label>
        </div>
      </div>

      {data.fichome_enable_deployment && (
        <>
          {/* WebLogic Host */}
          <div className="space-y-2">
            <label htmlFor="fichome_weblogic_host" className="text-xs font-bold uppercase tracking-wider text-text-secondary">
              WebLogic Server Host (Optional)
            </label>
            <input
              id="fichome_weblogic_host"
              type="text"
              name="fichome_weblogic_host"
              value={data.fichome_weblogic_host}
              onChange={handleInputChange}
              placeholder="e.g., 192.168.1.10 or weblogic.local"
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-bg-tertiary/50 text-text-primary focus:outline-none focus:ring-2 focus:ring-white/20"
            />
            <p className="text-xs text-text-muted">
              Leave empty to auto-detect from OFSAAI_InstallConfig.xml. Used for WAR context path URL construction.
            </p>
          </div>

          {/* WebLogic Port */}
          <div className="space-y-2">
            <label htmlFor="fichome_weblogic_port" className="text-xs font-bold uppercase tracking-wider text-text-secondary">
              WebLogic Server Port (Optional)
            </label>
            <input
              id="fichome_weblogic_port"
              type="text"
              name="fichome_weblogic_port"
              value={data.fichome_weblogic_port}
              onChange={handleInputChange}
              placeholder="e.g., 7001"
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-bg-tertiary/50 text-text-primary focus:outline-none focus:ring-2 focus:ring-white/20"
            />
            <p className="text-xs text-text-muted">
              Leave empty to auto-detect. Standard ports: 7001 (dev), 8001 (prod).
            </p>
          </div>

          {/* ant.sh Timeout */}
          <div className="space-y-2">
            <label htmlFor="fichome_ant_timeout_minutes" className="text-xs font-bold uppercase tracking-wider text-text-secondary">
              ant.sh Timeout (Minutes)
            </label>
            <input
              id="fichome_ant_timeout_minutes"
              type="number"
              name="fichome_ant_timeout_minutes"
              value={data.fichome_ant_timeout_minutes}
              onChange={handleInputChange}
              min="5"
              max="60"
              className="w-full px-3 py-2 text-sm rounded-lg border border-border bg-bg-tertiary/50 text-text-primary focus:outline-none focus:ring-2 focus:ring-white/20"
            />
            <p className="text-xs text-text-muted">
              Build timeout for FICHOME ant.sh execution. Typical: 10-20 minutes. Min: 5, Max: 60.
            </p>
          </div>

          {/* Deployment Steps Preview */}
          <div className="mt-6 p-4 rounded-lg border border-border bg-bg-tertiary/20">
            <div className="text-xs font-bold uppercase tracking-wider text-text-secondary mb-3">
              Deployment Flow (10 Steps)
            </div>
            <div className="space-y-2 text-xs text-text-muted">
              <div className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-border"></span>
                <span>Grant database privileges to schema users</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-border"></span>
                <span>Extract WebLogic domain configuration</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-border"></span>
                <span>Backup and rebuild FICHOME with ant.sh</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-border"></span>
                <span>Deploy EAR/WAR to WebLogic domain</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-1.5 h-1.5 rounded-full bg-border"></span>
                <span>Run startup and health check scripts</span>
              </div>
            </div>
          </div>
        </>
      )}

      {/* Info Box */}
      <div className="p-3 rounded-lg bg-bg-secondary/30 border border-border">
        <p className="text-xs text-text-muted leading-relaxed">
          <span className="text-text-secondary font-bold">ℹ️ Note:</span> FICHOME deployment runs after BD/ECM/SANC installation. Requires completed module installation and Oracle database access.
        </p>
      </div>
    </div>
  )
}
