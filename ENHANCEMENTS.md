# OFSAA Installation System - Smart Validation & Interactive Features

## 🎯 Overview

This document describes the enhanced OFSAA installation system with smart validation, user interaction improvements, and real-time interactive script execution capabilities.

## ✨ Key Enhancements

### 1. **Smart Validation Service** (`backend/services/validation.py`)

A new comprehensive validation service that provides:

- **User & Group Validation**
  - `check_user_exists()` - Verify if oracle user exists before creation
  - `check_group_exists()` - Verify if oinstall group exists before creation

- **Directory & File Validation**
  - `check_directory_exists()` - Check if paths like /u01 already exist
  - `check_file_exists()` - Verify file existence before operations

- **Package Detection**
  - `check_package_installed()` - Smart package detection (ksh, git, unzip)
  - `get_package_version()` - Get installed package versions

- **Auto-Detection**
  - `find_oracle_client()` - Auto-detect Oracle Client installations
  - `find_java_installation()` - Auto-detect Java installations

- **Utilities**
  - `backup_file()` - Create timestamped backups
  - `download_from_git()` - Download files from Git repositories

### 2. **Interactive SSH Execution** (`backend/services/ssh_service.py`)

New capability for real-time interactive command execution:

```python
async def execute_interactive_command(
    self, 
    host: str, 
    username: str, 
    password: str, 
    command: str,
    on_output_callback = None,     # Async callback for streaming output
    on_prompt_callback = None,     # Async callback for handling prompts
    timeout: int = 1800
) -> Dict[str, Any]
```

**Features:**
- Real-time output streaming
- Interactive prompt detection (Enter, Continue?, [Y/n], etc.)
- Bidirectional communication via callbacks
- Timeout handling for long-running scripts

### 3. **WebSocket Real-Time Communication**

**Backend** (`backend/main.py` & `backend/routers/installation.py`):
- WebSocket endpoint: `ws://localhost:8000/ws/{task_id}`
- `WebSocketManager` class for connection management
- Real-time output streaming
- Interactive prompt handling
- User input queue management

**Frontend** (`frontend/src/app/logs/[taskId]/page.tsx`):
- WebSocket connection with fallback to polling
- Real-time log streaming
- Interactive input prompt UI
- Keyboard shortcuts (Enter to send)

### 4. **Enhanced Service Implementations**

#### Oracle User Setup (`backend/services/oracle_user_setup.py`)
```python
# ✅ Before creating oinstall group
group_check = await self.validation.check_group_exists(host, username, password, "oinstall")
if group_check.get('exists'):
    logs.append("✓ oinstall group already exists, using existing group")
else:
    # Create group...

# ✅ Before creating oracle user
user_check = await self.validation.check_user_exists(host, username, password, "oracle")
if user_check.get('exists'):
    logs.append("✓ Oracle user already exists, skipping creation")
else:
    # Create user...
```

#### Mount Point Service (`backend/services/mount_point.py`)
```python
# ✅ Check each directory before creation
u01_check = await self.validation.check_directory_exists(host, username, password, "/u01")
if u01_check.get('exists'):
    logs.append("✓ /u01 mount point already exists")
else:
    # Create directory...

# ✅ Check subdirectories
for subdir in ["/u01/OFSAA/FICHOME", "/u01/OFSAA/FTPSHARE", "/u01/installer_kit"]:
    subdir_check = await self.validation.check_directory_exists(host, username, password, subdir)
    # Create only if needed...
```

#### Package Installation (`backend/services/packages.py`)
```python
# ✅ Smart package detection
ksh_check = await self.validation.check_package_installed(host, username, password, "ksh")
if ksh_check.get('installed'):
    logs.append(ksh_check.get('message', '✓ KSH already installed'))
else:
    packages_to_install.append("ksh")

# ✅ Get version info
git_version = await self.validation.get_package_version(host, username, password, "git")
logs.append(git_version.get('message', '✓ Git already installed'))
```

