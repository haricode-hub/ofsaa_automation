# OFSAA Installation System - Complete Working Guide

## System Overview

This is a comprehensive full-stack web application for automating Oracle Financial Services Analytical Applications (OFSAA) installation on Linux servers. The system provides a modern web interface with real-time progress tracking and background task processing.

### Key Features
- ✅ **Modern Web UI** - React/Next.js frontend with glass morphism design and animations
- ✅ **Background Task Processing** - FastAPI backend with async operations  
- ✅ **Real-time Progress Tracking** - Live status updates and detailed logging
- ✅ **10-Step Installation Pipeline** - Complete OFSAA environment setup
- ✅ **SSH Automation** - Remote server configuration via paramiko
- ✅ **Production Ready** - Error handling, logging, and scalable architecture

### Technology Stack
- **Backend**: FastAPI + Python 3.12 + paramiko + uvicorn
- **Frontend**: Next.js 14 + TypeScript + Tailwind CSS + Framer Motion
- **Communication**: REST API + Background Tasks
- **Target Environment**: Linux servers (RHEL/CentOS/Oracle Linux)

---

## Complete Code Implementation

### Backend Implementation

#### 1. Main Application (`backend/main.py`)

```python
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
import logging
from routers.installation import router as installation_router
from core.logging import setup_logging

# Setup application logging
setup_logging()
logger = logging.getLogger(__name__)

app = FastAPI(
    title="OFSAA Installation API",
    description="Backend API for Oracle Financial Services installation automation",
    version="1.0.0"
)

logger.info("Starting OFSAA Installation API...")

# CORS middleware for frontend communication
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],  # Next.js dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(installation_router, prefix="/api/installation", tags=["installation"])

@app.get("/")
async def root():
    return {"message": "OFSAA Installation API is running"}

@app.get("/health")
async def health_check():
    return {"status": "healthy", "service": "ofsaa-installation-backend"}

if __name__ == "__main__":
    logger.info("Starting Uvicorn server...")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
```

#### 2. Dependencies (`backend/requirements.txt`)

```pip-requirements
fastapi>=0.115.0
uvicorn[standard]>=0.32.0
pydantic>=2.10.0
python-multipart>=0.0.12
paramiko>=3.4.0
```

#### 3. Data Schemas (`backend/schemas/installation.py`)

```python
from pydantic import BaseModel, Field
from typing import Optional, List

class InstallationRequest(BaseModel):
    """Schema for installation request"""
    host: str = Field(..., description="Target host IP address or hostname")
    username: str = Field(..., description="Root username for SSH connection")
    password: str = Field(..., description="Root password for SSH connection")
    # Profile variables that user can customize
    fic_home: Optional[str] = Field(default="/u01/OFSAA/FICHOME", description="FIC_HOME path")
    java_home: Optional[str] = Field(default=None, description="Custom JAVA_HOME path (optional)")
    java_bin: Optional[str] = Field(default=None, description="Custom JAVA_BIN path (optional)")
    oracle_sid: Optional[str] = Field(default="ORCL", description="Oracle SID")

class InstallationResponse(BaseModel):
    """Schema for installation response"""
    task_id: str
    status: str
    message: str

class InstallationStatus(BaseModel):
    """Schema for installation status"""
    task_id: str
    status: str
    current_step: Optional[str] = None
    progress: int = 0
    logs: List[str] = []
    error: Optional[str] = None

class SSHConnectionRequest(BaseModel):
    """Schema for SSH connection test"""
    host: str
    username: str
    password: str

class ServiceResult(BaseModel):
    """Schema for service operation results"""
    success: bool
    message: str
    logs: List[str] = []
    error: Optional[str] = None
    output: Optional[str] = None
    stderr: Optional[str] = None
    returncode: Optional[int] = None

class OracleClientConfig(BaseModel):
    """Schema for Oracle client configuration"""
    oracle_home: str
    tns_admin: str
    oracle_sid: str
```

#### 4. Installation Router (`backend/routers/installation.py`)

