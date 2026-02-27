'use client'

export interface EcmFormData {
  jdbc_host: string
  jdbc_port: string
  jdbc_service: string
  hostname: string
  setupInfoName: string
  prefixSchemaName: 'Y' | 'N'
  applySameForAll: 'Y'
  schemaPassword: string
  datafileDir: string
  configSchemaName: string
  atomicSchemaName: string
  prop_base_country: string
  prop_default_jurisdiction: string
  prop_smtp_host: string
  prop_web_service_user: string
  prop_web_service_password: string
  prop_nls_length_semantics: string
  prop_analyst_data_source: string
  prop_miner_data_source: string
  prop_configure_obiee: '0' | '1'
  prop_fsdf_upload_model: '0' | '1'
  prop_amlsource: string
  prop_kycsource: string
  prop_cssource: string
  prop_externalsystemsource: string
  prop_tbamlsource: string
  prop_fatcasource: string
  prop_ofsecm_datasrcname: string
  prop_comn_gateway_ds: string
  prop_t2jurl: string
  prop_j2turl: string
  prop_cmngtwyurl: string
  prop_bdurl: string
  prop_ofss_wls_url: string
  prop_aai_url: string
  prop_cs_url: string
  prop_arachnys_nns_service_url: string
  // OFSAAI_InstallConfig.xml fields (inherited from BD Pack)
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

export interface EcmValidationResult {
  isValid: boolean
  errors: Partial<Record<keyof EcmFormData, string>> & Record<string, string>
}

const REQUIRED_URL_FIELDS: Array<keyof EcmFormData> = [
  'prop_t2jurl',
  'prop_j2turl',
  'prop_cmngtwyurl',
  'prop_bdurl',
  'prop_ofss_wls_url',
  'prop_aai_url',
  'prop_cs_url',
  'prop_arachnys_nns_service_url'
]

const REQUIRED_FIELDS: Array<keyof EcmFormData> = [
  'jdbc_host',
  'jdbc_port',
  'jdbc_service',
  'hostname',
  'setupInfoName',
  'schemaPassword',
  'prop_base_country',
  'prop_default_jurisdiction',
  'prop_smtp_host',
  'prop_nls_length_semantics',
  'prop_analyst_data_source',
  'prop_miner_data_source',
  'prop_amlsource',
  'prop_kycsource',
  'prop_cssource',
  'prop_externalsystemsource',
  'prop_tbamlsource',
  'prop_fatcasource',
  'prop_ofsecm_datasrcname',
  'prop_comn_gateway_ds',
  ...REQUIRED_URL_FIELDS
]



export function createDefaultEcmData(
  configSchemaName: string,
  atomicSchemaName: string,
  host: string,
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
): EcmFormData {
  return {
    jdbc_host: '',
    jdbc_port: '1521',
    jdbc_service: '',
    hostname: host || '',
    setupInfoName: 'DEV',
    prefixSchemaName: 'N',
    applySameForAll: 'Y',
    schemaPassword: 'ofsaa8x',
    datafileDir: '/u01/app/oracle/oradata/OFSAA/OFSAADB',
    configSchemaName,
    atomicSchemaName,
    prop_base_country: 'US',
    prop_default_jurisdiction: 'AMEA',
    prop_smtp_host: '',
    prop_web_service_user: 'oracle',
    prop_web_service_password: 'ofsaa8x',
    prop_nls_length_semantics: 'BYTE',
    prop_analyst_data_source: 'ANALYST',
    prop_miner_data_source: 'MINER',
    prop_configure_obiee: '0',
    prop_fsdf_upload_model: '0',
    prop_amlsource: 'OFSATOMIC',
    prop_kycsource: 'OFSATOMIC',
    prop_cssource: 'OFSATOMIC',
    prop_externalsystemsource: 'OFSATOMIC',
    prop_tbamlsource: 'OFSATOMIC',
    prop_fatcasource: 'OFSATOMIC',
    prop_ofsecm_datasrcname: 'FCCMINFO',
    prop_comn_gateway_ds: 'FCCMINFO',
    prop_t2jurl: 'http://192.168.0.166:7002',
    prop_j2turl: 'http://192.168.0.166:7002',
    prop_cmngtwyurl: 'http://192.168.0.166:7002',
    prop_bdurl: 'http://192.168.0.166:7002/FICHOME',
    prop_ofss_wls_url: 'http://192.168.0.166:7002',
    prop_aai_url: 'http://192.168.0.166:7002/FICHOME',
    prop_cs_url: 'http://192.168.0.166:7002',
    prop_arachnys_nns_service_url: 'http://192.168.0.166:7002/FICHOME',
    // OFSAAI values from BD Pack (inherited)
    aai_webappservertype: aaiConfig?.aai_webappservertype || '',
    aai_dbserver_ip: aaiConfig?.aai_dbserver_ip || '',
    aai_oracle_service_name: aaiConfig?.aai_oracle_service_name || '',
    aai_abs_driver_path: aaiConfig?.aai_abs_driver_path || '',
    aai_olap_server_implementation: aaiConfig?.aai_olap_server_implementation || '',
    aai_sftp_enable: aaiConfig?.aai_sftp_enable || '',
    aai_file_transfer_port: aaiConfig?.aai_file_transfer_port || '',
    aai_javaport: aaiConfig?.aai_javaport || '',
    aai_nativeport: aaiConfig?.aai_nativeport || '',
    aai_agentport: aaiConfig?.aai_agentport || '',
    aai_iccport: aaiConfig?.aai_iccport || '',
    aai_iccnativeport: aaiConfig?.aai_iccnativeport || '',
    aai_olapport: aaiConfig?.aai_olapport || '',
    aai_msgport: aaiConfig?.aai_msgport || '',
    aai_routerport: aaiConfig?.aai_routerport || '',
    aai_amport: aaiConfig?.aai_amport || '',
    aai_https_enable: aaiConfig?.aai_https_enable || '',
    aai_web_server_ip: aaiConfig?.aai_web_server_ip || '',
    aai_web_server_port: aaiConfig?.aai_web_server_port || '',
    aai_context_name: aaiConfig?.aai_context_name || '',
    aai_webapp_context_path: aaiConfig?.aai_webapp_context_path || '',
    aai_web_local_path: aaiConfig?.aai_web_local_path || '',
    aai_weblogic_domain_home: aaiConfig?.aai_weblogic_domain_home || '',
    aai_ftspshare_path: aaiConfig?.aai_ftspshare_path || '',
    aai_sftp_user_id: aaiConfig?.aai_sftp_user_id || ''
  }
}

function isHttpUrl(value: string): boolean {
  try {
    const parsed = new URL(value)
    return parsed.protocol === 'http:' || parsed.protocol === 'https:'
  } catch {
    return false
  }
}

export function validateEcmData(data: EcmFormData): EcmValidationResult {
  const errors: Record<string, string> = {}

  REQUIRED_FIELDS.forEach((field) => {
    const value = data[field]
    if (!value || `${value}`.trim() === '') {
      errors[field] = 'This field is required.'
    }
  })

  REQUIRED_URL_FIELDS.forEach((field) => {
    const value = (data[field] || '').trim()
    if (value && !isHttpUrl(value)) {
      errors[field] = 'Use a valid http/https URL.'
    }
  })

  if (!data.jdbc_host.trim()) {
    errors.jdbc_host = 'JDBC Host is required'
  }

  if (!data.jdbc_port.trim()) {
    errors.jdbc_port = 'JDBC Port is required'
  } else if (isNaN(Number(data.jdbc_port))) {
    errors.jdbc_port = 'JDBC Port must be a number'
  }

  if (!data.jdbc_service.trim()) {
    errors.jdbc_service = 'JDBC Service/SID is required'
  }

  if (data.datafileDir && !data.datafileDir.startsWith('/')) {
    errors.datafileDir = 'Datafile path must start with /'
  }

  if (data.prop_configure_obiee !== '0' && data.prop_configure_obiee !== '1') {
    errors.prop_configure_obiee = 'Only 0 or 1 is allowed.'
  }

  if (data.prop_fsdf_upload_model !== '0' && data.prop_fsdf_upload_model !== '1') {
    errors.prop_fsdf_upload_model = 'Only 0 or 1 is allowed.'
  }

  return {
    isValid: Object.keys(errors).length === 0,
    errors
  }
}

interface EcmPackFormProps {
  data: EcmFormData
  errors: Record<string, string>
  onChange: (next: EcmFormData) => void
}

function fieldClass(hasError: boolean): string {
  const base = 'w-full bg-bg-secondary border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:bg-bg-tertiary'
  return hasError ? `${base} border-error focus:border-error` : `${base} border-border focus:border-white`
}

export function EcmPackForm({ data, errors, onChange }: EcmPackFormProps) {
  const update = <K extends keyof EcmFormData>(field: K, value: EcmFormData[K]) => {
    const updated = { ...data, [field]: value }

    // ── Group 1: DB IP (bidirectional) ──
    const dbIpFields: Array<keyof EcmFormData> = ['aai_dbserver_ip', 'jdbc_host']
    if ((dbIpFields as string[]).includes(field) && value) {
      for (const f of dbIpFields) {
        if (f !== field) (updated as Record<string, unknown>)[f] = value
      }
    }

    // ── Group 2: Oracle Service (bidirectional) ──
    const serviceFields: Array<keyof EcmFormData> = ['aai_oracle_service_name', 'jdbc_service']
    if ((serviceFields as string[]).includes(field) && value) {
      for (const f of serviceFields) {
        if (f !== field) (updated as Record<string, unknown>)[f] = value
      }
    }

    // ── Group 3: App Host (bidirectional) ──
    const hostFields: Array<keyof EcmFormData> = ['hostname', 'prop_smtp_host', 'aai_web_server_ip']
    if ((hostFields as string[]).includes(field) && value) {
      for (const f of hostFields) {
        if (f !== field) (updated as Record<string, unknown>)[f] = value
      }
    }

    onChange(updated)
  }

  const input = (label: string, field: keyof EcmFormData, placeholder = '', type: 'text' | 'password' = 'text') => (
    <div className="space-y-1">
      <label className="text-xs font-bold text-text-primary uppercase tracking-wider">{label}</label>
      <input
        type={type}
        value={String(data[field] ?? '')}
        onChange={(e) => update(field, e.target.value as EcmFormData[typeof field])}
        placeholder={placeholder}
        className={fieldClass(!!errors[field])}
      />
      {errors[field] && <p className="text-xs text-error">{errors[field]}</p>}
    </div>
  )

  return (
    <div className="space-y-6">
      <details open className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">Schema Creator (OFS_ECM_SCHEMA_IN.xml)</div>
            <div className="text-xs text-text-muted mt-1">JDBC, tablespace paths, schema names, and password.</div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {input('JDBC Host (DB IP)', 'jdbc_host', '192.168.0.165')}
            {input('JDBC Port', 'jdbc_port', '1521')}
            {input('JDBC Service/SID', 'jdbc_service', 'FLEXPDB1')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('Application IP (HOSTNAME)', 'hostname', '192.168.0.41')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('SETUPINFO NAME', 'setupInfoName', 'DEV')}
            <div className="space-y-1">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">PREFIX_SCHEMA_NAME</label>
              <select value={data.prefixSchemaName} onChange={(e) => update('prefixSchemaName', e.target.value as 'Y' | 'N')} className={fieldClass(!!errors.prefixSchemaName)}>
                <option value="N">N</option>
                <option value="Y">Y</option>
              </select>
            </div>
          </div>
          {input('Schema Password', 'schemaPassword', 'ofsaa8x', 'password')}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('CONFIG Schema Name', 'configSchemaName')}
            {input('ATOMIC Schema Name', 'atomicSchemaName')}
          </div>
          <div className="text-xs text-text-muted">Schema names are inherited from BD pack (Atomic + Config).</div>
          {input('Datafile Directory Path', 'datafileDir', '/u01/app/oracle/oradata/OFSAA/OFSAADB')}
        </div>
      </details>

      <details className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">Silent Installer (default.properties)</div>
            <div className="text-xs text-text-muted mt-1">Only required ECM keys collected from UI.</div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('BASE_COUNTRY', 'prop_base_country')}
            {input('DEFAULT_JURISDICTION', 'prop_default_jurisdiction')}
            {input('SMTP_HOST', 'prop_smtp_host')}
            {input('NLS_LENGTH_SEMANTICS', 'prop_nls_length_semantics')}
            {input('ANALYST_DATA_SOURCE', 'prop_analyst_data_source')}
            {input('MINER_DATA_SOURCE', 'prop_miner_data_source')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">CONFIGURE_OBIEE</label>
              <select value={data.prop_configure_obiee} onChange={(e) => update('prop_configure_obiee', e.target.value as '0' | '1')} className={fieldClass(!!errors.prop_configure_obiee)}>
                <option value="0">0</option>
                <option value="1">1</option>
              </select>
              {errors.prop_configure_obiee && <p className="text-xs text-error">{errors.prop_configure_obiee}</p>}
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">FSDF_UPLOAD_MODEL</label>
              <select value={data.prop_fsdf_upload_model} onChange={(e) => update('prop_fsdf_upload_model', e.target.value as '0' | '1')} className={fieldClass(!!errors.prop_fsdf_upload_model)}>
                <option value="0">0</option>
                <option value="1">1</option>
              </select>
              {errors.prop_fsdf_upload_model && <p className="text-xs text-error">{errors.prop_fsdf_upload_model}</p>}
            </div>
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('AMLSOURCE', 'prop_amlsource')}
            {input('KYCSOURCE', 'prop_kycsource')}
            {input('CSSOURCE', 'prop_cssource')}
            {input('EXTERNALSYSTEMSOURCE', 'prop_externalsystemsource')}
            {input('TBAMLSOURCE', 'prop_tbamlsource')}
            {input('FATCASOURCE', 'prop_fatcasource')}
            {input('OFSECM_DATASRCNAME', 'prop_ofsecm_datasrcname')}
            {input('COMN_GATWAY_DS', 'prop_comn_gateway_ds')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('T2JURL', 'prop_t2jurl')}
            {input('J2TURL', 'prop_j2turl')}
            {input('CMNGTWYURL', 'prop_cmngtwyurl')}
            {input('BDURL', 'prop_bdurl')}
            {input('OFSS_WLS_URL', 'prop_ofss_wls_url')}
            {input('AAI_URL', 'prop_aai_url')}
            {input('CS_URL', 'prop_cs_url')}
            {input('ARACHNYS_NNS_SERVICE_URL', 'prop_arachnys_nns_service_url')}
          </div>
        </div>
      </details>