#### Profile Management (`backend/services/profile.py`)
```python
# ✅ Check existing profile and backup
profile_check = await self.validation.check_file_exists(host, username, password, "/home/oracle/.profile")
if profile_check.get('exists'):
    logs.append("✓ .profile already exists, will backup and update")
    backup_result = await self.validation.backup_file(host, username, password, "/home/oracle/.profile")
```

### 5. **Updated Profile Template**

The profile now includes all required variables from the specification:

```bash
export FIC_HOME=/u01/OFSAA/FICHOME 
export JAVA_HOME=/u01/jdk-11.0.16 
export JAVA_BIN=/u01/jdk-11.0.16/bin 
export ANT_HOME=$FIC_HOME/ficweb/apache-ant
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/client_1 
export TNS_ADMIN=/u01/app/oracle/product/19.0.0/client_1/network/admin 
export LANG=en_US.utf8
export NLS_LANG=AMERICAN_AMERICA.AL32UTF8
export ORACLE_SID=OFSAAPDB
export PATH=.:$JAVA_HOME/bin:$ORACLE_HOME/bin:/sbin:/bin:/usr/bin:/usr/kerberos/bin:/usr/local/bin:/usr/sbin:$PATH
export LD_LIBRARY_PATH=$ORACLE_HOME/lib:/lib:/usr/lib
export CLASSPATH=$ORACLE_HOME/jlib:$ORACLE_HOME/rdbms/jlib
export SHELL=/bin/ksh
export OS_VERSION="8"
export DB_CLIENT_VERSION="19.0"
ulimit -n 16000
ulimit -u 16000
ulimit -s 16000
```

### 6. **Frontend Enhancements**

#### Installation Form (`frontend/src/components/InstallationForm.tsx`)
Already includes optional fields:
- `fic_home` - FIC_HOME path (default: /u01/OFSAA/FICHOME)
- `java_home` - JAVA_HOME path (optional, auto-detected)
- `java_bin` - JAVA_BIN path (optional, auto-detected)
- `oracle_sid` - Oracle SID (default: ORCL)

#### Logs Page - Interactive Features
- **WebSocket Connection**: Real-time log streaming
- **Interactive Input UI**: 
  - Animated prompt display with warning styling
  - Input field with auto-focus
  - Send button with keyboard shortcut
  - Visual feedback for waiting state
- **Enhanced Log Display**:
  - Color-coded log levels (INFO, SUCCESS, WARNING, ERROR)
  - Search and filter capabilities
  - Auto-scroll with manual override
  - Pause/Resume functionality

## 🔧 Installation Steps Enhanced

### Step 1: Oracle User & Group Setup
- ✅ Check if oinstall group exists
- ✅ Check if oracle user exists
- ✅ Skip creation if already configured
- ✅ Clear logging for each action

### Step 2: Mount Point Creation
- ✅ Check /u01 existence
- ✅ Check subdirectories individually
- ✅ Set ownership and permissions only when needed

### Step 3: Package Installation
- ✅ Check ksh installation status
- ✅ Check git installation with version
- ✅ Check unzip installation
- ✅ Install only missing packages

### Step 4: Profile Management
- ✅ Check existing .profile
- ✅ Backup existing profile with timestamp
- ✅ Create/update with complete template
- ✅ Support selective variable updates

### Step 5: Java Installation
- ✅ Check existing Java installations
- ✅ Auto-detect JAVA_HOME
- ✅ Download from Git repository if needed
- ✅ Update profile with correct paths

### Step 6: Oracle Client Detection
- ✅ Scan common installation paths
- ✅ Verify sqlplus binary
- ✅ Auto-detect ORACLE_HOME
- ✅ Update profile with detected paths

### Step 7: OFSAA Directory Structure
- ✅ Check each directory before creation
- ✅ Skip if already exists
- ✅ Set proper ownership

### Step 8: Installer Kit Download
- ✅ Check if already downloaded
- ✅ Download from Git repository
- ✅ Extract in target location

### Step 9: Interactive Environment Check
- ✅ Execute envCheck.sh interactively
- ✅ Stream output in real-time
- ✅ Detect and handle user prompts
- ✅ Wait for user input via WebSocket
- ✅ Continue execution with user response