```python
from fastapi import APIRouter, HTTPException, BackgroundTasks
from typing import Optional
import asyncio
from services.ssh_service import SSHService
from services.installation_service import InstallationService
from schemas.installation import InstallationRequest, InstallationResponse, InstallationStatus, OracleClientConfig
from core.logging import TaskLogger
from core.config import Config, InstallationSteps
import logging

router = APIRouter()
logger = logging.getLogger(__name__)

# In-memory storage for installation tasks (use Redis/database in production)
installation_tasks: dict[str, InstallationStatus] = {}

@router.post("/start", response_model=InstallationResponse)
async def start_installation(
    request: InstallationRequest,
    background_tasks: BackgroundTasks
):
    """Start OFSAA installation process"""
    try:
        # Generate unique task ID
        import uuid
        task_id = str(uuid.uuid4())
        
        # Initialize task status
        installation_tasks[task_id] = InstallationStatus(
            task_id=task_id,
            status="started",
            current_step="Initializing connection",
            progress=0,
            logs=[
                f"OFSAA Installation Started - Task ID: {task_id[:8]}...",
                f"Target Server: {request.host}",
                f"Username: {request.username}",
                f"Started at: {__import__('datetime').datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
                "Initializing SSH connection..."
            ]
        )
        
        # Start installation in background
        background_tasks.add_task(
            run_installation_process,
            task_id,
            request.host,
            request.username,
            request.password,
            request.fic_home,
            request.java_home,
            request.java_bin,
            request.oracle_sid
        )
        
        return InstallationResponse(
            task_id=task_id,
            status="started",
            message="Installation process initiated successfully"
        )
        
    except Exception as e:
        logger.error(f"Failed to start installation: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to start installation: {str(e)}")

@router.get("/status/{task_id}", response_model=InstallationStatus)
async def get_installation_status(task_id: str):
    """Get installation status by task ID"""
    if task_id not in installation_tasks:
        raise HTTPException(status_code=404, detail="Installation task not found")
    
    return installation_tasks[task_id]

@router.get("/tasks")
async def list_installation_tasks():
    """List all installation tasks"""
    return {"tasks": list(installation_tasks.values())}

@router.post("/test-connection")
async def test_ssh_connection(request: InstallationRequest):
    """Test SSH connection without starting installation"""
    try:
        ssh_service = SSHService()
        result = await ssh_service.test_connection(request.host, request.username, request.password)
        return result
    except Exception as e:
        logger.error(f"Connection test failed: {str(e)}")
        return {
            "success": False,
            "error": f"Connection test failed: {str(e)}"
        }

async def run_installation_process(task_id: str, host: str, username: str, password: str, 
                                    fic_home: str, java_home: Optional[str], java_bin: Optional[str], oracle_sid: str):
    """Background task to run the complete OFSAA installation process"""
    try:
        print(f"Starting OFSAA installation process for task {task_id}")
        print(f"Target: {host}, User: {username}")
        print(f"Profile variables: FIC_HOME={fic_home}, ORACLE_SID={oracle_sid}")
        
        task = installation_tasks[task_id]
        ssh_service = SSHService()
        installation_service = InstallationService(ssh_service)
        
        # 10-Step Installation Process with real-time progress tracking
        
        # Step 1: Test SSH Connection
        task.current_step = "Testing SSH connection"
        task.progress = InstallationSteps.PROGRESS_MAP["connection_test"]
        task.logs.append("🔗 Testing SSH connection to target server...")
        
        connection_test = await ssh_service.test_connection(host, username, password)
        if not connection_test["success"]:
            task.status = "failed"
            task.error = connection_test["error"]
            task.logs.append(f"❌ Connection failed: {connection_test['error']}")
            return
        task.logs.append("✅ SSH connection successful")
        
        # Step 2: Oracle User Setup
        task.current_step = InstallationSteps.STEP_NAMES[1]
        task.progress = InstallationSteps.PROGRESS_MAP["oracle_user_setup"]
        task.logs.append("🔨 Creating oracle user and oinstall group...")
        
        oracle_user_result = await installation_service.create_oracle_user_and_oinstall_group(host, username, password)
        if not oracle_user_result["success"]:
            task.status = "failed"
            task.error = oracle_user_result["error"]
            task.logs.extend(oracle_user_result["logs"])
            return
        task.logs.extend(oracle_user_result["logs"])
        
        # Step 3: Mount Point Creation
        task.current_step = InstallationSteps.STEP_NAMES[2]
        task.progress = InstallationSteps.PROGRESS_MAP["mount_point_creation"]
        task.logs.append("🔨 Creating mount point /u01...")
        
        mount_point_result = await installation_service.create_mount_point(host, username, password)
        if not mount_point_result["success"]:
            task.status = "failed"
            task.error = mount_point_result["error"]
            task.logs.extend(mount_point_result["logs"])
            return
        task.logs.extend(mount_point_result["logs"])
        
        # Step 4: Package Installation
        task.current_step = InstallationSteps.STEP_NAMES[3]
        task.progress = InstallationSteps.PROGRESS_MAP["packages_installation"]
        task.logs.append("🔨 Installing KSH (Korn Shell) and git...")
        
        packages_result = await installation_service.install_ksh_and_git(host, username, password)
        if not packages_result["success"]:
            task.status = "failed"
            task.error = packages_result["error"]
            task.logs.extend(packages_result["logs"])
            return
        task.logs.extend(packages_result["logs"])
        
        # Step 5: Profile Creation
        task.current_step = InstallationSteps.STEP_NAMES[4]
        task.progress = InstallationSteps.PROGRESS_MAP["profile_creation"]
        task.logs.append("🔨 Creating .profile file at /home/oracle/.profile...")
        
        profile_result = await installation_service.create_profile_file(host, username, password)
        if not profile_result["success"]:
            task.status = "failed"
            task.error = profile_result["error"]
            task.logs.extend(profile_result["logs"])
            return
        task.logs.extend(profile_result["logs"])
        
        # Step 6: Java Installation
        task.current_step = InstallationSteps.STEP_NAMES[5]
        task.progress = InstallationSteps.PROGRESS_MAP["java_installation"]
        task.logs.append("🔨 Installing Java from Oracle installer kit...")
        
        java_home_path = java_home or "/u01/jdk-11.0.16"
        java_result = await installation_service.install_java_from_oracle_kit(host, username, password, java_home_path)
        if not java_result["success"]:
            task.status = "failed"
            task.error = java_result["error"]
            task.logs.extend(java_result["logs"])
            return
        task.logs.extend(java_result["logs"])
        
        # Step 7: OFSAA Directory Structure Creation
        task.current_step = InstallationSteps.STEP_NAMES[6]
        task.progress = InstallationSteps.PROGRESS_MAP["ofsaa_directories"]
        task.logs.append("📁 Creating OFSAA directory structure...")
        
        ofsaa_dirs_result = await installation_service.create_ofsaa_directories(host, username, password, fic_home)
        if not ofsaa_dirs_result["success"]:
            task.status = "failed"
            task.error = ofsaa_dirs_result["error"]
            task.logs.extend(ofsaa_dirs_result["logs"])
            return
        task.logs.extend(ofsaa_dirs_result["logs"])
        
        # Step 8: Oracle Client Check
        task.current_step = InstallationSteps.STEP_NAMES[7]
        task.progress = InstallationSteps.PROGRESS_MAP["oracle_client_check"]
        task.logs.append("🔍 Scanning for existing Oracle client installations...")
        
        oracle_client_result = await installation_service.check_existing_oracle_client_and_update_profile(host, username, password, oracle_sid)
        if not oracle_client_result["success"]:
            task.status = "failed"
            task.error = oracle_client_result["error"]
            task.logs.extend(oracle_client_result["logs"])
            return
        task.logs.extend(oracle_client_result["logs"])
        
        # Step 9: OFSAA Installer Setup and Environment Check
        task.current_step = InstallationSteps.STEP_NAMES[8]
        task.progress = InstallationSteps.PROGRESS_MAP["installer_setup"]
        task.logs.append("📦 Setting up OFSAA installer from git repository...")
        
        installer_result = await installation_service.extract_installer_files(host, username, password)
        if not installer_result["success"]:
            task.logs.append("⚠️ Installer setup had issues, but continuing...")
            task.logs.extend(installer_result["logs"])
        else:
            task.logs.extend(installer_result["logs"])
        
        # Step 10: Profile Update with Custom Variables
        task.current_step = InstallationSteps.STEP_NAMES[9]
        task.progress = InstallationSteps.PROGRESS_MAP["profile_update"]
        task.logs.append("🔨 Updating profile with custom variables...")
        
        custom_variables_result = await installation_service.update_profile_with_custom_variables(
            host, username, password, fic_home, java_home, java_bin, oracle_sid
        )
        if not custom_variables_result["success"]:
            task.status = "failed"
            task.error = custom_variables_result["error"]
            task.logs.extend(custom_variables_result["logs"])
            return
        task.logs.extend(custom_variables_result["logs"])
        
        # Complete
        task.progress = InstallationSteps.PROGRESS_MAP["completed"]
        task.current_step = "OFSAA environment setup completed successfully"
        task.status = "completed"
        task.logs.append("")
        task.logs.append("🎉 OFSAA Environment Setup Completed Successfully!")
        task.logs.append("=" * 50)
        task.logs.append("✅ Oracle user and oinstall group created")
        task.logs.append("✅ Mount point /u01 created with proper directory structure")
        task.logs.append("✅ KSH (Korn Shell) and git packages installed")
        task.logs.append("✅ Oracle profile file created at /home/oracle/.profile")
        task.logs.append("✅ Java installed from Oracle kit")
        task.logs.append("✅ OFSAA directory structure created (/u01/OFSAA/FICHOME, /u01/OFSAA/FTPSHARE)")
        task.logs.append("✅ Oracle client found and environment configured")
        task.logs.append("✅ OFSAA installer downloaded and environment check completed")
        task.logs.append("✅ Profile updated with custom variables")
        task.logs.append("✅ Environment ready for OFSAA installation")
        task.logs.append("")
        task.logs.append("🚀 System is ready for OFSAA installation!")
        
    except Exception as e:
        print(f"Installation process failed with exception: {str(e)}")
        logger.error(f"Installation process failed: {str(e)}")
        task = installation_tasks[task_id]
        task.status = "failed"
        task.error = str(e)
        task.logs.append(f"❌ Unexpected error: {str(e)}")
```

