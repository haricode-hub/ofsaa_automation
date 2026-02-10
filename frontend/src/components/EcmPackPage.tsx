'use client'

import { useEffect, useMemo, useState } from 'react'
import { EcmPackForm, EcmFormData, createDefaultEcmData, validateEcmData } from '@/components/EcmPackForm'
import { EcmPackPreview } from '@/components/EcmPackPreview'

interface EcmPackPageProps {
  enabled: boolean
  host: string
  configSchemaName: string
  atomicSchemaName: string
  onChange: (data: EcmFormData, isValid: boolean) => void
}

export function EcmPackPage({ enabled, host, configSchemaName, atomicSchemaName, onChange }: EcmPackPageProps) {
  const [data, setData] = useState<EcmFormData>(() => createDefaultEcmData(configSchemaName, atomicSchemaName, host))

  useEffect(() => {
    setData((prev) => ({ ...prev, hostname: host || prev.hostname, configSchemaName, atomicSchemaName }))
  }, [host, configSchemaName, atomicSchemaName])

  const validation = useMemo(() => validateEcmData(data), [data])

  useEffect(() => {
    onChange(data, validation.isValid)
  }, [data, validation.isValid, onChange])

  if (!enabled) {
    return null
  }

  return (
    <section className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5 space-y-4">
      <div className="text-sm font-bold text-text-primary uppercase tracking-wider">ECM Pack Configuration</div>
      <div className="text-xs text-text-muted">
        Database & Host, Schema & Password, Tablespaces, ECM default.properties, Review & Generate.
      </div>
      <EcmPackForm data={data} errors={validation.errors} onChange={setData} />
      <EcmPackPreview data={data} />
      {!validation.isValid && <p className="text-xs text-error">Review has blocking validation errors. Resolve highlighted fields before submit.</p>}
    </section>
  )
}
