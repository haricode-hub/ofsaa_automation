'use client'

import { useMemo, useState } from 'react'
import { EcmFormData } from '@/components/EcmPackForm'

interface EcmPackPreviewProps {
  data: EcmFormData
}

function buildSchemaXml(data: EcmFormData): string {
  const tablespaceXml = data.tablespaces
    .map((row) => `  <TABLESPACE ID="${row.id}" VALUE="${row.value}" DATAFILE="${data.datafileDir.replace(/\/$/, '')}/${row.filename}" SIZE="${row.size}" AUTOEXTEND="${row.autoextend}" ENCRYPT="${row.encrypt}" />`)
    .join('\n')

  return `<?xml version="1.0" encoding="UTF-8"?>
<INSTALL>
  <JDBC_URL>${data.jdbcUrl}</JDBC_URL>
  <HOST>${data.hostname}</HOST>
  <SETUPINFO NAME="${data.setupInfoName}" PREFIX_SCHEMA_NAME="${data.prefixSchemaName}" />
  <PASSWORD APPLYSAMEFORALL="Y" DEFAULT="${data.schemaPassword}" />

${tablespaceXml}

  <SCHEMA TYPE="CONFIG" NAME="${data.configSchemaName}" APP_ID="OFS_AAI" DEFAULTTABLESPACE="OFS_ECM_DATA_CONF_TBSP" TEMPTABLESPACE="TEMP" QUOTA="10G" />
  <SCHEMA TYPE="ATOMIC" NAME="${data.atomicSchemaName}" APP_ID="OFS_IPE" INFODOM="ECMINFO" DEFAULTTABLESPACE="OFS_ECM_DATA_CM_TBSP" TEMPTABLESPACE="TEMP" QUOTA="10G" />
  <SCHEMA TYPE="ATOMIC" NAME="${data.atomicSchemaName}" APP_ID="OFS_NGECM" INFODOM="ECMINFO" DEFAULTTABLESPACE="OFS_ECM_DATA_CM_TBSP" TEMPTABLESPACE="TEMP" QUOTA="10G" />
</INSTALL>
`
}

function buildDefaultProperties(data: EcmFormData): string {
  return [
    `BASE_COUNTRY=${data.prop_base_country}`,
    `DEFAULT_JURISDICTION=${data.prop_default_jurisdiction}`,
    `SMTP_HOST=${data.prop_smtp_host}`,
    `NLS_LENGTH_SEMANTICS=${data.prop_nls_length_semantics}`,
    `ANALYST_DATA_SOURCE=${data.prop_analyst_data_source}`,
    `MINER_DATA_SOURCE=${data.prop_miner_data_source}`,
    `CONFIGURE_OBIEE=${data.prop_configure_obiee}`,
    `FSDF_UPLOAD_MODEL=${data.prop_fsdf_upload_model}`,
    `AMLSOURCE=${data.prop_amlsource}`,
    `KYCSOURCE=${data.prop_kycsource}`,
    `CSSOURCE=${data.prop_cssource}`,
    `EXTERNALSYSTEMSOURCE=${data.prop_externalsystemsource}`,
    `TBAMLSOURCE=${data.prop_tbamlsource}`,
    `FATCASOURCE=${data.prop_fatcasource}`,
    `OFSECM_DATASRCNAME=${data.prop_ofsecm_datasrcname}`,
    `COMN_GATWAY_DS=${data.prop_comn_gateway_ds}`,
    `T2JURL=${data.prop_t2jurl}`,
    `J2TURL=${data.prop_j2turl}`,
    `CMNGTWYURL=${data.prop_cmngtwyurl}`,
    `BDURL=${data.prop_bdurl}`,
    `OFSS_WLS_URL=${data.prop_ofss_wls_url}`,
    `AAI_URL=${data.prop_aai_url}`,
    `CS_URL=${data.prop_cs_url}`,
    `ARACHNYS_NNS_SERVICE_URL=${data.prop_arachnys_nns_service_url}`,
  ].join('\n') + '\n'
}

function downloadText(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'text/plain;charset=utf-8' })
  const link = document.createElement('a')
  link.href = URL.createObjectURL(blob)
  link.download = filename
  link.click()
  URL.revokeObjectURL(link.href)
}

export function EcmPackPreview({ data }: EcmPackPreviewProps) {
  const [tab, setTab] = useState<'xml' | 'properties'>('xml')
  const schemaXml = useMemo(() => buildSchemaXml(data), [data])
  const defaultProperties = useMemo(() => buildDefaultProperties(data), [data])
  const activeContent = tab === 'xml' ? schemaXml : defaultProperties

  const copyToClipboard = async () => {
    await navigator.clipboard.writeText(activeContent)
  }

  return (
    <div className="rounded-xl border border-border bg-bg-secondary/40 p-4 space-y-3">
      <div className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <button type="button" onClick={() => setTab('xml')} className={`px-3 py-1 text-xs rounded ${tab === 'xml' ? 'bg-white text-black' : 'bg-bg-secondary text-text-primary border border-border'}`}>
            OFS_ECM_SCHEMA_IN.xml
          </button>
          <button type="button" onClick={() => setTab('properties')} className={`px-3 py-1 text-xs rounded ${tab === 'properties' ? 'bg-white text-black' : 'bg-bg-secondary text-text-primary border border-border'}`}>
            default.properties
          </button>
        </div>
        <div className="flex items-center gap-2">
          <button type="button" onClick={copyToClipboard} className="px-3 py-1 text-xs rounded border border-border">Copy</button>
          <button type="button" onClick={() => downloadText(tab === 'xml' ? 'OFS_ECM_SCHEMA_IN.xml' : 'default.properties', activeContent)} className="px-3 py-1 text-xs rounded border border-border">Download</button>
        </div>
      </div>
      <pre className="h-[360px] overflow-auto rounded-lg border border-border bg-black/40 p-3 text-xs text-text-secondary whitespace-pre-wrap">{activeContent}</pre>
    </div>
  )
}