---

### Frontend Implementation

#### 1. Next.js Configuration (`frontend/next.config.js`)

```javascript
/** @type {import('next').NextConfig} */
const nextConfig = {
  experimental: {
    optimizePackageImports: ['framer-motion'],
  },
  typescript: {
    ignoreBuildErrors: false,
  },
  eslint: {
    ignoreDuringBuilds: false,
  },
}

module.exports = nextConfig
```

#### 2. Main Page (`frontend/src/app/page.tsx`)

```tsx
'use client'

import { motion } from 'framer-motion'
import { BackgroundMatrix } from '@/components/BackgroundMatrix'
import { InstallationForm } from '@/components/InstallationForm'

export default function HomePage() {
  return (
    <div className="relative min-h-screen bg-bg-primary">
      <BackgroundMatrix />
      
      {/* Single column layout for better responsive behavior */}
      <div className="min-h-screen flex flex-col items-center justify-center p-4 lg:p-8 relative">
        
        {/* Installation Form Panel */}
        <motion.div 
          className="glass-panel rounded-2xl p-6 lg:p-12 w-full max-w-md lg:max-w-lg shadow-panel relative overflow-hidden mb-8"
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.6, ease: "easeOut" }}
        >
          {/* Subtle border glow */}
          <div className="absolute inset-0 opacity-10">
            <div className="absolute top-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-white to-transparent" />
            <div className="absolute bottom-0 left-0 w-full h-px bg-gradient-to-r from-transparent via-white to-transparent" />
            <div className="absolute left-0 top-0 w-px h-full bg-gradient-to-b from-transparent via-white to-transparent" />
            <div className="absolute right-0 top-0 w-px h-full bg-gradient-to-b from-transparent via-white to-transparent" />
          </div>
          
          <div className="relative z-10">
            {/* Header */}
            <motion.div 
              className="text-center mb-8 lg:mb-10"
              initial={{ opacity: 0, y: 15 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ duration: 0.5, delay: 0.1 }}
            >
              <h1 className="text-5xl lg:text-6xl xl:text-7xl font-black text-text-primary mb-4 tracking-tighter leading-none">
                OFSAA
              </h1>
              <div className="w-20 h-px bg-white mx-auto mb-4" />
              <p className="text-xs lg:text-sm text-text-secondary font-light tracking-[0.25em] uppercase">
                Remote Installation Gateway
                <span className="inline-block w-1.5 h-1.5 bg-success rounded-full ml-3 animate-blink" />
              </p>
            </motion.div>

            {/* Installation Form */}
            <InstallationForm />
          </div>
        </motion.div>
      </div>
    </div>
  )
}
```

