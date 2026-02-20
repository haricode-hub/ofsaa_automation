'use client'

import { useEffect, useMemo, useState } from 'react'
import { BdPackForm, BdPackFormData, createDefaultBdPackData, validateBdPackData } from '@/components/BdPackForm'
import { MainConfigData } from '@/components/MainConfiguration'

interface BdPackPageProps {
  enabled: boolean
  host: string
  mainConfig?: MainConfigData
  onChange: (data: BdPackFormData, isValid: boolean) => void
  onMainConfigChange?: (data: MainConfigData) => void
}

export function BdPackPage({ enabled, host, mainConfig, onChange, onMainConfigChange }: BdPackPageProps) {
  const [data, setData] = useState<BdPackFormData>(() => createDefaultBdPackData(host))

  useEffect(() => {
    setData((prev) => ({ ...prev, host: host || prev.host }))
  }, [host])

  const validation = useMemo(() => validateBdPackData(data), [data])

  useEffect(() => {
    onChange(data, validation.isValid)
  }, [data, validation.isValid, onChange])

  if (!enabled) {
    return null
  }

  return (
    <section className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5 space-y-4">
      <div className="text-sm font-bold text-text-primary uppercase tracking-wider">BD Pack Configuration</div>
      <div className="text-xs text-text-muted">
        Schema Creator, Application Pack, Silent Installer, & OFSAAI configuration.
      </div>
      <BdPackForm data={data} errors={validation.errors} onChange={setData} />
      {!validation.isValid && <p className="text-xs text-error">Review has blocking validation errors. Resolve highlighted fields before submit.</p>}
    </section>
  )
}
