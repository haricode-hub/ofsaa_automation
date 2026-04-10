'use client'

export interface SancFormData {
  // OFS_SANC_SCHEMA_IN.xml
  jdbc_host: string
  jdbc_port: string
  jdbc_service: string
  hostname: string
  setupInfoName: string
  applySameForAll: 'Y' | 'N'
  schemaPassword: string
  datafileDir: string
  tablespaceAutoextend: 'ON' | 'OFF'
  externalDirectoryValue: string
  configSchemaName: string
  atomicSchemaName: string
  // SWIFTINFO
  cs_swiftinfo: string
  tflt_swiftinfo: string
  // OFSAAI_InstallConfig.xml
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

export interface SancValidationResult {
  isValid: boolean
  errors: Record<string, string>
}

const REQUIRED_FIELDS: Array<keyof SancFormData> = [
  'jdbc_host',
  'jdbc_port',
  'jdbc_service',
  'hostname',
  'schemaPassword',
  'configSchemaName',
  'atomicSchemaName',
]

export function createDefaultSancData(
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
): SancFormData {
  return {
    jdbc_host: aaiConfig?.aai_dbserver_ip || '',
    jdbc_port: '1521',
    jdbc_service: aaiConfig?.aai_oracle_service_name || '',
    hostname: host || '',
    setupInfoName: 'DEV',
    applySameForAll: 'Y',
    schemaPassword: '',
    datafileDir: '/u01/app/oracle/oradata/OFSAA/OFSAADB',
    tablespaceAutoextend: 'OFF',
    externalDirectoryValue: '/u01/OFSAA/FICHOME/bdf/inbox',
    configSchemaName,
    atomicSchemaName,
    cs_swiftinfo: '',
    tflt_swiftinfo: '',
    aai_webappservertype: aaiConfig?.aai_webappservertype || '3',
    aai_dbserver_ip: aaiConfig?.aai_dbserver_ip || '',
    aai_oracle_service_name: aaiConfig?.aai_oracle_service_name || '',
    aai_abs_driver_path: aaiConfig?.aai_abs_driver_path || '',
    aai_olap_server_implementation: aaiConfig?.aai_olap_server_implementation || '0',
    aai_sftp_enable: aaiConfig?.aai_sftp_enable || '1',
    aai_file_transfer_port: aaiConfig?.aai_file_transfer_port || '22',
    aai_javaport: aaiConfig?.aai_javaport || '9999',
    aai_nativeport: aaiConfig?.aai_nativeport || '6666',
    aai_agentport: aaiConfig?.aai_agentport || '6510',
    aai_iccport: aaiConfig?.aai_iccport || '6507',
    aai_iccnativeport: aaiConfig?.aai_iccnativeport || '6509',
    aai_olapport: aaiConfig?.aai_olapport || '10101',
    aai_msgport: aaiConfig?.aai_msgport || '6501',
    aai_routerport: aaiConfig?.aai_routerport || '6502',
    aai_amport: aaiConfig?.aai_amport || '6506',
    aai_https_enable: aaiConfig?.aai_https_enable || '1',
    aai_web_server_ip: aaiConfig?.aai_web_server_ip || '',
    aai_web_server_port: aaiConfig?.aai_web_server_port || '7002',
    aai_context_name: aaiConfig?.aai_context_name || 'FICHOME',
    aai_webapp_context_path: aaiConfig?.aai_webapp_context_path || '',
    aai_web_local_path: aaiConfig?.aai_web_local_path || '/u01/OFSAA/FTPSHARE',
    aai_weblogic_domain_home: aaiConfig?.aai_weblogic_domain_home || '',
    aai_ftspshare_path: aaiConfig?.aai_ftspshare_path || '/u01/OFSAA/FTPSHARE',
    aai_sftp_user_id: aaiConfig?.aai_sftp_user_id || 'oracle',
  }
}

export function validateSancData(data: SancFormData): SancValidationResult {
  const errors: Record<string, string> = {}

  REQUIRED_FIELDS.forEach((field) => {
    const value = data[field]
    if (!value || `${value}`.trim() === '') {
      errors[field] = 'This field is required.'
    }
  })

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  }
}

interface SancPackFormProps {
  data: SancFormData
  errors: Record<string, string>
  onChange: (next: SancFormData) => void
}

function fieldClass(hasError: boolean): string {
  const base = 'w-full bg-bg-secondary border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:bg-bg-tertiary'
  return hasError ? `${base} border-error focus:border-error` : `${base} border-border focus:border-white`
}