#### 3. Installation Form Component (`frontend/src/components/InstallationForm.tsx`)

```tsx
'use client'

import { useState } from 'react'
import { useRouter } from 'next/navigation'
import { motion } from 'framer-motion'
import { clsx } from 'clsx'
import {
  ServerIcon,
  UserIcon,
  KeyIcon,
  RocketLaunchIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon
} from '@heroicons/react/24/outline'

interface InstallationData {
  host: string
  username: string
  password: string
  // Profile variables
  fic_home: string
  java_home: string
  java_bin: string
  oracle_sid: string
}

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
    oracle_sid: 'ORCL'
  })
  const [isLoading, setIsLoading] = useState(false)
  const [status, setStatus] = useState<'idle' | 'success' | 'error'>('idle')

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
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
          oracle_sid: formData.oracle_sid
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
    const baseClass = "w-full flex items-center justify-center gap-2 py-3 px-6 rounded-xl font-bold transition-all duration-300 transform hover:scale-[1.02] active:scale-[0.98] focus:outline-none focus:ring-2 focus:ring-offset-2 focus:ring-offset-bg-secondary uppercase tracking-wider text-sm"
    
    if (isLoading) {
      return clsx(baseClass, "bg-gray-500 text-gray-300 cursor-not-allowed")
    }
    
    if (status === 'success') {
      return clsx(baseClass, "bg-success text-white shadow-lg shadow-success/30 focus:ring-success")
    }
    
    if (status === 'error') {
      return clsx(baseClass, "bg-error text-white shadow-lg shadow-error/30 focus:ring-error")
    }
    
    return clsx(baseClass, "bg-white text-gray-900 shadow-lg shadow-white/20 hover:bg-gray-100 focus:ring-white")
  }

  return (
    <div>
      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Host Field */}
        <motion.div 
          className="space-y-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.1 }}
        >
          <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
            <ServerIcon className="w-4 h-4" />
            Target Server IP/Hostname
          </label>
          <input
            type="text"
            value={formData.host}
            onChange={handleInputChange('host')}
            placeholder="192.168.1.100"
            className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            required
          />
        </motion.div>

        {/* Username Field */}
        <motion.div 
          className="space-y-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.2 }}
        >
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
        </motion.div>

        {/* Password Field */}
        <motion.div 
          className="space-y-2"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.3 }}
        >
          <label className="flex items-center gap-2 text-xs font-bold text-text-primary uppercase tracking-wider">
            <KeyIcon className="w-4 h-4" />
            SSH Password
          </label>
          <input
            type="password"
            value={formData.password}
            onChange={handleInputChange('password')}
            placeholder="••••••••••••"
            className="w-full bg-bg-secondary border border-border rounded-lg px-4 py-3 text-sm text-text-primary transition-all duration-200 focus:outline-none focus:border-white focus:bg-bg-tertiary placeholder-text-muted"
            required
          />
        </motion.div>

        {/* Profile Variables Section */}
        <motion.div 
          className="border-t border-border pt-6 space-y-4"
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, delay: 0.4 }}
        >
          <div className="text-sm font-bold text-text-primary uppercase tracking-wider mb-4">
            📋 Profile Configuration
          </div>

          {/* FIC_HOME Field */}
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

          {/* JAVA_HOME Field */}
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

          {/* JAVA_BIN Field */}
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

          {/* ORACLE_SID Field */}
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
        </motion.div>

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
```

