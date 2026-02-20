'use client'

export interface BdPackFormData {
  // Main Configuration
  host: string
  username: string
  password: string
  fic_home: string
  java_home: string
  java_bin: string
  oracle_sid: string

  // Schema Creator
  schema_jdbc_host: string
  schema_jdbc_port: string
  schema_jdbc_service: string
  schema_setup_env: string
  schema_apply_same_for_all: string
  schema_default_password: string
  schema_datafile_dir: string
  schema_tablespace_autoextend: string
  schema_external_directory_value: string
  schema_config_schema_name: string
  schema_atomic_schema_name: string

  // Application Pack
  pack_app_enable: Record<string, boolean>

  // Silent Installer (default.properties)
  prop_base_country: string
  prop_default_jurisdiction: string
  prop_smtp_host: string
  prop_partition_date_format: string
  prop_datadumpdt_minus_0: string
  prop_endthisweek_minus_00: string
  prop_startnextmnth_minus_00: string
  prop_analyst_data_source: string
  prop_miner_data_source: string
  prop_nls_length_semantics: string
  prop_web_service_user: string
  prop_web_service_password: string
  prop_configure_obiee: string
  prop_obiee_url: string
  prop_sw_rmiport: string
  prop_big_data_enable: string
  prop_sqoop_working_dir: string
  prop_ssh_auth_alias: string
  prop_ssh_host_name: string
  prop_ssh_port: string
  prop_ecmsource: string
  prop_ecmloadtype: string
  prop_cssource: string
  prop_csloadtype: string
  prop_crrsource: string
  prop_crrloadtype: string
  prop_fsdf_upload_model: string

