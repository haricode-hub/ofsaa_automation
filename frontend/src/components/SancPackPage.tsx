'use client'

import { useEffect, useMemo, useState } from 'react'
import { SancPackForm, SancFormData, createDefaultSancData, validateSancData } from '@/components/SancPackForm'

interface AaiConfig {
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

interface SancPackPageProps {
  enabled: boolean
  host: string
  configSchemaName: string
  atomicSchemaName: string
  schemaDatafileDir?: string
  onChange: (data: SancFormData, isValid: boolean) => void
  aaiConfig?: AaiConfig
}

export function SancPackPage({ enabled, host, configSchemaName, atomicSchemaName, schemaDatafileDir, onChange, aaiConfig }: SancPackPageProps) {
  const [data, setData] = useState<SancFormData>(() => createDefaultSancData(configSchemaName, atomicSchemaName, host, aaiConfig))

  // Sync key fields from BD Pack -> SANC whenever they change
  useEffect(() => {
    setData((prev) => {
      const next = { ...prev, hostname: host || prev.hostname, configSchemaName, atomicSchemaName }

      // DB IP
      if (aaiConfig?.aai_dbserver_ip) {
        next.aai_dbserver_ip = aaiConfig.aai_dbserver_ip
        next.jdbc_host = aaiConfig.aai_dbserver_ip
      }
      // Oracle Service
      if (aaiConfig?.aai_oracle_service_name) {
        next.aai_oracle_service_name = aaiConfig.aai_oracle_service_name
        next.jdbc_service = aaiConfig.aai_oracle_service_name
      }
      // Web server IP
      if (aaiConfig?.aai_web_server_ip) {
        next.aai_web_server_ip = aaiConfig.aai_web_server_ip
      }
      // WebLogic Domain Home
      if (aaiConfig?.aai_weblogic_domain_home) {
        next.aai_weblogic_domain_home = aaiConfig.aai_weblogic_domain_home
      }
      // WebApp Context Path
      if (aaiConfig?.aai_webapp_context_path) {
        next.aai_webapp_context_path = aaiConfig.aai_webapp_context_path
      }
      // Datafile dir
      if (schemaDatafileDir) {
        next.datafileDir = schemaDatafileDir
      }
      // Inherit all AAI fields
      if (aaiConfig) {
        next.aai_webappservertype = aaiConfig.aai_webappservertype || next.aai_webappservertype
        next.aai_abs_driver_path = aaiConfig.aai_abs_driver_path || next.aai_abs_driver_path
        next.aai_olap_server_implementation = aaiConfig.aai_olap_server_implementation || next.aai_olap_server_implementation
        next.aai_sftp_enable = aaiConfig.aai_sftp_enable || next.aai_sftp_enable
        next.aai_file_transfer_port = aaiConfig.aai_file_transfer_port || next.aai_file_transfer_port
        next.aai_javaport = aaiConfig.aai_javaport || next.aai_javaport
        next.aai_nativeport = aaiConfig.aai_nativeport || next.aai_nativeport
        next.aai_agentport = aaiConfig.aai_agentport || next.aai_agentport
        next.aai_iccport = aaiConfig.aai_iccport || next.aai_iccport
        next.aai_iccnativeport = aaiConfig.aai_iccnativeport || next.aai_iccnativeport
        next.aai_olapport = aaiConfig.aai_olapport || next.aai_olapport
        next.aai_msgport = aaiConfig.aai_msgport || next.aai_msgport
        next.aai_routerport = aaiConfig.aai_routerport || next.aai_routerport
        next.aai_amport = aaiConfig.aai_amport || next.aai_amport
        next.aai_https_enable = aaiConfig.aai_https_enable || next.aai_https_enable
        next.aai_web_server_port = aaiConfig.aai_web_server_port || next.aai_web_server_port
        next.aai_context_name = aaiConfig.aai_context_name || next.aai_context_name
        next.aai_web_local_path = aaiConfig.aai_web_local_path || next.aai_web_local_path
        next.aai_ftspshare_path = aaiConfig.aai_ftspshare_path || next.aai_ftspshare_path
        next.aai_sftp_user_id = aaiConfig.aai_sftp_user_id || next.aai_sftp_user_id
      }

      return next
    })
  }, [host, configSchemaName, atomicSchemaName, schemaDatafileDir,
    aaiConfig?.aai_dbserver_ip, aaiConfig?.aai_oracle_service_name,
    aaiConfig?.aai_web_server_ip, aaiConfig?.aai_web_server_port,
    aaiConfig?.aai_https_enable, aaiConfig?.aai_weblogic_domain_home,
    aaiConfig?.aai_webapp_context_path, aaiConfig?.aai_abs_driver_path,
    aaiConfig?.aai_sftp_enable, aaiConfig?.aai_file_transfer_port,
    aaiConfig?.aai_javaport, aaiConfig?.aai_nativeport,
    aaiConfig?.aai_agentport, aaiConfig?.aai_iccport,
    aaiConfig?.aai_iccnativeport, aaiConfig?.aai_olapport,
    aaiConfig?.aai_msgport, aaiConfig?.aai_routerport,
    aaiConfig?.aai_amport, aaiConfig?.aai_web_local_path,
    aaiConfig?.aai_ftspshare_path, aaiConfig?.aai_sftp_user_id,
    aaiConfig?.aai_context_name, aaiConfig?.aai_webappservertype,
    aaiConfig?.aai_olap_server_implementation])

  const validation = useMemo(() => validateSancData(data), [data])

  useEffect(() => {
    onChange(data, validation.isValid)
  }, [data, validation.isValid, onChange])

  if (!enabled) {
    return null
  }

  return (
    <section className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5 space-y-4">
      <div className="text-sm font-bold text-text-primary uppercase tracking-wider">SANC Pack Configuration</div>
      <div className="text-xs text-text-muted">
        Database & Host, Schema & Password, Tablespaces, CS/TFLT SWIFTINFO, OFSAAI config.
      </div>
      <SancPackForm data={data} errors={validation.errors} onChange={setData} />
      {!validation.isValid && <p className="text-xs text-error">Review has blocking validation errors. Resolve highlighted fields before submit.</p>}
    </section>
  )
}