      <details className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">OFSAAI Install (OFSAAI_InstallConfig.xml)</div>
            <div className="text-xs text-text-muted mt-1">Web server, DB, SFTP and port configuration. Inherited from BD Pack if available.</div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {input('WEBAPPSERVERTYPE', 'aai_webappservertype', '3')}
            {input('DBSERVER_IP', 'aai_dbserver_ip', '192.168.3.42')}
            {input('ORACLE_SERVICE', 'aai_oracle_service_name', 'OFSAAPDB')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('ABS_DRIVER_PATH', 'aai_abs_driver_path', '/u01/oracle/jdbc')}
            {input('WEB_SERVER_IP', 'aai_web_server_ip', '192.168.3.41')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            {input('HTTPS_ENABLE', 'aai_https_enable', '1')}
            {input('WEB_SERVER_PORT', 'aai_web_server_port', '7002')}
            {input('CONTEXT_NAME', 'aai_context_name', 'FICHOME')}
            {input('WEBAPP_CONTEXT_PATH', 'aai_webapp_context_path', '/FICHOME')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('WEB_LOCAL_PATH', 'aai_web_local_path', '/u01/OFSAA')}
            {input('WEBLOGIC_DOMAIN_HOME', 'aai_weblogic_domain_home', '/u01/wls/domains/FICHOME')}
          </div>
          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {input('JAVAPORT', 'aai_javaport', '8001')}
            {input('NATIVEPORT', 'aai_nativeport', '8002')}
            {input('AGENTPORT', 'aai_agentport', '8003')}
            {input('ICCPORT', 'aai_iccport', '8004')}
            {input('ICCNATIVE', 'aai_iccnativeport', '8005')}
            {input('OLAPPORT', 'aai_olapport', '8006')}
            {input('MSGPORT', 'aai_msgport', '8007')}
            {input('ROUTERPORT', 'aai_routerport', '8008')}
            {input('AMPORT', 'aai_amport', '8009')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {input('SFTP_ENABLE', 'aai_sftp_enable', '1')}
            {input('FILE_TRANSFER_PORT', 'aai_file_transfer_port', '22')}
            {input('OFSAAI_SFTP_USER_ID', 'aai_sftp_user_id', 'oracle')}
          </div>
          <div>
            {input('OFSAAI_FTPSHARE_PATH', 'aai_ftspshare_path', '/u01/OFSAA/FICHOME/ftp')}
          </div>
          <div className="text-xs text-text-muted">
            OLAP_IMPL and other OFSAAI fields are derived from configuration. Edit as needed if different from inherited values.
          </div>
        </div>
      </details>
    </div>
  )
}