  // OFSAAI Install Config
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

export const APP_PACK_APPS = [
  { id: 'FACILITYMANAGEMENTPACK', name: 'Facility Management Pack' },
  { id: 'LOANMANAGEMENTPACK', name: 'Loan Management Pack' },
  { id: 'INVESTMENTPACK', name: 'Investment Pack' },
  { id: 'TREASURYMANAGEMENTPACK', name: 'Treasury Management Pack' },
  { id: 'TRADEFINANCEMANAGEMENTPACK', name: 'Trade Finance Management Pack' },
  { id: 'RETAILMANAGEMENTPACK', name: 'Retail Management Pack' },
  { id: 'ASSETMANAGEMENTPACK', name: 'Asset Management Pack' },
  { id: 'CORPORATEACTIONPACK', name: 'Corporate Action Pack' }
]

export function createDefaultBdPackData(host?: string): BdPackFormData {
  return {
    host: host || '',
    username: '',
    password: '',
    fic_home: '/u01/OFSAA/FICHOME',
    java_home: '',
    java_bin: '',
    oracle_sid: 'ORCL',
    schema_jdbc_host: '',
    schema_jdbc_port: '1521',
    schema_jdbc_service: 'OFSAAPDB',
    schema_setup_env: 'DEV',
    schema_apply_same_for_all: 'Y',
    schema_default_password: '',
    schema_datafile_dir: '/u01/app/oracle/oradata/OFSAA/OFSAADB',
    schema_tablespace_autoextend: 'OFF',
    schema_external_directory_value: '/u01/OFSAA/FICHOME/bdf/inbox',
    schema_config_schema_name: 'OFSCONFIG',
    schema_atomic_schema_name: 'OFSATOMIC',
    pack_app_enable: {},
    prop_base_country: 'US',
    prop_default_jurisdiction: 'AMEA',
    prop_smtp_host: '',
    prop_partition_date_format: 'DD-MM-YYYY',
    prop_datadumpdt_minus_0: '10/12/2015',
    prop_endthisweek_minus_00: '19/12/2015',
    prop_startnextmnth_minus_00: '01/01/2016',
    prop_analyst_data_source: 'ANALYST',
    prop_miner_data_source: 'MINER',
    prop_nls_length_semantics: 'CHAR',
    prop_web_service_user: 'oracle',
    prop_web_service_password: '',
    prop_configure_obiee: '0',
    prop_obiee_url: '',
    prop_sw_rmiport: '8204',
    prop_big_data_enable: 'FALSE',
    prop_sqoop_working_dir: '',
    prop_ssh_auth_alias: '',
    prop_ssh_host_name: '',
    prop_ssh_port: '',
    prop_ecmsource: '',
    prop_ecmloadtype: '',
    prop_cssource: '',
    prop_csloadtype: '',
    prop_crrsource: '',
    prop_crrloadtype: '',
    prop_fsdf_upload_model: '1',
    aai_webappservertype: '3',
    aai_dbserver_ip: '',
    aai_oracle_service_name: 'OFSAAPDB',
    aai_abs_driver_path: '',
    aai_olap_server_implementation: '0',
    aai_sftp_enable: '1',
    aai_file_transfer_port: '22',
    aai_javaport: '',
    aai_nativeport: '',
    aai_agentport: '',
    aai_iccport: '',
    aai_iccnativeport: '',
    aai_olapport: '',
    aai_msgport: '',
    aai_routerport: '',
    aai_amport: '',
    aai_https_enable: '1',
    aai_web_server_ip: '',
    aai_web_server_port: '7002',
    aai_context_name: 'FICHOME',
    aai_webapp_context_path: '',
    aai_web_local_path: '',
    aai_weblogic_domain_home: '',
    aai_ftspshare_path: '',
    aai_sftp_user_id: 'oracle',
  }
}

interface BdPackFormProps {
  data: BdPackFormData
  errors: Record<string, string>
  onChange: (data: BdPackFormData) => void
}

export function BdPackForm({ data, errors, onChange }: BdPackFormProps) {
  const handleInputChange = (field: keyof BdPackFormData) => (e: React.ChangeEvent<HTMLInputElement | HTMLSelectElement>) => {
    onChange({ ...data, [field]: e.target.value })
  }

  const togglePackAppEnable = (appId: string) => {
    onChange({
      ...data,
      pack_app_enable: {
        ...data.pack_app_enable,
        [appId]: !data.pack_app_enable[appId]
      }
    })
  }

  return (
    <div className="space-y-6">

      {/* Schema Creator Details */}
      <details className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
              Schema Creator (OFS_BD_SCHEMA_IN.xml)
            </div>
            <div className="text-xs text-text-muted mt-1">
              JDBC, tablespace paths, AUTOEXTEND, schema names.
            </div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>

        <div className="mt-5 space-y-4">
          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              JDBC Host (DB)
            </label>
            <input
              type="text"
              value={data.schema_jdbc_host}
              onChange={handleInputChange('schema_jdbc_host')}
              placeholder="192.168.3.42"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                JDBC Port
              </label>
              <input
                type="text"
                value={data.schema_jdbc_port}
                onChange={handleInputChange('schema_jdbc_port')}
                placeholder="1521"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                JDBC Service/SID
              </label>
              <input
                type="text"
                value={data.schema_jdbc_service}
                onChange={handleInputChange('schema_jdbc_service')}
                placeholder="OFSAAPDB"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              Application IP (HOST Tag Value)
            </label>
            <input
              type="text"
              value={data.host}
              placeholder="192.168.3.41"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              readOnly
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SETUPINFO Name
              </label>
              <input
                type="text"
                value={data.schema_setup_env}
                onChange={handleInputChange('schema_setup_env')}
                placeholder="DEV"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ApplySameForAll (Y/N)
              </label>
              <input
                type="text"
                value={data.schema_apply_same_for_all}
                onChange={handleInputChange('schema_apply_same_for_all')}
                placeholder="Y"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              Default Schema Password
            </label>
            <input
              type="password"
              value={data.schema_default_password}
              onChange={handleInputChange('schema_default_password')}
              placeholder="Password1"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                DATAFILE Base Dir
              </label>
              <input
                type="text"
                value={data.schema_datafile_dir}
                onChange={handleInputChange('schema_datafile_dir')}
                placeholder="/u01/app/oracle/oradata/OFSAA/OFSAADB"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                AUTOEXTEND (ON/OFF)
              </label>
              <input
                type="text"
                value={data.schema_tablespace_autoextend}
                onChange={handleInputChange('schema_tablespace_autoextend')}
                placeholder="OFF"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
              External Directory Value
            </label>
            <input
              type="text"
              value={data.schema_external_directory_value}
              onChange={handleInputChange('schema_external_directory_value')}
              placeholder="/u01/OFSAA/FICHOME/bdf/inbox"
              className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                CONFIG Schema Name
              </label>
              <input
                type="text"
                value={data.schema_config_schema_name}
                onChange={handleInputChange('schema_config_schema_name')}
                placeholder="OFSCONFIG"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ATOMIC Schema Name
              </label>
              <input
                type="text"
                value={data.schema_atomic_schema_name}
                onChange={handleInputChange('schema_atomic_schema_name')}
                placeholder="OFSATOMIC"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>
        </div>
      </details>

      {/* Application Pack Details */}
      <details className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
              Application Pack (OFS_BD_PACK.xml)
            </div>
            <div className="text-xs text-text-muted mt-1">
              Toggle apps to set `ENABLE=\"YES\"` (off = empty).
            </div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>

        <div className="mt-5 grid grid-cols-1 lg:grid-cols-2 gap-3">
          {APP_PACK_APPS.map(app => {
            const enabled = !!data.pack_app_enable[app.id]
            return (
              <button
                key={app.id}
                type="button"
                onClick={() => togglePackAppEnable(app.id)}
                aria-pressed={enabled}
                className="text-left rounded-lg border border-border bg-bg-secondary/40 hover:bg-bg-tertiary/40 transition-colors px-4 py-3 flex items-center justify-between gap-4"
              >
                <div className="min-w-0">
                  <div className="text-xs font-mono text-text-muted">{app.id}</div>
                  <div className="text-sm text-text-primary truncate">{app.name}</div>
                </div>
                <div className="shrink-0 flex items-center gap-2">
                  <span className={`text-xs font-bold tracking-widest ${enabled ? 'text-success' : 'text-text-muted'}`}>
                    {enabled ? 'YES' : 'OFF'}
                  </span>
                  <span
                    className={`h-6 w-6 rounded-md border flex items-center justify-center transition-colors ${
                      enabled ? 'bg-white text-black border-white' : 'bg-transparent text-transparent border-border'
                    }`}
                    aria-hidden="true"
                  >
                    <svg viewBox="0 0 24 24" className="h-4 w-4" fill="none" stroke="currentColor" strokeWidth="3">
                      <path strokeLinecap="round" strokeLinejoin="round" d="M5 13l4 4L19 7" />
                    </svg>
                  </span>
                </div>
              </button>
            )
          })}
        </div>
      </details>

      {/* Silent Installer Details */}
      <details className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
              Silent Installer (default.properties)
            </div>
            <div className="text-xs text-text-muted mt-1">
              User input section only (above `FSDF_UPLOAD_MODEL`).
            </div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>

        <div className="mt-5 space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                BASE_COUNTRY
              </label>
              <input
                type="text"
                value={data.prop_base_country}
                onChange={handleInputChange('prop_base_country')}
                placeholder="US"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                DEFAULT_JURISDICTION
              </label>
              <input
                type="text"
                value={data.prop_default_jurisdiction}
                onChange={handleInputChange('prop_default_jurisdiction')}
                placeholder="AMEA"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SMTP_HOST
              </label>
              <input
                type="text"
                value={data.prop_smtp_host}
                onChange={handleInputChange('prop_smtp_host')}
                placeholder="192.168.3.41"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                PARTITION_DATE_FORMAT
              </label>
              <input
                type="text"
                value={data.prop_partition_date_format}
                onChange={handleInputChange('prop_partition_date_format')}
                placeholder="DD-MM-YYYY"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                DATADUMPDT_MINUS_0
              </label>
              <input
                type="text"
                value={data.prop_datadumpdt_minus_0}
                onChange={handleInputChange('prop_datadumpdt_minus_0')}
                placeholder="10/12/2015"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ENDTHISWEEK_MINUS_00
              </label>
              <input
                type="text"
                value={data.prop_endthisweek_minus_00}
                onChange={handleInputChange('prop_endthisweek_minus_00')}
                placeholder="19/12/2015"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                STARTNEXTMNTH_MINUS_00
              </label>
              <input
                type="text"
                value={data.prop_startnextmnth_minus_00}
                onChange={handleInputChange('prop_startnextmnth_minus_00')}
                placeholder="01/01/2016"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ANALYST_DATA_SOURCE
              </label>
              <input
                type="text"
                value={data.prop_analyst_data_source}
                onChange={handleInputChange('prop_analyst_data_source')}
                placeholder="ANALYST"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                MINER_DATA_SOURCE
              </label>
              <input
                type="text"
                value={data.prop_miner_data_source}
                onChange={handleInputChange('prop_miner_data_source')}
                placeholder="MINER"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                NLS_LENGTH_SEMANTICS
              </label>
              <input
                type="text"
                value={data.prop_nls_length_semantics}
                onChange={handleInputChange('prop_nls_length_semantics')}
                placeholder="CHAR"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                WEB_SERVICE_USER
              </label>
              <input
                type="text"
                value={data.prop_web_service_user}
                onChange={handleInputChange('prop_web_service_user')}
                placeholder="oracle"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                WEB_SERVICE_PASSWORD
              </label>
              <input
                type="password"
                value={data.prop_web_service_password}
                onChange={handleInputChange('prop_web_service_password')}
                placeholder="Oracle@123"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                CONFIGURE_OBIEE
              </label>
              <input
                type="text"
                value={data.prop_configure_obiee}
                onChange={handleInputChange('prop_configure_obiee')}
                placeholder="0"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                OBIEE_URL (optional)
              </label>
              <input
                type="text"
                value={data.prop_obiee_url}
                onChange={handleInputChange('prop_obiee_url')}
                placeholder="(empty allowed)"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SW_RMIPORT
              </label>
              <input
                type="text"
                value={data.prop_sw_rmiport}
                onChange={handleInputChange('prop_sw_rmiport')}
                placeholder="8204"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                BIG_DATA_ENABLE
              </label>
              <input
                type="text"
                value={data.prop_big_data_enable}
                onChange={handleInputChange('prop_big_data_enable')}
                placeholder="FALSE"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SQOOP_WORKING_DIR
              </label>
              <input type="text" value={data.prop_sqoop_working_dir} onChange={handleInputChange('prop_sqoop_working_dir')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SSH_AUTH_ALIAS
              </label>
              <input type="text" value={data.prop_ssh_auth_alias} onChange={handleInputChange('prop_ssh_auth_alias')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SSH_HOST_NAME
              </label>
              <input type="text" value={data.prop_ssh_host_name} onChange={handleInputChange('prop_ssh_host_name')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                SSH_PORT
              </label>
              <input type="text" value={data.prop_ssh_port} onChange={handleInputChange('prop_ssh_port')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ECMSOURCE
              </label>
              <input type="text" value={data.prop_ecmsource} onChange={handleInputChange('prop_ecmsource')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                ECMLOADTYPE
              </label>
              <input type="text" value={data.prop_ecmloadtype} onChange={handleInputChange('prop_ecmloadtype')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                CSSOURCE
              </label>
              <input type="text" value={data.prop_cssource} onChange={handleInputChange('prop_cssource')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                CSLOADTYPE
              </label>
              <input type="text" value={data.prop_csloadtype} onChange={handleInputChange('prop_csloadtype')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                CRRSOURCE
              </label>
              <input type="text" value={data.prop_crrsource} onChange={handleInputChange('prop_crrsource')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                CRRLOADTYPE
              </label>
              <input type="text" value={data.prop_crrloadtype} onChange={handleInputChange('prop_crrloadtype')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                FSDF_UPLOAD_MODEL
              </label>
              <input type="text" value={data.prop_fsdf_upload_model} onChange={handleInputChange('prop_fsdf_upload_model')} placeholder="1" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>
        </div>
      </details>

      {/* OFSAAI Install Config Details */}
      <details className="group rounded-xl border border-border bg-bg-secondary/20 p-4">
        <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
          <div>
            <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
              OFSAAI Install (OFSAAI_InstallConfig.xml)
            </div>
            <div className="text-xs text-text-muted mt-1">
              Web server, DB, SFTP and port configuration.
            </div>
          </div>
          <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
          <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
        </summary>

        <div className="mt-5 space-y-5">
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEBAPPSERVERTYPE</label>
              <input type="text" value={data.aai_webappservertype} onChange={handleInputChange('aai_webappservertype')} placeholder="3" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">DBSERVER_IP</label>
              <input type="text" value={data.aai_dbserver_ip} onChange={handleInputChange('aai_dbserver_ip')} placeholder="192.168.3.42" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">ORACLE SERVICE</label>
              <input type="text" value={data.aai_oracle_service_name} onChange={handleInputChange('aai_oracle_service_name')} placeholder="OFSAAPDB" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">ABS_DRIVER_PATH</label>
              <input type="text" value={data.aai_abs_driver_path} onChange={handleInputChange('aai_abs_driver_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEB_SERVER_IP</label>
              <input type="text" value={data.aai_web_server_ip} onChange={handleInputChange('aai_web_server_ip')} placeholder="192.168.3.41" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">HTTPS_ENABLE</label>
              <input type="text" value={data.aai_https_enable} onChange={handleInputChange('aai_https_enable')} placeholder="1" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEB_SERVER_PORT</label>
              <input type="text" value={data.aai_web_server_port} onChange={handleInputChange('aai_web_server_port')} placeholder="7002" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">CONTEXT_NAME</label>
              <input type="text" value={data.aai_context_name} onChange={handleInputChange('aai_context_name')} placeholder="FICHOME" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">OLAP_IMPL</label>
              <input type="text" value={data.aai_olap_server_implementation} onChange={handleInputChange('aai_olap_server_implementation')} placeholder="0" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEBAPP_CONTEXT_PATH</label>
            <input type="text" value={data.aai_webapp_context_path} onChange={handleInputChange('aai_webapp_context_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEB_LOCAL_PATH</label>
              <input type="text" value={data.aai_web_local_path} onChange={handleInputChange('aai_web_local_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEBLOGIC_DOMAIN_HOME</label>
              <input type="text" value={data.aai_weblogic_domain_home} onChange={handleInputChange('aai_weblogic_domain_home')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>

          <div className="grid grid-cols-2 lg:grid-cols-5 gap-3">
            {[
              ['JAVAPORT', 'aai_javaport'],
              ['NATIVEPORT', 'aai_nativeport'],
              ['AGENTPORT', 'aai_agentport'],
              ['ICCPORT', 'aai_iccport'],
              ['ICCNATIVE', 'aai_iccnativeport'],
              ['OLAPPORT', 'aai_olapport'],
              ['MSGPORT', 'aai_msgport'],
              ['ROUTERPORT', 'aai_routerport'],
              ['AMPORT', 'aai_amport']
            ].map(([label, field]) => (
              <div key={label} className="space-y-2">
                <label className="text-[10px] font-bold text-text-primary uppercase tracking-wider">{label}</label>
                <input
                  type="text"
                  value={(data as any)[field]}
                  onChange={handleInputChange(field as any)}
                  className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                />
              </div>
            ))}
          </div>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">SFTP_ENABLE</label>
              <input type="text" value={data.aai_sftp_enable} onChange={handleInputChange('aai_sftp_enable')} placeholder="1" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">FILE_TRANSFER_PORT</label>
              <input type="text" value={data.aai_file_transfer_port} onChange={handleInputChange('aai_file_transfer_port')} placeholder="22" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">OFSAAI_SFTP_USER_ID</label>
              <input type="text" value={data.aai_sftp_user_id} onChange={handleInputChange('aai_sftp_user_id')} placeholder="oracle" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
            </div>
          </div>

          <div className="space-y-2">
            <label className="text-xs font-bold text-text-primary uppercase tracking-wider">OFSAAI_FTPSHARE_PATH</label>
            <input type="text" value={data.aai_ftspshare_path} onChange={handleInputChange('aai_ftspshare_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
          </div>
        </div>
      </details>
    </div>
  )
}

export function validateBdPackData(data: BdPackFormData): { isValid: boolean; errors: Record<string, string> } {
  const errors: Record<string, string> = {}

  if (!data.host?.trim()) errors.host = 'Target host is required'
  if (!data.username?.trim()) errors.username = 'SSH username is required'
  if (!data.password?.trim()) errors.password = 'SSH password is required'
  if (!data.fic_home?.trim()) errors.fic_home = 'FIC_HOME path is required'

  return {
    isValid: Object.keys(errors).length === 0,
    errors,
  }
}