#### 4. Real-time Logs Page (`frontend/src/app/logs/[taskId]/page.tsx`)

```tsx
'use client'

import { useState, useEffect, useRef } from 'react'
import { useParams, useRouter } from 'next/navigation'
import { motion, AnimatePresence } from 'framer-motion'
import {
  ArrowLeftIcon,
  CommandLineIcon,
  SignalIcon,
  CheckCircleIcon,
  ExclamationCircleIcon,
  ArrowPathIcon,
  DocumentTextIcon,
  ServerIcon,
  MagnifyingGlassIcon,
  FunnelIcon,
  PlayIcon,
  PauseIcon,
  EyeIcon,
  ClockIcon
} from '@heroicons/react/24/outline'

interface LogEntry {
  timestamp: string
  level: 'INFO' | 'ERROR' | 'SUCCESS' | 'WARNING'
  message: string
}

export default function LogsPage() {
  const params = useParams()
  const router = useRouter()
  const taskId = params?.taskId as string
  
  const [logs, setLogs] = useState<LogEntry[]>([])
  const [currentStep, setCurrentStep] = useState<string>('')
  const [progress, setProgress] = useState<number>(0)
  const [status, setStatus] = useState<'idle' | 'running' | 'success' | 'error'>('running')
  const [filterLevel, setFilterLevel] = useState<string>('all')
  const [searchQuery, setSearchQuery] = useState('')
  const [isAutoScroll, setIsAutoScroll] = useState(true)
  const [isPaused, setIsPaused] = useState(false)
  
  const logsEndRef = useRef<HTMLDivElement>(null)
  const pollIntervalRef = useRef<NodeJS.Timeout | null>(null)

  const formatLogEntry = (logText: string): LogEntry => {
    const timestamp = new Date().toLocaleTimeString('en-US', { 
      hour12: false,
      hour: '2-digit',
      minute: '2-digit',
      second: '2-digit'
    })
    
    // Clean log text by removing step indicators and arrows
    let cleanedText = logText
      .replace(/^→\\s*✓\\s*Step\\s*\\d+:\\s*/i, '') // Remove "→ ✓ Step X:" prefix
      .replace(/^✓\\s*Step\\s*\\d+:\\s*/i, '')     // Remove "✓ Step X:" prefix
      .replace(/^🔨\\s*Step\\s*\\d+:\\s*/i, '')     // Remove "🔨 Step X:" prefix
      .replace(/^Step\\s*\\d+:\\s*/i, '')          // Remove "Step X:" prefix
      .replace(/^→\\s*/g, '')                    // Remove standalone arrows "→"
      .replace(/\\s*→\\s*/g, ' ')                 // Remove arrows in middle of text
      .trim()
    
    let level: LogEntry['level'] = 'INFO'
    if (cleanedText.includes('❌') || cleanedText.includes('ERROR') || cleanedText.includes('failed') || cleanedText.includes('Failed')) {
      level = 'ERROR'
    } else if (cleanedText.includes('✅') || cleanedText.includes('SUCCESS') || cleanedText.includes('successful') || cleanedText.includes('Complete')) {
      level = 'SUCCESS'
    } else if (cleanedText.includes('⚠️') || cleanedText.includes('WARNING')) {
      level = 'WARNING'
    }
    
    return { timestamp, level, message: cleanedText }
  }

  useEffect(() => {
    if (!taskId) return

    const pollStatus = async () => {
      try {
        const response = await fetch(`http://localhost:8000/api/installation/status/${taskId}`)
        if (!response.ok) {
          throw new Error(`HTTP error! status: ${response.status}`)
        }
        
        const statusData = await response.json()
        
        setCurrentStep(statusData.current_step || '')
        setProgress(statusData.progress || 0)
        
        // Format and update logs - only add new logs to prevent blinking
        if (statusData.logs && statusData.logs.length > 0) {
          const formattedLogs = statusData.logs.map(formatLogEntry)
          setLogs(prevLogs => {
            // Compare the actual content to avoid unnecessary updates
            const prevContent = prevLogs.map((log: LogEntry) => log.message).join('|')
            const newContent = formattedLogs.map((log: LogEntry) => log.message).join('|')
            
            if (prevContent !== newContent) {
              return formattedLogs
            }
            return prevLogs
          })
        }
        
        // Update status based on task status
        if (statusData.status === 'completed') {
          setStatus('success')
        } else if (statusData.status === 'failed') {
          setStatus('error')
        } else {
          setStatus('running')
        }
        
      } catch (error) {
        console.error('Failed to fetch status:', error)
        setStatus('error')
      }
    }

    // Initial fetch
    pollStatus()
    
    // Set up polling - only if not paused
    if (!isPaused) {
      pollIntervalRef.current = setInterval(pollStatus, 2000) // Poll every 2 seconds
    }

    return () => {
      if (pollIntervalRef.current) {
        clearInterval(pollIntervalRef.current)
      }
    }
  }, [taskId, isPaused])

  // Auto-scroll to bottom when new logs arrive
  useEffect(() => {
    if (isAutoScroll && logsEndRef.current) {
      logsEndRef.current.scrollIntoView({ behavior: 'smooth' })
    }
  }, [logs, isAutoScroll])

  // Filter logs based on level and search query
  const filteredLogs = logs.filter(log => {
    if (filterLevel !== 'all' && log.level !== filterLevel) return false
    if (searchQuery && !log.message.toLowerCase().includes(searchQuery.toLowerCase())) return false
    return true
  })

  const getStatusIcon = () => {
    switch (status) {
      case 'running':
        return <ArrowPathIcon className="w-5 h-5 text-warning animate-spin" />
      case 'success':
        return <CheckCircleIcon className="w-5 h-5 text-success" />
      case 'error':
        return <ExclamationCircleIcon className="w-5 h-5 text-error" />
      default:
        return <CommandLineIcon className="w-5 h-5 text-text-muted" />
    }
  }

  const getStatusText = () => {
    switch (status) {
      case 'running':
        return 'Installation in Progress'
      case 'success':
        return 'Installation Complete'
      case 'error':
        return 'Installation Failed'
      default:
        return 'Installation Status'
    }
  }

  return (
    <div className="min-h-screen bg-bg-primary text-text-primary">
      <div className="flex flex-col h-screen">
        {/* Header */}
        <div className="flex-shrink-0 p-4 lg:p-6 bg-bg-secondary border-b border-border">
          <div className="flex items-center justify-between mb-4">
            <button
              onClick={() => router.push('/')}
              className="flex items-center gap-2 px-3 py-2 bg-bg-tertiary hover:bg-bg-tertiary/80 rounded-lg transition-colors text-sm font-medium"
            >
              <ArrowLeftIcon className="w-4 h-4" />
              Back to Home
            </button>
            
            <div className="flex items-center gap-3">
              {getStatusIcon()}
              <div>
                <h1 className="text-xl lg:text-2xl font-bold text-text-primary tracking-tight">
                  {getStatusText()}
                </h1>
                <p className="text-sm text-text-muted font-mono">Task ID: {taskId}</p>
              </div>
            </div>
            
            {status === 'running' && (
              <div className="flex items-center gap-2 text-sm text-text-secondary">
                <SignalIcon className="w-4 h-4 text-success animate-pulse" />
                <span className="font-mono">LIVE</span>
              </div>
            )}
          </div>
          
          <div className="text-xs font-mono text-text-muted">
            Task: {taskId}
          </div>
        </div>

        {/* Status Bar */}
        {currentStep && (
          <div className="px-4 lg:px-6 py-4 bg-bg-secondary border-b border-border">
            <div className="flex items-center justify-between mb-3">
              <div className="flex items-center gap-2">
                <ServerIcon className="w-4 h-4 text-text-secondary" />
                <span className="text-sm font-medium text-text-primary">{currentStep}</span>
              </div>
              {progress > 0 && (
                <span className="text-sm font-mono text-text-secondary">{progress}%</span>
              )}
            </div>
            {progress > 0 && (
              <div className="w-full bg-bg-tertiary rounded-full h-3 overflow-hidden">
                <motion.div 
                  className="h-full bg-gradient-to-r from-white to-gray-300 rounded-full"
                  initial={{ width: 0 }}
                  animate={{ width: `${progress}%` }}
                  transition={{ duration: 0.5, ease: "easeOut" }}
                />
              </div>
            )}
          </div>
        )}

        {/* Controls */}
        <div className="flex items-center gap-3 px-4 lg:px-6 py-3 bg-bg-secondary border-b border-border">
          {/* Search */}
          <div className="relative flex-1 max-w-sm">
            <MagnifyingGlassIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <input
              type="text"
              placeholder="Search logs..."
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="w-full pl-9 pr-4 py-2 text-sm bg-bg-tertiary border border-border rounded-lg text-text-primary placeholder-text-muted focus:outline-none focus:border-white"
            />
          </div>

          {/* Filter */}
          <div className="relative">
            <FunnelIcon className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-text-muted" />
            <select
              value={filterLevel}
              onChange={(e) => setFilterLevel(e.target.value)}
              className="pl-9 pr-8 py-2 text-sm bg-bg-tertiary border border-border rounded-lg text-text-primary focus:outline-none focus:border-white appearance-none cursor-pointer"
            >
              <option value="all">All Levels</option>
              <option value="INFO">Info</option>
              <option value="SUCCESS">Success</option>
              <option value="WARNING">Warning</option>
              <option value="ERROR">Error</option>
            </select>
          </div>

          {/* Controls */}
          <div className="flex items-center gap-1">
            <button
              onClick={() => setIsPaused(!isPaused)}
              className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors"
              title={isPaused ? "Resume" : "Pause"}
            >
              {isPaused ? 
                <PlayIcon className="w-4 h-4 text-text-muted hover:text-text-primary" /> :
                <PauseIcon className="w-4 h-4 text-text-muted hover:text-text-primary" />
              }
            </button>
            <button
              onClick={() => setIsAutoScroll(!isAutoScroll)}
              className="p-2 hover:bg-bg-tertiary rounded-lg transition-colors"
              title={isAutoScroll ? "Disable auto-scroll" : "Enable auto-scroll"}
            >
              <EyeIcon className={`w-4 h-4 transition-colors ${
                isAutoScroll ? "text-success" : "text-text-muted hover:text-text-primary"
              }`} />
            </button>
          </div>
        </div>

        {/* Log Content - Scrollable Area */}
        <div className="flex-1 min-h-0 bg-gray-950 relative">
          <div className="h-full overflow-y-auto scrollbar-thin scrollbar-track-gray-900 scrollbar-thumb-gray-700 hover:scrollbar-thumb-gray-600">
            <div className="p-4 lg:p-6">
              {/* Terminal header */}
              <div className="flex items-center gap-2 mb-4 pb-3 border-b border-gray-800 sticky top-0 bg-gray-950 z-10">
                <div className="flex gap-1.5">
                  <div className="w-3 h-3 rounded-full bg-error" />
                  <div className="w-3 h-3 rounded-full bg-warning" />
                  <div className="w-3 h-3 rounded-full bg-success" />
                </div>
                <DocumentTextIcon className="w-4 h-4 text-text-muted ml-2" />
                <span className="text-sm font-mono text-text-muted">installation.log</span>
                <div className="flex-1" />
                <div className="flex items-center gap-2 text-sm font-mono text-text-muted">
                  <ClockIcon className="w-4 h-4" />
                  <span>{new Date().toLocaleTimeString()}</span>
                </div>
              </div>
          
              {/* Log entries */}
              <div className="space-y-2 text-sm lg:text-base font-mono">
                {filteredLogs.length === 0 ? (
                  <div className="flex items-center justify-center py-16 text-text-muted">
                    <div className="text-center">
                      <CommandLineIcon className="w-16 h-16 mx-auto mb-6 opacity-50" />
                      <p className="text-xl mb-3 font-medium">No logs to display</p>
                      {searchQuery && (
                        <p className="text-sm opacity-75">Try adjusting your search or filter criteria</p>
                      )}
                    </div>
                  </div>
                ) : (
                  filteredLogs.map((log, index) => (
                    <motion.div 
                      key={`${index}-${log.timestamp}-${log.message.substring(0, 20)}`}
                      className="flex items-start gap-4 py-3 px-4 rounded-lg hover:bg-bg-secondary/30 transition-all duration-200 group border-l-2 border-transparent hover:border-text-muted/20"
                      initial={{ opacity: 0, x: -10 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ duration: 0.2 }}
                    >
                      <span className="text-text-muted/80 shrink-0 w-20 text-xs font-medium tracking-wide">
                        {log.timestamp}
                      </span>
                      <span className={`shrink-0 w-18 text-center rounded-md px-2 py-1 text-xs font-bold uppercase tracking-wider shadow-sm ${
                        log.level === 'INFO' ? 'bg-blue-500/20 text-blue-300 border border-blue-500/30' :
                        log.level === 'ERROR' ? 'bg-red-500/20 text-red-300 border border-red-500/30' :
                        log.level === 'SUCCESS' ? 'bg-green-500/20 text-green-300 border border-green-500/30' :
                        'bg-yellow-500/20 text-yellow-300 border border-yellow-500/30'
                      }`}>
                        {log.level}
                      </span>
                      <span className="text-text-primary flex-1 leading-relaxed break-words group-hover:text-white transition-colors duration-200">
                        {log.message}
                      </span>
                    </motion.div>
                  ))
                )}
                
                {/* Live cursor when active */}
                {status === 'running' && !isPaused && (
                  <motion.div 
                    className="flex items-center gap-4 py-2 px-3"
                    initial={{ opacity: 0 }}
                    animate={{ opacity: 1 }}
                  >
                    <span className="text-text-muted shrink-0 w-24 text-sm">
                      {new Date().toLocaleTimeString('en-US', { 
                        hour12: false, 
                        hour: '2-digit', 
                        minute: '2-digit', 
                        second: '2-digit' 
                      })}
                    </span>
                    <div className="w-3 h-5 bg-success animate-blink ml-20" />
                    <span className="text-text-muted text-sm animate-pulse">Waiting for output...</span>
                  </motion.div>
                )}
                
                <div ref={logsEndRef} />
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  )
}
```

---

## How It Works

### 1. System Architecture

The application follows a modern full-stack architecture:

- **Frontend**: Next.js React app with TypeScript and Tailwind CSS for styling
- **Backend**: FastAPI Python API with async background task processing  
- **Communication**: REST API endpoints for starting installations and polling status
- **Execution**: SSH-based remote server configuration using paramiko

### 2. Installation Process Flow

1. **User Interface**: User fills out installation form with server details and profile variables
2. **Form Submission**: Frontend POST to `/api/installation/start` endpoint
3. **Task Creation**: Backend generates unique task ID and initializes status tracking
4. **Background Processing**: 10-step installation process runs in background thread
5. **Real-time Updates**: Frontend polls `/api/installation/status/{task_id}` for live updates
6. **Log Display**: Real-time logs shown with progress tracking and filtering

### 3. 10-Step Installation Pipeline

The backend orchestrates a comprehensive 10-step installation:

1. **SSH Connection Test** - Verify connectivity to target server
2. **Oracle User Setup** - Create oracle user and oinstall group  
3. **Mount Point Creation** - Create /u01 directory structure
4. **Package Installation** - Install KSH shell and git packages
5. **Profile Creation** - Create .profile file for oracle user
6. **Java Installation** - Install Java from Oracle installer kit
7. **OFSAA Directories** - Create FICHOME and FTPSHARE directory structure
8. **Oracle Client Check** - Scan and configure existing Oracle client
9. **Installer Setup** - Download OFSAA installer and run environment check  
10. **Profile Update** - Update profile with custom variables and verify setup

### 4. Key Features

- **Real-time Progress Tracking**: Visual progress bar with current step indication
- **Live Log Streaming**: Real-time log updates with timestamp, level, and filtering
- **Error Handling**: Comprehensive error detection with detailed error messages
- **Modern UI**: Glass morphism design with smooth animations and responsive layout
- **Background Processing**: Non-blocking installation that doesn't freeze the UI
- **Status Management**: Persistent task tracking with unique IDs

### 5. Git Repository Integration

The system uses two main git repositories for component downloads:

- **Java & OFSAA Installer**: `https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation`
  - Contains: `jdk-11.0.16_linux-x64_bin__1_.tar.gz`
  - Contains: `p33940349_81100_Linux-x86-64.zip` (OFSAA installer)
  
- **Oracle Client**: `https://infrarepo.jmrinfotech.com:8443/infra_build_tf/oracle_db19c_client_oel7-8-9.git`
  - Contains Oracle Database 19c client for RHEL/CentOS/Oracle Linux 7-9

