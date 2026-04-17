'use client'

import { useEffect, useMemo, useState } from 'react'
import { EcmPackForm, EcmFormData, createDefaultEcmData, validateEcmData } from '@/components/EcmPackForm'

interface EcmPackPageProps {
  enabled: boolean
  host: string
  configSchemaName: string
  atomicSchemaName: string
  schemaDatafileDir?: string
  bdSchemaPassword?: string
  bdJdbcPort?: string
  initialData?: EcmFormData | null
  onChange: (data: EcmFormData, isValid: boolean) => void
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

export function EcmPackPage({ enabled, host, configSchemaName, atomicSchemaName, schemaDatafileDir, bdSchemaPassword, bdJdbcPort, initialData, onChange, aaiConfig }: EcmPackPageProps) {
  const [data, setData] = useState<EcmFormData>(() => initialData || createDefaultEcmData(configSchemaName, atomicSchemaName, host, aaiConfig))

  // Sync key fields from BD Pack → ECM whenever they change
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
      // App / Web server IP
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
      // SMTP host mirrors the app host
      if (host) {
        next.prop_smtp_host = host
      }
      // Datafile dir
      if (schemaDatafileDir) {
        next.datafileDir = schemaDatafileDir
      }
      // Schema password from BD
      if (bdSchemaPassword && !prev.schemaPassword) {
        next.schemaPassword = bdSchemaPassword
      }
      // JDBC port from BD
      if (bdJdbcPort) {
        next.jdbc_port = bdJdbcPort
      }

      // Schema-based sources
      // ATOMIC schema for data sources
      if (atomicSchemaName) {
        next.prop_amlsource = atomicSchemaName
        next.prop_kycsource = atomicSchemaName
        next.prop_cssource = atomicSchemaName
        next.prop_externalsystemsource = atomicSchemaName
        next.prop_tbamlsource = atomicSchemaName
        next.prop_fatcasource = atomicSchemaName
      }
      // CONFIG schema for metadata/gateway sources
      if (configSchemaName) {
        next.prop_ofsecm_datasrcname = configSchemaName
        next.prop_comn_gateway_ds = configSchemaName
      }

      // Build URLs from web server IP and port
      if (aaiConfig?.aai_web_server_ip && aaiConfig?.aai_web_server_port) {
        const protocol = aaiConfig.aai_https_enable === '1' ? 'https' : 'http'
        const baseUrl = `${protocol}://${aaiConfig.aai_web_server_ip}:${aaiConfig.aai_web_server_port}`
        next.prop_t2jurl = baseUrl
        next.prop_j2turl = baseUrl
        next.prop_cmngtwyurl = baseUrl
        next.prop_ofss_wls_url = baseUrl
        next.prop_cs_url = baseUrl
        next.prop_bdurl = `${baseUrl}/FICHOME`
        next.prop_aai_url = `${baseUrl}/FICHOME`
        next.prop_arachnys_nns_service_url = `${baseUrl}/FICHOME`
      }

      return next
    })
  }, [host, configSchemaName, atomicSchemaName, aaiConfig?.aai_dbserver_ip, aaiConfig?.aai_oracle_service_name, aaiConfig?.aai_web_server_ip, aaiConfig?.aai_web_server_port, aaiConfig?.aai_https_enable, aaiConfig?.aai_weblogic_domain_home, aaiConfig?.aai_webapp_context_path, schemaDatafileDir, bdSchemaPassword, bdJdbcPort])

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
