# Quick Reference Guide - OFSAA Installation Enhancements

## 🎯 Quick Start

### Backend
```bash
cd backend
pip install -r requirements.txt
python main.py
```

### Frontend
```bash
cd frontend
bun install
bun run dev
```

## 📡 API Endpoints

### HTTP Endpoints
- `POST /api/installation/start` - Start installation
- `GET /api/installation/status/{task_id}` - Get status
- `POST /api/installation/test-connection` - Test SSH
- `GET /api/installation/tasks` - List all tasks

### WebSocket
- `ws://localhost:8000/ws/{task_id}` - Real-time updates

## 🔧 Using the Validation Service

```python
from services.validation import ValidationService

validation = ValidationService(ssh_service)

# Check user existence
user_exists = await validation.check_user_exists(host, user, pwd, "oracle")
if user_exists.get('exists'):
    logs.append("✓ Oracle user already exists")

# Check package installation  
ksh_status = await validation.check_package_installed(host, user, pwd, "ksh")
if ksh_status.get('installed'):
    logs.append(f"✓ KSH at {ksh_status.get('path')}")

# Auto-detect Oracle Client
oracle_home = await validation.find_oracle_client(host, user, pwd)
if oracle_home:
    logs.append(f"✓ Oracle Client found at {oracle_home}")

# Auto-detect Java
java_home = await validation.find_java_installation(host, user, pwd)
if java_home:
    logs.append(f"✓ Java found at {java_home}")

# Backup file
backup = await validation.backup_file(host, user, pwd, "/path/to/file")
# Creates: /path/to/file.backup.20260205_143022
```

## 🔄 Interactive Command Execution

```python
from services.ssh_service import SSHService

ssh = SSHService()

# Define callbacks
async def on_output(output: str):
    # Stream to logs/WebSocket
    print(f"Output: {output}")

async def on_prompt(prompt: str) -> str:
    # Wait for user input
    print(f"Prompt detected: {prompt}")
    return await websocket_manager.wait_for_user_input(task_id)

# Execute interactively
result = await ssh.execute_interactive_command(
    host="192.168.1.100",
    username="root",
    password="secret",
    command="/path/to/script.sh",
    on_output_callback=on_output,
    on_prompt_callback=on_prompt,
    timeout=1800  # 30 minutes
)
```

## 🌐 WebSocket Integration

### Backend
```python
# In installation_service.py
from routers.installation import websocket_manager

# Stream output
await websocket_manager.send_output(task_id, "Installing packages...")

# Send prompt
await websocket_manager.send_prompt(task_id, "Enter hostname: ")

# Wait for user input
user_response = await websocket_manager.wait_for_user_input(task_id, timeout=300)
```

### Frontend
```typescript
// Connect
const ws = new WebSocket(`ws://localhost:8000/ws/${taskId}`)

// Receive messages
ws.onmessage = (event) => {
  const data = JSON.parse(event.data)
  
  if (data.type === 'output') {
    setLogs(prev => [...prev, formatLogEntry(data.data)])
  } else if (data.type === 'prompt') {
    setIsWaitingForInput(true)
    setCurrentPrompt(data.data)
  }
}

// Send user input
ws.send(JSON.stringify({
  type: 'user_input',
  input: userInput
}))
```

## 📝 Smart Logging Patterns

### "Already Exists" Pattern
```python
logs.append("→ Checking for oracle user...")
user_check = await validation.check_user_exists(host, user, pwd, "oracle")

if user_check.get('exists'):
    logs.append("✓ Oracle user already exists, skipping creation")
else:
    logs.append("Creating oracle user...")
    # Create user...
    logs.append("✓ Oracle user created successfully")
```

### Package Detection Pattern
```python
logs.append("→ Checking for KSH (Korn Shell)...")
ksh_check = await validation.check_package_installed(host, user, pwd, "ksh")

if ksh_check.get('installed'):
    logs.append(ksh_check.get('message', '✓ KSH already installed'))
else:
    logs.append("KSH not found, will install")
    packages_to_install.append("ksh")
```

### Auto-Detection Pattern
```python
logs.append("→ Auto-detecting Java installation...")
java_home = await validation.find_java_installation(host, user, pwd)

if java_home:
    logs.append(f"✓ Java found at: {java_home}")
    # Use detected path
else:
    logs.append("Java not found, will download and install")
    # Download and install
