'use client'

import { useEffect, useMemo, useState } from 'react'
import { EcmPackForm, EcmFormData, createDefaultEcmData, validateEcmData } from '@/components/EcmPackForm'
import { MainConfigData } from '@/components/MainConfiguration'

interface EcmPackPageProps {
  enabled: boolean
  host: string
  configSchemaName: string
  atomicSchemaName: string
  mainConfig?: MainConfigData
  onChange: (data: EcmFormData, isValid: boolean) => void
  onMainConfigChange?: (data: MainConfigData) => void
  aaiConfig?: {
    aai_webappservertype: string
    aai_dbserver_ip: string
    aai_oracle_service_name: string
    aai_abs_driver_path: string
    aai_olap_server_implementation: string
    aai_sftp_enable: string
    aai_file_transfer_port: string
    aai_javaport: string
    aai_nativeport: string
    aai_agentport: string
    aai_iccport: string
    aai_iccnativeport: string
    aai_olapport: string
    aai_msgport: string
    aai_routerport: string
    aai_amport: string
    aai_https_enable: string
    aai_web_server_ip: string
    aai_web_server_port: string
    aai_context_name: string
    aai_webapp_context_path: string
    aai_web_local_path: string
    aai_weblogic_domain_home: string
    aai_ftspshare_path: string
    aai_sftp_user_id: string
  }
}

export function EcmPackPage({ enabled, host, configSchemaName, atomicSchemaName, mainConfig, onChange, onMainConfigChange, aaiConfig }: EcmPackPageProps) {
  const [data, setData] = useState<EcmFormData>(() => createDefaultEcmData(configSchemaName, atomicSchemaName, host, aaiConfig))

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
      {!validation.isValid && <p className="text-xs text-error">Review has blocking validation errors. Resolve highlighted fields before submit.</p>}
    </section>
  )
}
