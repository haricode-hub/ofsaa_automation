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
import { BdPackPage } from '@/components/BdPackPage'
import { BdPackFormData } from '@/components/BdPackForm'
import { EcmPackPage } from '@/components/EcmPackPage'
import { EcmFormData } from '@/components/EcmPackForm'
import { MainConfiguration, MainConfigData } from '@/components/MainConfiguration'

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
    install_bdpack: true,
    install_ecm: false
  })
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')
  const [mainConfig, setMainConfig] = useState<MainConfigData>({
    host: '',
    username: '',
    password: '',
    fic_home: '/u01/OFSAA/FICHOME',
    java_home: '',
    java_bin: '',
    oracle_sid: 'ORCL'
  })
  const [bdPackConfig, setBdPackConfig] = useState<BdPackFormData | null>(null)
  const [isBdPackValid, setIsBdPackValid] = useState(true)
  const [ecmConfig, setEcmConfig] = useState<EcmFormData | null>(null)
  const [isEcmValid, setIsEcmValid] = useState(true)
  const [ecmSubmitError, setEcmSubmitError] = useState('')

  useEffect(() => {
    try {
      const raw = localStorage.getItem(INSTALL_FORM_STORAGE_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw) as {
        formData?: Partial<InstallationData>
        mainConfig?: Partial<MainConfigData>
        bdPackConfig?: BdPackFormData | null
        ecmConfig?: EcmFormData | null
      }
      if (parsed.formData) {
        setFormData(prev => ({ ...prev, ...parsed.formData }))
      }
      if (parsed.mainConfig) {
        setMainConfig(prev => ({ ...prev, ...parsed.mainConfig }))
      }
      if (parsed.bdPackConfig !== undefined) {
        setBdPackConfig(parsed.bdPackConfig)
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
          mainConfig,
          bdPackConfig,
          ecmConfig,
        })
      )
    } catch {
      // Ignore local storage write errors
    }
  }, [formData, mainConfig, bdPackConfig, ecmConfig])

  const handleBdPackChange = useCallback((data: BdPackFormData, valid: boolean) => {
    setBdPackConfig(data)
    setIsBdPackValid(valid)
  }, [])

  const handleMainConfigChange = useCallback((data: MainConfigData) => {
    setMainConfig(data)
    // Also update the formData if needed for consistency
    setFormData(prev => ({
      ...prev,
      host: data.host,
      username: data.username,
      password: data.password,
      fic_home: data.fic_home,
      java_home: data.java_home,
      java_bin: data.java_bin,
      oracle_sid: data.oracle_sid
    }))
  }, [])

  const handleEcmChange = useCallback((data: EcmFormData, valid: boolean) => {
    setEcmConfig(data)
    setIsEcmValid(valid)
  }, [])

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setEcmSubmitError('')
    
    if (formData.install_bdpack && (!bdPackConfig || !isBdPackValid)) {
      setStatus('error')
      setEcmSubmitError('BD Pack review is blocked by validation errors. Fix BD Pack fields before deployment.')
      return
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
          // Module selection
          installation_mode: formData.installation_mode,
          install_bdpack: formData.install_bdpack,
          install_ecm: formData.install_ecm,
          
          // Main Configuration (from shared mainConfig)
          host: mainConfig.host,
          username: mainConfig.username,
          password: mainConfig.password,
          fic_home: mainConfig.fic_home,
          java_home: mainConfig.java_home || null,
          java_bin: mainConfig.java_bin || null,
          oracle_sid: mainConfig.oracle_sid,

          schema_jdbc_host: bdPackConfig?.schema_jdbc_host || formData.schema_jdbc_host,
          schema_jdbc_port: bdPackConfig?.schema_jdbc_port ? Number(bdPackConfig.schema_jdbc_port) : (formData.schema_jdbc_port ? Number(formData.schema_jdbc_port) : null),
          schema_jdbc_service: bdPackConfig?.schema_jdbc_service || formData.schema_jdbc_service,
          schema_host: mainConfig.host,
          schema_setup_env: bdPackConfig?.schema_setup_env || formData.schema_setup_env,
          schema_apply_same_for_all: bdPackConfig?.schema_apply_same_for_all || formData.schema_apply_same_for_all,
          schema_default_password: bdPackConfig?.schema_default_password || formData.schema_default_password,
          schema_datafile_dir: bdPackConfig?.schema_datafile_dir || formData.schema_datafile_dir,
          schema_tablespace_autoextend: bdPackConfig?.schema_tablespace_autoextend || formData.schema_tablespace_autoextend,
          schema_external_directory_value: bdPackConfig?.schema_external_directory_value || formData.schema_external_directory_value,
          schema_config_schema_name: bdPackConfig?.schema_config_schema_name || formData.schema_config_schema_name,
          schema_atomic_schema_name: bdPackConfig?.schema_atomic_schema_name || formData.schema_atomic_schema_name,

          pack_app_enable: bdPackConfig?.pack_app_enable || formData.pack_app_enable,

          prop_base_country: bdPackConfig?.prop_base_country || formData.prop_base_country,
          prop_default_jurisdiction: bdPackConfig?.prop_default_jurisdiction || formData.prop_default_jurisdiction,
          prop_smtp_host: bdPackConfig?.prop_smtp_host || formData.prop_smtp_host,
          prop_partition_date_format: bdPackConfig?.prop_partition_date_format || formData.prop_partition_date_format,
          prop_datadumpdt_minus_0: bdPackConfig?.prop_datadumpdt_minus_0 || formData.prop_datadumpdt_minus_0,
          prop_endthisweek_minus_00: bdPackConfig?.prop_endthisweek_minus_00 || formData.prop_endthisweek_minus_00,
          prop_startnextmnth_minus_00: bdPackConfig?.prop_startnextmnth_minus_00 || formData.prop_startnextmnth_minus_00,
          prop_analyst_data_source: bdPackConfig?.prop_analyst_data_source || formData.prop_analyst_data_source,
          prop_miner_data_source: bdPackConfig?.prop_miner_data_source || formData.prop_miner_data_source,
          prop_web_service_user: bdPackConfig?.prop_web_service_user || formData.prop_web_service_user,
          prop_web_service_password: bdPackConfig?.prop_web_service_password || formData.prop_web_service_password,
          prop_nls_length_semantics: bdPackConfig?.prop_nls_length_semantics || formData.prop_nls_length_semantics,
          prop_configure_obiee: bdPackConfig?.prop_configure_obiee || formData.prop_configure_obiee,
          prop_obiee_url: (bdPackConfig?.prop_obiee_url || formData.prop_obiee_url) || '',
          prop_sw_rmiport: bdPackConfig?.prop_sw_rmiport || formData.prop_sw_rmiport,
          prop_big_data_enable: bdPackConfig?.prop_big_data_enable || formData.prop_big_data_enable,
          prop_sqoop_working_dir: bdPackConfig?.prop_sqoop_working_dir || formData.prop_sqoop_working_dir,
          prop_ssh_auth_alias: bdPackConfig?.prop_ssh_auth_alias || formData.prop_ssh_auth_alias,
          prop_ssh_host_name: bdPackConfig?.prop_ssh_host_name || formData.prop_ssh_host_name,
          prop_ssh_port: bdPackConfig?.prop_ssh_port || formData.prop_ssh_port,
          prop_ecmsource: bdPackConfig?.prop_ecmsource || formData.prop_ecmsource,
          prop_ecmloadtype: bdPackConfig?.prop_ecmloadtype || formData.prop_ecmloadtype,
          prop_cssource: bdPackConfig?.prop_cssource || formData.prop_cssource,
          prop_csloadtype: bdPackConfig?.prop_csloadtype || formData.prop_csloadtype,
          prop_crrsource: bdPackConfig?.prop_crrsource || formData.prop_crrsource,
          prop_crrloadtype: bdPackConfig?.prop_crrloadtype || formData.prop_crrloadtype,
          prop_fsdf_upload_model: bdPackConfig?.prop_fsdf_upload_model || formData.prop_fsdf_upload_model,

          aai_webappservertype: bdPackConfig?.aai_webappservertype || formData.aai_webappservertype,
          aai_dbserver_ip: bdPackConfig?.aai_dbserver_ip || formData.aai_dbserver_ip,
          aai_oracle_service_name: bdPackConfig?.aai_oracle_service_name || formData.aai_oracle_service_name,
          aai_abs_driver_path: bdPackConfig?.aai_abs_driver_path || formData.aai_abs_driver_path,
          aai_olap_server_implementation: bdPackConfig?.aai_olap_server_implementation || formData.aai_olap_server_implementation,
          aai_sftp_enable: bdPackConfig?.aai_sftp_enable || formData.aai_sftp_enable,
          aai_file_transfer_port: bdPackConfig?.aai_file_transfer_port || formData.aai_file_transfer_port,
          aai_javaport: bdPackConfig?.aai_javaport || formData.aai_javaport,
          aai_nativeport: bdPackConfig?.aai_nativeport || formData.aai_nativeport,
          aai_agentport: bdPackConfig?.aai_agentport || formData.aai_agentport,
          aai_iccport: bdPackConfig?.aai_iccport || formData.aai_iccport,
          aai_iccnativeport: bdPackConfig?.aai_iccnativeport || formData.aai_iccnativeport,
          aai_olapport: bdPackConfig?.aai_olapport || formData.aai_olapport,
          aai_msgport: bdPackConfig?.aai_msgport || formData.aai_msgport,
          aai_routerport: bdPackConfig?.aai_routerport || formData.aai_routerport,
          aai_amport: bdPackConfig?.aai_amport || formData.aai_amport,
          aai_https_enable: bdPackConfig?.aai_https_enable || formData.aai_https_enable,
          aai_web_server_ip: bdPackConfig?.aai_web_server_ip || formData.aai_web_server_ip,
          aai_web_server_port: bdPackConfig?.aai_web_server_port || formData.aai_web_server_port,
          aai_context_name: bdPackConfig?.aai_context_name || formData.aai_context_name,
          aai_webapp_context_path: bdPackConfig?.aai_webapp_context_path || formData.aai_webapp_context_path,
          aai_web_local_path: bdPackConfig?.aai_web_local_path || formData.aai_web_local_path,
          aai_weblogic_domain_home: bdPackConfig?.aai_weblogic_domain_home || formData.aai_weblogic_domain_home,
          aai_ftspshare_path: bdPackConfig?.aai_ftspshare_path || formData.aai_ftspshare_path,
          aai_sftp_user_id: bdPackConfig?.aai_sftp_user_id || formData.aai_sftp_user_id,
          
          bd_pack_config: formData.install_bdpack ? bdPackConfig : null,
          ecm_config: formData.install_ecm ? ecmConfig : null
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
    setFormData(prev => ({ ...prev, [field]: e.target.value }))
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
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">
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
            <div className="space-y-2">
              <label className="text-xs font-bold text-text-primary uppercase tracking-wider">
                Scenario
              </label>
              <div className="flex items-center pt-2">
                <span className={`px-3 py-2 rounded text-xs font-bold ${
                  formData.install_bdpack && !formData.install_ecm ? 'bg-blue-600 text-white' :
                  formData.install_bdpack && formData.install_ecm ? 'bg-purple-600 text-white' :
                  formData.install_ecm && !formData.install_bdpack ? 'bg-indigo-600 text-white' :
                  'bg-gray-600 text-white'
                }`}>
                  {formData.install_bdpack && !formData.install_ecm ? 'BD Pack' :
                   formData.install_bdpack && formData.install_ecm ? 'BD Pack + ECM' :
                   formData.install_ecm && !formData.install_bdpack ? 'ECM Only' :
                   'No modules'}
                </span>
              </div>
            </div>
          </div>
        </motion.div>

        {/* Shared Main Configuration */}
        {(formData.install_bdpack || formData.install_ecm) && (
          <MainConfiguration
            enabled={true}
            data={mainConfig}
            errors={{}}
            onChange={handleMainConfigChange}
          />
        )}

        {/* BD Pack Configuration */}
        <BdPackPage
          enabled={formData.install_bdpack}
          host={mainConfig.host}
          mainConfig={mainConfig}
          onChange={handleBdPackChange}
          onMainConfigChange={handleMainConfigChange}
        />

        {/* ECM Pack Configuration */}
        <EcmPackPage
          enabled={formData.install_ecm}
          host={mainConfig.host}
          configSchemaName={formData.schema_config_schema_name}
          atomicSchemaName={formData.schema_atomic_schema_name}
          mainConfig={mainConfig}
          onChange={handleEcmChange}
          onMainConfigChange={handleMainConfigChange}
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
            aai_sftp_user_id: formData.aai_sftp_user_id,
          }}
        />
        {ecmSubmitError && <p className="text-xs text-error">{ecmSubmitError}</p>}

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
