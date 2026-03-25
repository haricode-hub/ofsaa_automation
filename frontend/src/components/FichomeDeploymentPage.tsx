'use client'

import { useEffect, useState } from 'react'
import { FichomeDeploymentForm, FichomeDeploymentFormData } from '@/components/FichomeDeploymentForm'

interface FichomeDeploymentPageProps {
  enabled: boolean
  onChange: (data: FichomeDeploymentFormData, isValid: boolean) => void
}

function createDefaultFichomeData(): FichomeDeploymentFormData {
  return {
    fichome_enable_deployment: false,
    fichome_weblogic_host: '',
    fichome_weblogic_port: '7001',
    fichome_ant_timeout_minutes: 20,
  }
}

export function FichomeDeploymentPage({ enabled, onChange }: FichomeDeploymentPageProps) {
  const [data, setData] = useState<FichomeDeploymentFormData>(createDefaultFichomeData)
  const [isValid, setIsValid] = useState(false)

  // Validate form
  useEffect(() => {
    const valid = !data.fichome_enable_deployment || (
      data.fichome_ant_timeout_minutes > 0 && data.fichome_ant_timeout_minutes <= 60
    )
    setIsValid(valid)
    onChange(data, valid)
  }, [data, onChange])

  const handleChange = (updates: Partial<FichomeDeploymentFormData>) => {
    setData((prev) => ({ ...prev, ...updates }))
  }

  if (!enabled) return null

  return (
    <div className="space-y-6 pt-4 border-t border-border">
      <div className="space-y-3">
        <div className="text-sm font-bold uppercase tracking-wider text-text-primary">
          FICHOME Deployment Configuration
        </div>
        <p className="text-xs text-text-muted">
          Configure FICHOME deployment settings. This runs after module installation is complete.
        </p>
      </div>

      <FichomeDeploymentForm data={data} onChange={handleChange} />
    </div>
  )
}