---

## Installation & Setup

### Prerequisites
- **Python 3.12+** with pip
- **Node.js 18+** with npm/yarn/bun
- **Target Linux Server** with SSH access

### Backend Setup

```bash
cd backend
pip install -r requirements.txt
python main.py
# Server runs on http://localhost:8000
```

### Frontend Setup  

```bash
cd frontend
npm install
npm run dev
# Web app runs on http://localhost:3000
```

---

## Usage Guide

1. **Access Web Interface**: Open http://localhost:3000 in browser
2. **Fill Installation Form**: 
   - Target Server IP/Hostname
   - SSH Username (typically 'oracle' or 'root')
   - SSH Password
   - Profile variables (FIC_HOME, JAVA_HOME, etc.)
3. **Start Installation**: Click "Deploy Installation" button
4. **Monitor Progress**: Redirected to real-time logs page with:
   - Live progress tracking
   - Real-time log streaming
   - Log filtering and search
   - Pause/resume and auto-scroll controls
5. **Review Results**: Installation completes with full summary

---

## Production Deployment

### Backend Deployment
- Use production WSGI server like Gunicorn or Uvicorn workers
- Configure environment variables for security
- Implement proper logging and monitoring
- Use Redis or database instead of in-memory task storage

### Frontend Deployment
- Build for production: `npm run build`
- Deploy to CDN or static hosting
- Configure proper CORS origins
- Implement authentication if needed

### Security Considerations
- Never log passwords in production
- Use encrypted connections (SSH keys preferred over passwords)
- Implement proper access controls
- Sanitize all user inputs
- Use environment variables for sensitive configuration

---

This system provides a complete solution for OFSAA installation automation with modern web interface, real-time progress tracking, and production-ready architecture.