export function SancPackForm({ data, errors, onChange }: SancPackFormProps) {
  const update = <K extends keyof SancFormData>(field: K, value: SancFormData[K]) => {
    const updated = { ...data, [field]: value }

    // Bidirectional: DB IP
    const dbIpFields: Array<keyof SancFormData> = ['aai_dbserver_ip', 'jdbc_host']
    if ((dbIpFields as string[]).includes(field) && value) {
      for (const f of dbIpFields) {
        if (f !== field) (updated as Record<string, unknown>)[f] = value
      }
    }

    // Bidirectional: Oracle Service
    const serviceFields: Array<keyof SancFormData> = ['aai_oracle_service_name', 'jdbc_service']
    if ((serviceFields as string[]).includes(field) && value) {
      for (const f of serviceFields) {
        if (f !== field) (updated as Record<string, unknown>)[f] = value
      }
    }

    // Bidirectional: App Host
    const hostFields: Array<keyof SancFormData> = ['hostname', 'aai_web_server_ip']
    if ((hostFields as string[]).includes(field) && value) {
      for (const f of hostFields) {
        if (f !== field) (updated as Record<string, unknown>)[f] = value
      }
    }

    onChange(updated)
  }

  const input = (label: string, field: keyof SancFormData, placeholder = '', type: 'text' | 'password' = 'text') => (
    <div className="space-y-1">
      <label className="text-xs font-bold text-text-primary uppercase tracking-wider">{label}</label>
      <input
        type={type}
        value={String(data[field] ?? '')}
        onChange={(e) => update(field, e.target.value as SancFormData[typeof field])}
        placeholder={placeholder}
        className={fieldClass(!!errors[field])}
      />
      {errors[field] && <p className="text-xs text-error">{errors[field]}</p>}
    </div>
  )

  return (
    <div className="space-y-6">
      {/* Schema Creator */}
      <details open className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">Schema Creator (OFS_SANC_SCHEMA_IN.xml)</div>
            <div className="text-xs text-text-muted mt-1">JDBC, tablespace paths, schema names, and password.</div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {input('JDBC Host (DB IP)', 'jdbc_host', '192.168.0.165')}
            {input('JDBC Port', 'jdbc_port', '1521')}
            {input('JDBC Service Name', 'jdbc_service', 'FLEXPDB1')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('Application IP (HOSTNAME)', 'hostname', '192.168.0.41')}
            {input('SETUPINFO NAME', 'setupInfoName', 'DEV')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-1">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">ApplySameForAll</label>
              <select value={data.applySameForAll} onChange={(e) => update('applySameForAll', e.target.value as 'Y' | 'N')} className={fieldClass(false)}>
                <option value="Y">Y</option>
                <option value="N">N</option>
              </select>
            </div>
            <div className="space-y-1">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">AUTOEXTEND</label>
              <select value={data.tablespaceAutoextend} onChange={(e) => update('tablespaceAutoextend', e.target.value as 'ON' | 'OFF')} className={fieldClass(false)}>
                <option value="OFF">OFF</option>
                <option value="ON">ON</option>
              </select>
            </div>
          </div>
          {input('Schema Password', 'schemaPassword', 'Password1', 'password')}
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('CONFIG Schema Name', 'configSchemaName')}
            {input('ATOMIC Schema Name', 'atomicSchemaName')}
          </div>
          <div className="text-xs text-text-muted">Schema names are inherited from BD Pack (Atomic + Config).</div>
          {input('Datafile Directory Path', 'datafileDir', '/u01/app/oracle/oradata/OFSAA/OFSAADB')}
          {input('External Directory Value', 'externalDirectoryValue', '/u01/OFSAA/FICHOME/bdf/inbox')}
        </div>
      </details>

      {/* SWIFTINFO */}
      <details className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">SWIFTINFO (default.properties CS / TFLT)</div>
            <div className="text-xs text-text-muted mt-1">SWIFTINFO values for OFS_CS and OFS_TFLT.</div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>
        <div className="mt-5 space-y-4">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('CS SWIFTINFO', 'cs_swiftinfo', 'SWIFT_CS_INFO')}
            {input('TFLT SWIFTINFO', 'tflt_swiftinfo', 'SWIFT_TFLT_INFO')}
          </div>
        </div>
      </details>

      {/* OFSAAI Install Config */}
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
            {input('JAVAPORT', 'aai_javaport', '9999')}
            {input('NATIVEPORT', 'aai_nativeport', '6666')}
            {input('AGENTPORT', 'aai_agentport', '6510')}
            {input('ICCPORT', 'aai_iccport', '6507')}
            {input('ICCNATIVE', 'aai_iccnativeport', '6509')}
            {input('OLAPPORT', 'aai_olapport', '10101')}
            {input('MSGPORT', 'aai_msgport', '6501')}
            {input('ROUTERPORT', 'aai_routerport', '6502')}
            {input('AMPORT', 'aai_amport', '6506')}
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            {input('SFTP_ENABLE', 'aai_sftp_enable', '1')}
            {input('FILE_TRANSFER_PORT', 'aai_file_transfer_port', '22')}
            {input('OFSAAI_SFTP_USER_ID', 'aai_sftp_user_id', 'oracle')}
          </div>
          {input('OFSAAI_FTPSHARE_PATH', 'aai_ftspshare_path', '/u01/OFSAA/FTPSHARE')}
          <div className="text-xs text-text-muted">
            OFSAAI fields are inherited from BD Pack configuration. Edit as needed if different.
          </div>
        </div>
      </details>
    </div>
  )
}
