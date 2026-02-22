'use client'

import { useCallback, useEffect, useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import {
  ServerIcon,
  UserIcon,
  KeyIcon,
  RocketLaunchIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'
import { EcmPackPage } from '@/components/EcmPackPage'
import { EcmFormData } from '@/components/EcmPackForm'

interface InstallationData {
  host: string
  username: string
  password: string
  // Profile variables
  fic_home: string
  java_home: string
  java_bin: string
  oracle_sid: string

  // OFS_BD_SCHEMA_IN.xml inputs
  schema_jdbc_host: string
  schema_jdbc_port: string
  schema_jdbc_service: string
  schema_host: string
  schema_setup_env: string
  schema_apply_same_for_all: string
  schema_default_password: string
  schema_datafile_dir: string
  schema_tablespace_autoextend: string
  schema_external_directory_value: string
  schema_config_schema_name: string
  schema_atomic_schema_name: string

  // OFS_BD_PACK.xml inputs: APP_ID -> enabled
  pack_app_enable: Record<string, boolean>

  // default.properties inputs
  prop_base_country: string
  prop_default_jurisdiction: string
  prop_smtp_host: string
  prop_partition_date_format: string
  prop_datadumpdt_minus_0: string
  prop_endthisweek_minus_00: string
  prop_startnextmnth_minus_00: string
  prop_analyst_data_source: string
  prop_miner_data_source: string
  prop_web_service_user: string
  prop_web_service_password: string
  prop_nls_length_semantics: string
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

  // OFSAAI_InstallConfig.xml inputs
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
  installation_mode: 'fresh' | 'addon'
  install_bdpack: boolean
  install_ecm: boolean
}

const APP_PACK_APPS: Array<{ id: string; name: string }> = [
  { id: 'OFS_AAI', name: 'Financial Services Analytical Applications Infrastructure' },
  { id: 'OFS_IPE', name: 'Financial Services Inline Processing Engine' },
  { id: 'OFS_AML', name: 'Financial Services Anti Money Laundering' },
  { id: 'OFS_FRAUD', name: 'Financial Services Fraud' },
  { id: 'OFS_FRAUD_EE', name: 'Financial Services Fraud Enterprise Edition' },
  { id: 'OFS_TC', name: 'Financial Services Trader Compliance' },
  { id: 'OFS_TB', name: 'Financial Services Trade Blotter' },
  { id: 'OFS_PTA', name: 'Financial Services Personal Trading Approval' },
  { id: 'OFS_BC', name: 'Financial Services Broker Compliance' },
  { id: 'OFS_ECTC', name: 'Financial Services Energy and Commodity Trading Compliance' },
  { id: 'OFS_KYC', name: 'Financial Services Know Your Customer' },
  { id: 'OFS_CTR', name: 'Financial Services Currency Transaction Reporting' },
  { id: 'OFS_FATCA', name: 'Financial Services Foreign Account Tax Compliance Act Management' },
  { id: 'OFS_CRSR', name: 'Financial Services Common Reporting Standard' },
  { id: 'OFS_AAIB', name: 'Financial Services Analytical Applications Infrastructure Big Data Processing' }
]

const INSTALL_FORM_STORAGE_KEY = 'ofsaa_install_form_v1'

export function InstallationForm() {
  const router = useRouter()
  const [formData, setFormData] = useState<InstallationData>({
    host: '',
    username: '',
    password: '',
    // Profile variables with defaults
    fic_home: '/u01/OFSAA/FICHOME',
    java_home: '', // Will be auto-detected if empty
    java_bin: '', // Will be auto-detected if empty
    oracle_sid: 'ORCL',

    schema_jdbc_host: '',
    schema_jdbc_port: '1521',
    schema_jdbc_service: '',
    schema_host: '',
    schema_setup_env: 'DEV',
    schema_apply_same_for_all: 'Y',
    schema_default_password: '',
    schema_datafile_dir: '/u01/app/oracle/oradata/OFSAA/OFSAADB',
    schema_tablespace_autoextend: 'OFF',
    schema_external_directory_value: '/u01/OFSAA/FICHOME/bdf/inbox',
    schema_config_schema_name: 'OFSCONFIG',
    schema_atomic_schema_name: 'OFSATOMIC',

    pack_app_enable: {
      OFS_AAI: true,
      OFS_IPE: true,
      OFS_AML: true,
      OFS_FRAUD: true,
      OFS_FRAUD_EE: true,
      OFS_TC: false,
      OFS_TB: false,
      OFS_PTA: false,
      OFS_BC: false,
      OFS_ECTC: false,
      OFS_KYC: true,
      OFS_CTR: false,
      OFS_FATCA: false,
      OFS_CRSR: false,
      OFS_AAIB: false
    },

    prop_base_country: 'US',
    prop_default_jurisdiction: 'AMEA',
    prop_smtp_host: '',
    prop_partition_date_format: 'DD-MM-YYYY',
    prop_datadumpdt_minus_0: '10/12/2015',
    prop_endthisweek_minus_00: '19/12/2015',
    prop_startnextmnth_minus_00: '01/01/2016',
    prop_analyst_data_source: 'ANALYST',
    prop_miner_data_source: 'MINER',
    prop_web_service_user: 'oracle',
    prop_web_service_password: '',
    prop_nls_length_semantics: 'CHAR',
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
    aai_oracle_service_name: '',
    aai_abs_driver_path: '/u01/app/oracle/product/19.0.0/client_1/jdbc/lib',
    aai_olap_server_implementation: '0',
    aai_sftp_enable: '1',
    aai_file_transfer_port: '22',
    aai_javaport: '9999',
    aai_nativeport: '6666',
    aai_agentport: '6510',
    aai_iccport: '6507',
    aai_iccnativeport: '6509',
    aai_olapport: '10101',
    aai_msgport: '6501',
    aai_routerport: '6502',
    aai_amport: '6506',
    aai_https_enable: '1',
    aai_web_server_ip: '',
    aai_web_server_port: '7002',
    aai_context_name: 'FICHOME',
    aai_webapp_context_path: '/u01/Oracle/Middleware/Oracle_Home/wlserver',
    aai_web_local_path: '/u01/OFSAA/FTPSHARE',
    aai_weblogic_domain_home: '/u01/Oracle/Middleware/Oracle_Home/user_projects/domains/DEMO_OFSAA_DOMAIN',
    aai_ftspshare_path: '/u01/OFSAA/FTPSHARE',
    aai_sftp_user_id: 'oracle',
    installation_mode: 'fresh',
    install_bdpack: false,
    install_ecm: false
  })
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [ecmConfig, setEcmConfig] = useState<EcmFormData | null>(null)
  const [isEcmValid, setIsEcmValid] = useState(true)
  const [ecmSubmitError, setEcmSubmitError] = useState('')

  useEffect(() => {
    try {
      const raw = localStorage.getItem(INSTALL_FORM_STORAGE_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw) as {
        formData?: Partial<InstallationData>
        ecmConfig?: EcmFormData | null
      }
      if (parsed.formData) {
        setFormData(prev => ({ ...prev, ...parsed.formData }))
      }
      if (parsed.ecmConfig !== undefined) {
        setEcmConfig(parsed.ecmConfig)
      }
    } catch {
      // Ignore local storage parse errors
    }
  }, [])

  useEffect(() => {
    try {
      localStorage.setItem(
        INSTALL_FORM_STORAGE_KEY,
        JSON.stringify({
          formData,
          ecmConfig,
        })
      )
    } catch {
      // Ignore local storage write errors
    }
  }, [formData, ecmConfig])

  const handleEcmChange = useCallback((data: EcmFormData, valid: boolean) => {
    setEcmConfig(data)
    setIsEcmValid(valid)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setEcmSubmitError('')
    if (formData.install_bdpack) {
      // BD Pack validation would go here
    }
    
    if (formData.install_ecm && (!ecmConfig || !isEcmValid)) {
      setStatus('error')
      setEcmSubmitError('ECM review is blocked by validation errors. Fix ECM fields before deployment.')
      return
    }
    setIsLoading(true)
    
    try {
      // Call backend API to start installation
      const response = await fetch('http://localhost:8000/api/installation/start', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          host: formData.host,
          username: formData.username,
          password: formData.password,
          fic_home: formData.fic_home,
          java_home: formData.java_home || null,
          java_bin: formData.java_bin || null,
          oracle_sid: formData.oracle_sid,

          schema_jdbc_host: formData.schema_jdbc_host,
          schema_jdbc_port: formData.schema_jdbc_port ? Number(formData.schema_jdbc_port) : null,
          schema_jdbc_service: formData.schema_jdbc_service,
          schema_host: (formData.schema_host || formData.host),
          schema_setup_env: formData.schema_setup_env,
          schema_apply_same_for_all: formData.schema_apply_same_for_all,
          schema_default_password: formData.schema_default_password,
          schema_datafile_dir: formData.schema_datafile_dir,
          schema_tablespace_autoextend: formData.schema_tablespace_autoextend,
          schema_external_directory_value: formData.schema_external_directory_value,
          schema_config_schema_name: formData.schema_config_schema_name,
          schema_atomic_schema_name: formData.schema_atomic_schema_name,

          pack_app_enable: formData.pack_app_enable,

          prop_base_country: formData.prop_base_country,
          prop_default_jurisdiction: formData.prop_default_jurisdiction,
          prop_smtp_host: formData.prop_smtp_host,
          prop_partition_date_format: formData.prop_partition_date_format,
          prop_datadumpdt_minus_0: formData.prop_datadumpdt_minus_0,
          prop_endthisweek_minus_00: formData.prop_endthisweek_minus_00,
          prop_startnextmnth_minus_00: formData.prop_startnextmnth_minus_00,
          prop_analyst_data_source: formData.prop_analyst_data_source,
          prop_miner_data_source: formData.prop_miner_data_source,
          prop_web_service_user: formData.prop_web_service_user,
          prop_web_service_password: formData.prop_web_service_password,
          prop_nls_length_semantics: formData.prop_nls_length_semantics,
          prop_configure_obiee: formData.prop_configure_obiee,
          prop_obiee_url: formData.prop_obiee_url, // may be empty
          prop_sw_rmiport: formData.prop_sw_rmiport,
          prop_big_data_enable: formData.prop_big_data_enable,
          prop_sqoop_working_dir: formData.prop_sqoop_working_dir,
          prop_ssh_auth_alias: formData.prop_ssh_auth_alias,
          prop_ssh_host_name: formData.prop_ssh_host_name,
          prop_ssh_port: formData.prop_ssh_port,
          prop_ecmsource: formData.prop_ecmsource,
          prop_ecmloadtype: formData.prop_ecmloadtype,
          prop_cssource: formData.prop_cssource,
          prop_csloadtype: formData.prop_csloadtype,
          prop_crrsource: formData.prop_crrsource,
          prop_crrloadtype: formData.prop_crrloadtype,
          prop_fsdf_upload_model: formData.prop_fsdf_upload_model,

          aai_webappservertype: formData.aai_webappservertype,
          aai_dbserver_ip: formData.aai_dbserver_ip,
          aai_oracle_service_name: formData.aai_oracle_service_name,
          aai_abs_driver_path: formData.aai_abs_driver_path,
          aai_olap_server_implementation: formData.aai_olap_server_implementation,
          aai_sftp_enable: formData.aai_sftp_enable,
          aai_file_transfer_port: formData.aai_file_transfer_port,
          aai_javaport: formData.aai_javaport,
          aai_nativeport: formData.aai_nativeport,
          aai_agentport: formData.aai_agentport,
          aai_iccport: formData.aai_iccport,
          aai_iccnativeport: formData.aai_iccnativeport,
          aai_olapport: formData.aai_olapport,
          aai_msgport: formData.aai_msgport,
          aai_routerport: formData.aai_routerport,
          aai_amport: formData.aai_amport,
          aai_https_enable: formData.aai_https_enable,
          aai_web_server_ip: formData.aai_web_server_ip,
          aai_web_server_port: formData.aai_web_server_port,
          aai_context_name: formData.aai_context_name,
          aai_webapp_context_path: formData.aai_webapp_context_path,
          aai_web_local_path: formData.aai_web_local_path,
          aai_weblogic_domain_home: formData.aai_weblogic_domain_home,
          aai_ftspshare_path: formData.aai_ftspshare_path,
          aai_sftp_user_id: formData.aai_sftp_user_id,
          installation_mode: formData.installation_mode,
          install_bdpack: formData.install_bdpack,
          install_ecm: formData.install_ecm,
          // Flatten ECM config fields for backend
          ...(formData.install_ecm && ecmConfig ? {
            // Schema configuration fields
            ecm_schema_jdbc_host: ecmConfig.jdbc_host,
            ecm_schema_jdbc_port: ecmConfig.jdbc_port ? Number(ecmConfig.jdbc_port) : 1521,
            ecm_schema_jdbc_service: ecmConfig.jdbc_service,
            ecm_schema_host: ecmConfig.hostname,
            ecm_schema_setup_env: ecmConfig.setupInfoName,
            ecm_schema_prefix_schema_name: ecmConfig.prefixSchemaName,
            ecm_schema_apply_same_for_all: ecmConfig.applySameForAll,
            ecm_schema_default_password: ecmConfig.schemaPassword,
            ecm_schema_datafile_dir: ecmConfig.datafileDir,
            ecm_schema_config_schema_name: ecmConfig.configSchemaName,
            ecm_schema_atomic_schema_name: ecmConfig.atomicSchemaName,
            // Properties (default.properties) fields
            ecm_prop_base_country: ecmConfig.prop_base_country,
            ecm_prop_default_jurisdiction: ecmConfig.prop_default_jurisdiction,
            ecm_prop_smtp_host: ecmConfig.prop_smtp_host,
            ecm_prop_web_service_user: ecmConfig.prop_web_service_user,
            ecm_prop_web_service_password: ecmConfig.prop_web_service_password,
            ecm_prop_nls_length_semantics: ecmConfig.prop_nls_length_semantics,
            ecm_prop_analyst_data_source: ecmConfig.prop_analyst_data_source,
            ecm_prop_miner_data_source: ecmConfig.prop_miner_data_source,
            ecm_prop_configure_obiee: ecmConfig.prop_configure_obiee,
            ecm_prop_fsdf_upload_model: ecmConfig.prop_fsdf_upload_model,
            ecm_prop_amlsource: ecmConfig.prop_amlsource,
            ecm_prop_kycsource: ecmConfig.prop_kycsource,
            ecm_prop_cssource: ecmConfig.prop_cssource,
            ecm_prop_externalsystemsource: ecmConfig.prop_externalsystemsource,
            ecm_prop_tbamlsource: ecmConfig.prop_tbamlsource,
            ecm_prop_fatcasource: ecmConfig.prop_fatcasource,
            ecm_prop_ofsecm_datasrcname: ecmConfig.prop_ofsecm_datasrcname,
            ecm_prop_comn_gateway_ds: ecmConfig.prop_comn_gateway_ds,
            ecm_prop_t2jurl: ecmConfig.prop_t2jurl,
            ecm_prop_j2turl: ecmConfig.prop_j2turl,
            ecm_prop_cmngtwyurl: ecmConfig.prop_cmngtwyurl,
            ecm_prop_bdurl: ecmConfig.prop_bdurl,
            ecm_prop_ofss_wls_url: ecmConfig.prop_ofss_wls_url,
            ecm_prop_aai_url: ecmConfig.prop_aai_url,
            ecm_prop_cs_url: ecmConfig.prop_cs_url,
            ecm_prop_arachnys_nns_service_url: ecmConfig.prop_arachnys_nns_service_url,
            // OFSAAI configuration fields (OFSAAI_InstallConfig.xml)
            ecm_aai_webappservertype: ecmConfig.aai_webappservertype,
            ecm_aai_dbserver_ip: ecmConfig.aai_dbserver_ip,
            ecm_aai_oracle_service_name: ecmConfig.aai_oracle_service_name,
            ecm_aai_abs_driver_path: ecmConfig.aai_abs_driver_path,
            ecm_aai_olap_server_implementation: ecmConfig.aai_olap_server_implementation,
            ecm_aai_sftp_enable: ecmConfig.aai_sftp_enable,
            ecm_aai_file_transfer_port: ecmConfig.aai_file_transfer_port,
            ecm_aai_javaport: ecmConfig.aai_javaport,
            ecm_aai_nativeport: ecmConfig.aai_nativeport,
            ecm_aai_agentport: ecmConfig.aai_agentport,
            ecm_aai_iccport: ecmConfig.aai_iccport,
            ecm_aai_iccnativeport: ecmConfig.aai_iccnativeport,
            ecm_aai_olapport: ecmConfig.aai_olapport,
            ecm_aai_msgport: ecmConfig.aai_msgport,
            ecm_aai_routerport: ecmConfig.aai_routerport,
            ecm_aai_amport: ecmConfig.aai_amport,
            ecm_aai_https_enable: ecmConfig.aai_https_enable,
            ecm_aai_web_server_ip: ecmConfig.aai_web_server_ip,
            ecm_aai_web_server_port: ecmConfig.aai_web_server_port,
            ecm_aai_context_name: ecmConfig.aai_context_name,
            ecm_aai_webapp_context_path: ecmConfig.aai_webapp_context_path,
            ecm_aai_web_local_path: ecmConfig.aai_web_local_path,
            ecm_aai_weblogic_domain_home: ecmConfig.aai_weblogic_domain_home,
            ecm_aai_ftspshare_path: ecmConfig.aai_ftspshare_path,
            ecm_aai_sftp_user_id: ecmConfig.aai_sftp_user_id
          } : {})
        })
      })
      
      if (!response.ok) {
        throw new Error(`HTTP error! status: ${response.status}`)
      }
      
      const result = await response.json()
      console.log('Installation started:', result)
      
      // Navigate to logs page instead of showing inline logs
      router.push(`/logs/${result.task_id}`)
      
    } catch (error) {
      console.error('Installation failed:', error)
      setStatus('error')
      setIsLoading(false)
      
      setTimeout(() => {
        setStatus('idle')
      }, 5000)
    }
  }

  const handleInputChange = (field: keyof InstallationData) => (
    e: React.ChangeEvent<HTMLInputElement>
  ) => {
    const value = e.target.value
    setFormData(prev => {
      const updated = { ...prev, [field]: value }
      // Auto-populate schema_jdbc_host when aai_dbserver_ip is changed
      if (field === 'aai_dbserver_ip' && value) {
        updated.schema_jdbc_host = value
      }
      return updated
    })
  }

  const togglePackAppEnable = (appId: string) => {
    setFormData(prev => ({
      ...prev,
      pack_app_enable: {
        ...prev.pack_app_enable,
        [appId]: !prev.pack_app_enable[appId]
      }
    }))
  }

  const toggleModuleSelection = (field: 'install_bdpack' | 'install_ecm') => {
    setFormData(prev => ({ ...prev, [field]: !prev[field] }))
  }

  const getButtonText = () => {
    if (isLoading) return 'Initializing...'
    if (status === 'success') return 'Installation Complete'
    if (status === 'error') return 'Connection Failed'
    return 'Deploy Installation'
  }

  const getButtonIcon = () => {
    if (isLoading) return <ArrowPathIcon className="w-4 h-4 animate-spin" />
    if (status === 'success') return <CheckCircleIcon className="w-4 h-4" />
    if (status === 'error') return <ExclamationCircleIcon className="w-4 h-4" />
    return <RocketLaunchIcon className="w-4 h-4" />
  }

  const getButtonClass = () => {
    const baseClass = "w-full relative overflow-hidden rounded-lg px-6 py-4 font-bold text-sm tracking-wide transition-all duration-300 disabled:cursor-not-allowed flex items-center justify-center gap-3"
    
    if (status === 'success') {
      return baseClass + ' bg-success text-black'
    }
    if (status === 'error') {
      return baseClass + ' bg-error text-white'
    }
    if (isLoading) {
      return baseClass + ' bg-bg-tertiary text-text-muted cursor-wait'
    }
    
    return baseClass + ' bg-white text-black hover:bg-gray-200 active:scale-98'
  }

  return (
    <div className="space-y-6">
      <form onSubmit={handleSubmit} className="space-y-6">
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.08 }}
        >
          <div className="text-sm font-bold text-text-primary uppercase tracking-wider mb-3">
            Module Installation Scenario
          </div>
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                Installation Mode
              </label>
              <select
                value={formData.installation_mode}
                onChange={e =>
                  setFormData(prev => ({ ...prev, installation_mode: e.target.value as 'fresh' | 'addon' }))
                }
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary"
              >
                <option value="fresh">Fresh</option>
                <option value="addon">Add-on</option>
              </select>
            </div>
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                Optional Modules
              </label>
              <div className="flex items-center gap-5 pt-2">
                <label className="inline-flex items-center gap-2 text-sm text-text-primary cursor-pointer">
                  <input type="checkbox" checked={formData.install_bdpack} onChange={() => toggleModuleSelection('install_bdpack')} />
                  BD Pack
                </label>
                <label className="inline-flex items-center gap-2 text-sm text-text-primary cursor-pointer">
                  <input type="checkbox" checked={formData.install_ecm} onChange={() => toggleModuleSelection('install_ecm')} />
                  ECM
                </label>
              </div>
            </div>
          </div>
        </motion.div>

        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <details open className="group">
            <summary className="list-none cursor-pointer select-none flex items-center justify-between gap-3">
              <div>
                <div className="text-sm font-bold text-text-primary uppercase tracking-wider">
                  Main Configuration
                </div>
                <div className="text-xs text-text-muted mt-1">
                  Host access and profile defaults.
                </div>
              </div>
              <div className="text-xs font-mono text-text-muted group-open:hidden">OPEN</div>
              <div className="text-xs font-mono text-text-muted hidden group-open:block">CLOSE</div>
            </summary>

            <div className="mt-5 space-y-4">
              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
                  <ServerIcon className="w-4 h-4" />
                  Target Host
                </label>
                <input
                  type="text"
                  value={formData.host}
                  onChange={handleInputChange('host')}
                  placeholder="192.168.1.100"
                  className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
                  <UserIcon className="w-4 h-4" />
                  SSH Username
                </label>
                <input
                  type="text"
                  value={formData.username}
                  onChange={handleInputChange('username')}
                  placeholder="oracle"
                  className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                  required
                />
              </div>

              <div className="space-y-2">
                <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
                  <KeyIcon className="w-4 h-4" />
                  SSH Password
                </label>
                <input
                  type="password"
                  value={formData.password}
                  onChange={handleInputChange('password')}
                  placeholder="********"
                  className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                  required
                />
              </div>

              <div className="border-t border-border pt-6 space-y-4">
                <div className="text-sm font-bold text-text-primary uppercase tracking-wider mb-1">
                  Profile Configuration
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    FIC_HOME Path
                  </label>
                  <input
                    type="text"
                    value={formData.fic_home}
                    onChange={handleInputChange('fic_home')}
                    placeholder="/u01/OFSAA/FICHOME"
                    className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                    required
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    JAVA_HOME (Optional - Auto-detected if empty)
                  </label>
                  <input
                    type="text"
                    value={formData.java_home}
                    onChange={handleInputChange('java_home')}
                    placeholder="Leave empty for auto-detection"
                    className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    JAVA_BIN (Optional - Auto-detected if empty)
                  </label>
                  <input
                    type="text"
                    value={formData.java_bin}
                    onChange={handleInputChange('java_bin')}
                    placeholder="Leave empty for auto-detection"
                    className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                  />
                </div>

                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    Oracle SID
                  </label>
                  <input
                    type="text"
                    value={formData.oracle_sid}
                    onChange={handleInputChange('oracle_sid')}
                    placeholder="ORCL"
                    className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                    required
                  />
                </div>
              </div>
            </div>
          </details>
        </motion.div>

        {/* Schema Config Section - BD Pack Only */}
        {formData.install_bdpack && (
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.45 }}
        >
          <details open className="group">
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
              value={formData.schema_jdbc_host}
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
                value={formData.schema_jdbc_port}
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
                value={formData.schema_jdbc_service}
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
              value={formData.host}
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
                value={formData.schema_setup_env}
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
                value={formData.schema_apply_same_for_all}
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
              value={formData.schema_default_password}
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
                value={formData.schema_datafile_dir}
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
                value={formData.schema_tablespace_autoextend}
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
              value={formData.schema_external_directory_value}
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
                value={formData.schema_config_schema_name}
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
                value={formData.schema_atomic_schema_name}
                onChange={handleInputChange('schema_atomic_schema_name')}
                placeholder="OFSATOMIC"
                className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
              />
            </div>
          </div>
            </div>
          </details>
        </motion.div>
        )}

        {/* App Pack Config Section - BD Pack Only */}
        {formData.install_bdpack && (
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
        >
          <details open className="group">
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
                const enabled = !!formData.pack_app_enable[app.id]
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
        </motion.div>
        )}

        {/* Silent Installer Section - BD Pack Only */}
        {formData.install_bdpack && (
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.55 }}
        >
          <details className="group">
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
                    value={formData.prop_base_country}
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
                    value={formData.prop_default_jurisdiction}
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
                    value={formData.prop_smtp_host}
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
                    value={formData.prop_partition_date_format}
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
                    value={formData.prop_datadumpdt_minus_0}
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
                    value={formData.prop_endthisweek_minus_00}
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
                    value={formData.prop_startnextmnth_minus_00}
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
                    value={formData.prop_analyst_data_source}
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
                    value={formData.prop_miner_data_source}
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
                    value={formData.prop_nls_length_semantics}
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
                    value={formData.prop_web_service_user}
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
                    value={formData.prop_web_service_password}
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
                    value={formData.prop_configure_obiee}
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
                    value={formData.prop_obiee_url}
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
                    value={formData.prop_sw_rmiport}
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
                    value={formData.prop_big_data_enable}
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
                  <input type="text" value={formData.prop_sqoop_working_dir} onChange={handleInputChange('prop_sqoop_working_dir')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    SSH_AUTH_ALIAS
                  </label>
                  <input type="text" value={formData.prop_ssh_auth_alias} onChange={handleInputChange('prop_ssh_auth_alias')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    SSH_HOST_NAME
                  </label>
                  <input type="text" value={formData.prop_ssh_host_name} onChange={handleInputChange('prop_ssh_host_name')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    SSH_PORT
                  </label>
                  <input type="text" value={formData.prop_ssh_port} onChange={handleInputChange('prop_ssh_port')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    ECMSOURCE
                  </label>
                  <input type="text" value={formData.prop_ecmsource} onChange={handleInputChange('prop_ecmsource')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    ECMLOADTYPE
                  </label>
                  <input type="text" value={formData.prop_ecmloadtype} onChange={handleInputChange('prop_ecmloadtype')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    CSSOURCE
                  </label>
                  <input type="text" value={formData.prop_cssource} onChange={handleInputChange('prop_cssource')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    CSLOADTYPE
                  </label>
                  <input type="text" value={formData.prop_csloadtype} onChange={handleInputChange('prop_csloadtype')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    CRRSOURCE
                  </label>
                  <input type="text" value={formData.prop_crrsource} onChange={handleInputChange('prop_crrsource')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    CRRLOADTYPE
                  </label>
                  <input type="text" value={formData.prop_crrloadtype} onChange={handleInputChange('prop_crrloadtype')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                    FSDF_UPLOAD_MODEL
                  </label>
                  <input type="text" value={formData.prop_fsdf_upload_model} onChange={handleInputChange('prop_fsdf_upload_model')} placeholder="1" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
              </div>

            </div>
          </details>
        </motion.div>
        )}

        {/* ECM Pack Configuration */}
        {formData.install_ecm && (
        <EcmPackPage
          enabled={formData.install_ecm}
          host={formData.host}
          configSchemaName={formData.schema_config_schema_name}
          atomicSchemaName={formData.schema_atomic_schema_name}
          aaiConfig={{
            aai_webappservertype: formData.aai_webappservertype,
            aai_dbserver_ip: formData.aai_dbserver_ip,
            aai_oracle_service_name: formData.aai_oracle_service_name,
            aai_abs_driver_path: formData.aai_abs_driver_path,
            aai_olap_server_implementation: formData.aai_olap_server_implementation,
            aai_sftp_enable: formData.aai_sftp_enable,
            aai_file_transfer_port: formData.aai_file_transfer_port,
            aai_javaport: formData.aai_javaport,
            aai_nativeport: formData.aai_nativeport,
            aai_agentport: formData.aai_agentport,
            aai_iccport: formData.aai_iccport,
            aai_iccnativeport: formData.aai_iccnativeport,
            aai_olapport: formData.aai_olapport,
            aai_msgport: formData.aai_msgport,
            aai_routerport: formData.aai_routerport,
            aai_amport: formData.aai_amport,
            aai_https_enable: formData.aai_https_enable,
            aai_web_server_ip: formData.aai_web_server_ip,
            aai_web_server_port: formData.aai_web_server_port,
            aai_context_name: formData.aai_context_name,
            aai_webapp_context_path: formData.aai_webapp_context_path,
            aai_web_local_path: formData.aai_web_local_path,
            aai_weblogic_domain_home: formData.aai_weblogic_domain_home,
            aai_ftspshare_path: formData.aai_ftspshare_path,
            aai_sftp_user_id: formData.aai_sftp_user_id
          }}
          onChange={handleEcmChange}
        />
        )}
        {ecmSubmitError && <p className="text-xs text-error">{ecmSubmitError}</p>}

        {/* OFSAAI Install Config Section - BD Pack Only */}
        {formData.install_bdpack && (
        <motion.div
          className="rounded-xl border border-border bg-bg-secondary/40 p-4 lg:p-5"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.6 }}
        >
          <details className="group">
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
                  <input type="text" value={formData.aai_webappservertype} onChange={handleInputChange('aai_webappservertype')} placeholder="3" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">DBSERVER_IP</label>
                  <input type="text" value={formData.aai_dbserver_ip} onChange={handleInputChange('aai_dbserver_ip')} placeholder="192.168.3.42" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">ORACLE SERVICE</label>
                  <input type="text" value={formData.aai_oracle_service_name} onChange={handleInputChange('aai_oracle_service_name')} placeholder="OFSAAPDB" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">ABS_DRIVER_PATH</label>
                  <input type="text" value={formData.aai_abs_driver_path} onChange={handleInputChange('aai_abs_driver_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEB_SERVER_IP</label>
                  <input type="text" value={formData.aai_web_server_ip} onChange={handleInputChange('aai_web_server_ip')} placeholder="192.168.3.41" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-4 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">HTTPS_ENABLE</label>
                  <input type="text" value={formData.aai_https_enable} onChange={handleInputChange('aai_https_enable')} placeholder="1" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEB_SERVER_PORT</label>
                  <input type="text" value={formData.aai_web_server_port} onChange={handleInputChange('aai_web_server_port')} placeholder="7002" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">CONTEXT_NAME</label>
                  <input type="text" value={formData.aai_context_name} onChange={handleInputChange('aai_context_name')} placeholder="FICHOME" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">OLAP_IMPL</label>
                  <input type="text" value={formData.aai_olap_server_implementation} onChange={handleInputChange('aai_olap_server_implementation')} placeholder="0" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEBAPP_CONTEXT_PATH</label>
                <input type="text" value={formData.aai_webapp_context_path} onChange={handleInputChange('aai_webapp_context_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEB_LOCAL_PATH</label>
                  <input type="text" value={formData.aai_web_local_path} onChange={handleInputChange('aai_web_local_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">WEBLOGIC_DOMAIN_HOME</label>
                  <input type="text" value={formData.aai_weblogic_domain_home} onChange={handleInputChange('aai_weblogic_domain_home')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
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
                      value={(formData as any)[field]}
                      onChange={handleInputChange(field as any)}
                      className="w-full bg-bg-secondary border border-border rounded-lg px-3 py-2 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
                    />
                  </div>
                ))}
              </div>

              <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">SFTP_ENABLE</label>
                  <input type="text" value={formData.aai_sftp_enable} onChange={handleInputChange('aai_sftp_enable')} placeholder="1" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">FILE_TRANSFER_PORT</label>
                  <input type="text" value={formData.aai_file_transfer_port} onChange={handleInputChange('aai_file_transfer_port')} placeholder="22" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
                <div className="space-y-2">
                  <label className="text-xs font-bold text-text-primary uppercase tracking-wider">OFSAAI_SFTP_USER_ID</label>
                  <input type="text" value={formData.aai_sftp_user_id} onChange={handleInputChange('aai_sftp_user_id')} placeholder="oracle" className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
                </div>
              </div>

              <div className="space-y-2">
                <label className="text-xs font-bold text-text-primary uppercase tracking-wider">OFSAAI_FTPSHARE_PATH</label>
                <input type="text" value={formData.aai_ftspshare_path} onChange={handleInputChange('aai_ftspshare_path')} className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted" />
              </div>
            </div>
          </details>
        </motion.div>
        )}

        {/* Submit Button */}
        <motion.div
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.5 }}
        >
          <button
            type="submit"
            disabled={isLoading}
            className={getButtonClass()}
          >
            {getButtonIcon()}
            <span>{getButtonText()}</span>
          </button>
        </motion.div>
      </form>
    </div>
  )
}