## 📡 WebSocket Protocol

### Message Types

**Server → Client:**
```json
{
  "type": "output",
  "data": "Command output line..."
}

{
  "type": "prompt",
  "data": "Enter value: "
}
```

**Client → Server:**
```json
{
  "type": "user_input",
  "input": "user response here"
}
```

## 🎨 UI/UX Features

### Interactive Prompt Display
- Animated slide-up entrance
- Warning color scheme (yellow/orange)
- Clear prompt message display
- Auto-focused input field
- Send button with keyboard shortcut
- Visual feedback during wait

### Log Level Styling
- **INFO**: Blue background with border
- **SUCCESS**: Green background with border
- **WARNING**: Yellow background with border
- **ERROR**: Red background with border

### Real-Time Indicators
- Live connection status
- Animated cursor when active
- Pulse animations on prompts
- Spinner on loading states

## 🔒 Error Handling

All enhanced services include:
- Comprehensive try-catch blocks
- Detailed error logging
- Graceful fallbacks
- User-friendly error messages
- Connection state management

## 📦 Dependencies Added

```
websockets>=12.0
```

## 🚀 Usage Examples

### Backend - Using Validation Service
```python
from services.validation import ValidationService

validation = ValidationService(ssh_service)

# Check if Oracle Client is already installed
oracle_home = await validation.find_oracle_client(host, username, password)
if oracle_home:
    logs.append(f"✓ Oracle Client found at: {oracle_home}")
else:
    logs.append("Oracle Client not found, will install")
```

### Backend - Interactive Execution
```python
# Define callbacks for interactive execution
async def output_callback(output: str):
    await websocket_manager.send_output(task_id, output)

async def prompt_callback(prompt: str) -> str:
    await websocket_manager.send_prompt(task_id, prompt)
    return await websocket_manager.wait_for_user_input(task_id)

# Execute interactive script
result = await ssh_service.execute_interactive_command(
    host, username, password,
    "/u01/installer_kit/OFS_BD_PACK/OFS_AAI/bin/envCheck.sh",
    on_output_callback=output_callback,
    on_prompt_callback=prompt_callback
)
```

### Frontend - WebSocket Connection
```typescript
const websocket = new WebSocket(`ws://localhost:8000/ws/${taskId}`)

websocket.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  if (data.type === 'output') {
    // Add to logs
    setLogs(prev => [...prev, formatLogEntry(data.data)])
  } else if (data.type === 'prompt') {
    // Show input prompt
    setIsWaitingForInput(true)
    setCurrentPrompt(data.data)
  }
}

// Send user input
websocket.send(JSON.stringify({
  type: 'user_input',
  input: userInput
}))
```

## ✅ Testing Checklist

- [ ] Run installation twice to verify "already exists" detection
- [ ] Test with custom profile variables (java_home, oracle_sid)
- [ ] Test Oracle Client auto-detection with multiple paths
- [ ] Test interactive script with various prompts
- [ ] Test WebSocket connection and reconnection
- [ ] Test Git repository downloads
- [ ] Verify all log messages are clear and informative
- [ ] Test error scenarios and fallback behavior

## 🎯 Benefits

1. **Idempotent Installation**: Can be run multiple times safely
2. **Smart Detection**: Auto-detects existing installations
3. **User-Friendly**: Clear progress indication and helpful messages
4. **Interactive**: Supports scripts requiring user input
5. **Real-Time**: Live output streaming and status updates
6. **Flexible**: Customizable profile variables
7. **Production-Ready**: Comprehensive error handling and logging

## 📚 Next Steps

To use the enhanced system:

1. Install dependencies: `pip install -r backend/requirements.txt`
2. Start backend: `cd backend && python main.py`
3. Start frontend: `cd frontend && bun run dev`
4. Access at: `http://localhost:3000`
5. Fill form with server details and custom variables
6. Monitor real-time logs at `/logs/{task_id}`
7. Respond to interactive prompts when displayed

---

**Note**: All enhancements maintain backward compatibility with existing installations while adding intelligent validation and interactive capabilities.
