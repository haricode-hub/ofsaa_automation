'use client'

export interface EcmFormData {
  jdbcUrl: string
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
  'jdbcUrl',
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



export function createDefaultEcmData(configSchemaName: string, atomicSchemaName: string, host: string): EcmFormData {
  return {
    jdbcUrl: '',
    hostname: host || '',
    setupInfoName: 'DEV',
    prefixSchemaName: 'N',
    applySameForAll: 'Y',
    schemaPassword: 'ofsaa8x',
    datafileDir: '/CHANGE_ME/',
    configSchemaName,
    atomicSchemaName,
    prop_base_country: '',
    prop_default_jurisdiction: '',
    prop_smtp_host: '',
    prop_nls_length_semantics: 'BYTE',
    prop_analyst_data_source: '',
    prop_miner_data_source: '',
    prop_configure_obiee: '0',
    prop_fsdf_upload_model: '0',
    prop_amlsource: '',
    prop_kycsource: '',
    prop_cssource: '',
    prop_externalsystemsource: '',
    prop_tbamlsource: '',
    prop_fatcasource: '',
    prop_ofsecm_datasrcname: '',
    prop_comn_gateway_ds: '',
    prop_t2jurl: '',
    prop_j2turl: '',
    prop_cmngtwyurl: '',
    prop_bdurl: '',
    prop_ofss_wls_url: '',
    prop_aai_url: '',
    prop_cs_url: '',
    prop_arachnys_nns_service_url: ''
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

  if (!data.jdbcUrl.startsWith('jdbc:oracle:thin:@')) {
    errors.jdbcUrl = 'JDBC URL must start with jdbc:oracle:thin:@'
  }

  if (!data.datafileDir.startsWith('/')) {
    errors.datafileDir = 'Datafile path must start with /'
  }

  if (!data.datafileDir.startsWith('/CHANGE_ME/')) {
    errors.datafileDir = 'Datafile path must follow BD convention: /CHANGE_ME/...'
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
    onChange({ ...data, [field]: value })
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
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            {input('JDBC_URL', 'jdbcUrl', 'jdbc:oracle:thin:@//dbhost:1521/OFSAAPDB')}
            {input('HOSTNAME', 'hostname', 'app-hostname')}
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
          {input('Datafile Directory Path', 'datafileDir', '/CHANGE_ME/')}
          <div className="text-xs text-text-muted">Datafile path must match BD pack convention (/CHANGE_ME/...).</div>
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
    </div>
  )
}