```

## 🎨 Frontend Log Styling

### Log Entry Interface
```typescript
interface LogEntry {
  timestamp: string
  level: 'INFO' | 'ERROR' | 'SUCCESS' | 'WARNING'
  message: string
}
```

### Log Level Colors
- **INFO**: Blue (`bg-blue-500/20 text-blue-300`)
- **SUCCESS**: Green (`bg-green-500/20 text-green-300`)
- **WARNING**: Yellow (`bg-yellow-500/20 text-yellow-300`)
- **ERROR**: Red (`bg-red-500/20 text-red-300`)

### Format Log Entry
```typescript
const formatLogEntry = (logText: string): LogEntry => {
  const timestamp = new Date().toLocaleTimeString('en-US', { 
    hour12: false,
    hour: '2-digit',
    minute: '2-digit',
    second: '2-digit'
  })
  
  let level: LogEntry['level'] = 'INFO'
  if (logText.includes('ERROR') || logText.includes('failed')) {
    level = 'ERROR'
  } else if (logText.includes('SUCCESS') || logText.includes('✓')) {
    level = 'SUCCESS'
  } else if (logText.includes('WARNING')) {
    level = 'WARNING'
  }
  
  return { timestamp, level, message: logText.trim() }
}
```

## 🔍 Common Validation Checks

### Pre-Installation Checks
```python
# 1. Check SSH connection
conn_test = await ssh_service.test_connection(host, username, password)
if not conn_test['success']:
    return {"error": "SSH connection failed"}

# 2. Check if user exists
user_exists = await validation.check_user_exists(host, username, password, "oracle")

# 3. Check if directory exists
dir_exists = await validation.check_directory_exists(host, username, password, "/u01")

# 4. Check if package is installed
pkg_installed = await validation.check_package_installed(host, username, password, "ksh")

# 5. Check if file exists
file_exists = await validation.check_file_exists(host, username, password, "/home/oracle/.profile")
```

### Post-Installation Verification
```python
# Verify Java installation
java_check = await ssh_service.execute_command(
    host, username, password,
    "java -version"
)

# Verify Oracle Client
sqlplus_check = await ssh_service.execute_command(
    host, username, password,
    "sqlplus -v"
)

# Verify profile sourcing
profile_check = await ssh_service.execute_command(
    host, username, password,
    "sudo -u oracle bash -c 'source /home/oracle/.profile && echo $JAVA_HOME'"
)
```

## 🛠️ Troubleshooting

### WebSocket Connection Issues
```typescript
// Add error handling
ws.onerror = (error) => {
  console.error('WebSocket error:', error)
  // Fallback to HTTP polling
  startPolling()
}

ws.onclose = () => {
  console.log('WebSocket closed, falling back to polling')
  startPolling()
}
```

### SSH Timeout Issues
```python
# Increase timeout for long-running commands
result = await ssh_service.execute_command(
    host, username, password,
    command,
    timeout=1800  # 30 minutes
)
```

### Interactive Script Not Responding
```python
# Check prompt detection patterns
prompt_patterns = [
    'Enter', 'enter', 'Input', 'input', 'Type', 'type',
    '[Y/n]', '[y/N]', 'Continue?', 'Proceed?', 'password:', 'Password:'
]

# Add custom patterns if needed
```

## 📊 Monitoring & Debugging

### Enable Debug Logging
```python
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
```

### Check Installation Status
```bash
curl http://localhost:8000/api/installation/status/{task_id}
```

### View All Tasks
```bash
curl http://localhost:8000/api/installation/tasks
```

### Test SSH Connection
```bash
curl -X POST http://localhost:8000/api/installation/test-connection \
  -H "Content-Type: application/json" \
  -d '{"host":"192.168.1.100","username":"root","password":"secret"}'
```

## ⚡ Performance Tips

1. **Batch Operations**: Use multi_replace_string_in_file for multiple edits
2. **Minimize SSH Calls**: Check multiple conditions in one command when possible
3. **Use Async**: All service methods are async - await them properly
4. **WebSocket Over Polling**: WebSocket has lower overhead
5. **Timeout Management**: Set appropriate timeouts for long operations

## 🔐 Security Notes

- Never log passwords
- Use environment variables for sensitive data
- Validate all user inputs
- Sanitize file paths
- Use parameterized commands when possible

## 📚 Additional Resources

- **ENHANCEMENTS.md** - Full technical documentation
- **IMPLEMENTATION_SUMMARY.md** - Implementation details
- **Backend Code** - Inline comments and docstrings
- **Frontend Code** - TypeScript types and component docs

---

**Need Help?** Check the error logs in the terminal and browser console.
