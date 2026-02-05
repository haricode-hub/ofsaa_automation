# OFSAA Installation System - Complete Guide with Examples

## 📋 **System Overview**

This automated OFSAA installation system performs a complete 7-step Oracle Financial Services Analytical Applications setup using FastAPI backend, Next.js frontend, and SSH automation.

---

## 🏗️ **Architecture Flow**

```
[Frontend Form] → [FastAPI Backend] → [SSH Commands] → [Target Server] → [Real-time Logs] → [User Interface]
```

### **Technology Stack**
- **Backend**: FastAPI + Python + Paramiko SSH
- **Frontend**: Next.js + React + WebSocket
- **Infrastructure**: Terraform + Git repositories
- **Authentication**: SSH key/password authentication

---

## 🎯 **Complete 7-Step Installation Process**

### **Step 1: Oracle User & oinstall Group**
```bash
# Commands executed on target server
sudo groupadd oinstall
sudo useradd -g oinstall oracle
sudo passwd oracle
sudo usermod -aG wheel oracle  # Add to sudoers if needed
```

**Example Output:**
```
✓ Step 1: Oracle User and oinstall Group Creation
  → oinstall group created successfully
  → oracle user created and assigned to oinstall group
  → User permissions configured for OFSAA installation
```

---

### **Step 2: Mount Point Creation**
```bash
# Commands executed on target server
sudo mkdir -p /u01/OFSAA/FICHOME
sudo mkdir -p /u01/OFSAA/FTPSHARE  
sudo mkdir -p /u01/installer_kit
sudo chown -R oracle:oinstall /u01
sudo chmod -R 755 /u01
```

**Example Output:**
```
✓ Step 2: Mount Point Creation
  → /u01/OFSAA/FICHOME (Application home)
  → /u01/OFSAA/FTPSHARE (FTP share directory)  
  → /u01/installer_kit (Installation files)
  → Ownership set to oracle:oinstall
  → Permissions configured (755)
```

---

### **Step 3: KSH and Git Installation**
```bash
# Commands executed on target server
sudo apt-get update -y
sudo apt-get install ksh git curl wget -y
which ksh && which git  # Verification
```

**Example Output:**
```
✓ Step 3: KSH and Git Installation
  → Package repository updated
  → Korn Shell (ksh) installed: /bin/ksh
  → Git installed: /usr/bin/git
  → Additional tools installed (curl, wget)
```

---

### **Step 4: Complete Profile Creation**
The system creates `/home/oracle/.profile` with your complete template:

```bash
# Complete profile template deployed
cat > /home/oracle/.profile << 'EOF'
alias c=clear

alias p="ps -ef | grep $LOGNAME"

alias pp="ps -fu $LOGNAME"

PS1='$PWD>'

export PS1
 
stty erase ^?

#set -o vi
 
echo $PATH

export FIC_HOME=/u01/OFSAA/FICHOME 
 
export JAVA_HOME=/u01/jdk-11.0.16 

export JAVA_BIN=/u01/jdk-11.0.16/bin 

export ANT_HOME=$FIC_HOME/ficweb/apache-ant

#export ANT_HOME=$FIC_HOME/ficweb/apache-ant
 
export ORACLE_HOME=/u01/app/oracle/product/19.0.0/client_1 
export TNS_ADMIN=/u01/app/oracle/product/19.0.0/client_1/network/admin 
export LANG=en_US.utf8

export NLS_LANG=AMERICAN_AMERICA.AL32UTF8
 
export ORACLE_SID=OFSAAPDB

export PATH=.:$JAVA_HOME/bin:$ORACLE_HOME/bin:/sbin:/bin:/usr/bin:/usr/kerberos/bin:/usr/local/bin:/usr/sbin:$PATH

#export PATH=$ORACLE_HOME/bin:$PATH:$JAVA_HOME/bin
 
export LD_LIBRARY_PATH=$ORACLE_HOME/lib:/lib:/usr/lib

export CLASSPATH=$ORACLE_HOME/jlib:$ORACLE_HOME/rdbms/jlib

export SHELL=/bin/ksh

echo "********************************************************"

echo "   THIS IS FCCM SKND SETUP,PLEASE DO NOT MAKE ANY CHANGE   "

echo "           UNAUTHORISED ACCESS PROHIBITED             "

echo "                                                      "

echo "********************************************************"

echo PROFILE EXECUTED

echo $PATH

echo "SHELL Check :: " $SHELL

set -o emacs

umask 0027 

export OS_VERSION="8"

export DB_CLIENT_VERSION="19.0"

ulimit -n 16000

ulimit -u 16000

ulimit -s 16000
EOF
```

**Example Output:**
```
✓ Step 4: Complete Profile Creation
  → Complete FCCM SKND profile template deployed
  → All aliases and environment variables configured
  → Security warnings and shell settings applied
  → File ownership: oracle:oinstall (644 permissions)
```

---

### **Step 5: Java Installation**
```bash
# Commands executed on target server
cd /u01/installer_kit
wget --no-check-certificate https://infrarepo.jmrinfotech.com:8443/ofsaa_agentic/ofsaa_auto_installation/raw/main/jdk-11.0.16_linux-x64_bin__1_.tar.gz

# Extract to profile path
mkdir -p /u01
tar -xzf jdk-11.0.16_linux-x64_bin__1_.tar.gz -C /u01
chown -R oracle:oinstall /u01/jdk-11.0.16
chmod -R 755 /u01/jdk-11.0.16

# Verification
/u01/jdk-11.0.16/bin/java -version
```

**Example Output:**
```
✓ Step 5: Java Installation Complete
  → JDK 11.0.16 downloaded from repository
  → Extracted to: /u01/jdk-11.0.16
  → Java verification: openjdk version "11.0.16" 2022-07-19
  → JAVA_HOME matches profile: /u01/jdk-11.0.16
  → JAVA_BIN matches profile: /u01/jdk-11.0.16/bin
```

---

### **Step 6: Oracle Client Installation via Terraform**
```bash
# Commands executed on target server

# 1. Install terraform
wget -O- https://apt.releases.hashicorp.com/gpg | gpg --dearmor | sudo tee /usr/share/keyrings/hashicorp-archive-keyring.gpg
echo "deb [signed-by=/usr/share/keyrings/hashicorp-archive-keyring.gpg] https://apt.releases.hashicorp.com $(lsb_release -cs) main" | sudo tee /etc/apt/sources.list.d/hashicorp.list
sudo apt-get update && sudo apt-get install terraform -y

# 2. Clone repository
cd /tmp && rm -rf oracle_db19c_client_oel7-8-9 2>/dev/null
git clone https://infrarepo.jmrinfotech.com:8443/infra_build_tf/oracle_db19c_client_oel7-8-9.git
cd oracle_db19c_client_oel7-8-9

# 3. Configure terraform.tfvars
cat > terraform.tfvars << 'EOF'
# Target host configuration
target_host = "192.168.1.100"
oracle_client_version = "19.0"
oracle_home = "/u01/app/oracle/product/19.0.0/client_1"
tns_admin = "/u01/app/oracle/product/19.0.0/client_1/network/admin"
oracle_sid = "OFSAAPDB"
EOF

# 4. Deploy with terraform
terraform init
terraform apply -auto-approve

# 5. Set permissions
sudo chown -R oracle:oinstall /u01/app/oracle
sudo chmod -R 755 /u01/app/oracle
```

**Example Output:**
```
✓ Step 6: Oracle Client Installation Complete
  → Repository cloned from infrarepo.jmrinfotech.com
  → Terraform configured with target host IP
  → Oracle 19c client installed via terraform
  → ORACLE_HOME configured: /u01/app/oracle/product/19.0.0/client_1
  → TNS_ADMIN configured: /u01/app/oracle/product/19.0.0/client_1/network/admin
  → ORACLE_SID configured: OFSAAPDB
  → Oracle client ready for OFSAA installation
```

---

### **Step 7: Frontend Variable Overrides**
```bash
# Commands executed based on frontend input
sed -i 's|export FIC_HOME=.*|export FIC_HOME=/u01/OFSAA/FICHOME|g' /home/oracle/.profile
sed -i 's|export JAVA_HOME=.*|export JAVA_HOME=/u01/jdk-11.0.16|g' /home/oracle/.profile
sed -i 's|export JAVA_BIN=.*|export JAVA_BIN=/u01/jdk-11.0.16/bin|g' /home/oracle/.profile
sed -i 's|export ORACLE_SID=.*|export ORACLE_SID=OFSAAPDB|g' /home/oracle/.profile

# Verification
grep -E "(FIC_HOME|JAVA_HOME|JAVA_BIN|ORACLE_SID)=" /home/oracle/.profile
```

**Example Output:**
```
✓ Step 7: Custom Profile Variables Updated
  → FIC_HOME: /u01/OFSAA/FICHOME
  → JAVA_HOME: /u01/jdk-11.0.16
  → JAVA_BIN: /u01/jdk-11.0.16/bin
  → ORACLE_SID: OFSAAPDB
  → Profile variables synchronized with frontend preferences
  → Environment ready for OFSAA installation
```

---

## 🖥️ **Frontend Interface Examples**

### **Installation Form Input**
```javascript
// Example frontend form data
{
  "host": "192.168.1.100",
  "username": "root", 
  "password": "secure_password",
  "fic_home": "/u01/OFSAA/FICHOME",        // Optional override
  "custom_java_home": "/u01/jdk-11.0.16",  // Optional override
  "custom_java_bin": "/u01/jdk-11.0.16/bin", // Optional override
  "custom_oracle_sid": "OFSAAPDB"          // Optional override
}
```

### **API Request Example**
```bash
curl -X POST "http://localhost:8000/api/installation/run" \
  -H "Content-Type: application/json" \
  -d '{
    "host": "192.168.1.100",
    "username": "root",
    "password": "secure_password",
    "fic_home": "/u01/OFSAA/FICHOME",
    "custom_java_home": "/u01/jdk-11.0.16",
    "custom_java_bin": "/u01/jdk-11.0.16/bin", 
    "custom_oracle_sid": "OFSAAPDB"
  }'
```

### **API Response Example**
```json
{
  "task_id": "12345678-1234-1234-1234-123456789012",
  "message": "Installation started successfully",
  "status": "in_progress",
  "logs_url": "ws://localhost:8000/ws/installation/logs/12345678-1234-1234-1234-123456789012"
}
```

---

## 📊 **Real-Time Logging Examples**

### **WebSocket Log Stream**
```javascript
// Frontend WebSocket connection
const ws = new WebSocket('ws://localhost:8000/ws/installation/logs/12345678-1234-1234-1234-123456789012');

ws.onmessage = (event) => {
  const logEntry = JSON.parse(event.data);
  console.log(`${logEntry.timestamp}: ${logEntry.message}`);
};
```

### **Sample Log Output**
```
2026-02-04 10:15:30 → Step 1: Creating oracle user and oinstall group
2026-02-04 10:15:32 ✓ oracle user created successfully
2026-02-04 10:15:33 → Step 2: Creating mount point /u01
2026-02-04 10:15:35 ✓ Mount point created and configured
2026-02-04 10:15:36 → Step 3: Installing KSH and Git
2026-02-04 10:15:45 ✓ KSH and Git installed successfully
2026-02-04 10:15:46 → Step 4: Creating complete profile template
2026-02-04 10:15:47 ✓ Complete FCCM SKND profile deployed
2026-02-04 10:15:48 → Step 5: Installing Java from repository
2026-02-04 10:16:15 ✓ Java 11.0.16 installed at /u01/jdk-11.0.16
2026-02-04 10:16:16 → Step 6: Installing Oracle client via terraform
2026-02-04 10:18:30 ✓ Oracle client installed successfully
2026-02-04 10:18:31 → Step 7: Applying frontend variable overrides
2026-02-04 10:18:32 ✓ All 7 steps completed successfully
```

---

## ⚙️ **Configuration Examples**

### **Default Profile Variables**
```bash
# These are the default values from your profile template
export FIC_HOME=/u01/OFSAA/FICHOME 
export JAVA_HOME=/u01/jdk-11.0.16 
export JAVA_BIN=/u01/jdk-11.0.16/bin 
export ORACLE_SID=OFSAAPDB
```

### **Frontend Override Examples**

**Example 1: Custom ORACLE_SID**
```json
{
  "host": "192.168.1.100",
  "username": "root",
  "password": "password",
  "custom_oracle_sid": "PRODDB"
}
```
Result: `export ORACLE_SID=PRODDB`

**Example 2: Custom Java Path**
```json
{
  "host": "192.168.1.100", 
  "username": "root",
  "password": "password",
  "custom_java_home": "/opt/java/jdk-11",
  "custom_java_bin": "/opt/java/jdk-11/bin"
}
```
Result: 
```bash
export JAVA_HOME=/opt/java/jdk-11
export JAVA_BIN=/opt/java/jdk-11/bin
```

**Example 3: Using All Defaults**
```json
{
  "host": "192.168.1.100",
  "username": "root", 
  "password": "password"
}
```
Result: Uses all profile template defaults

---

## 🔍 **Verification Examples**

### **Post-Installation Verification**
```bash
# SSH into target server as oracle user
ssh oracle@192.168.1.100

# Check profile loading
source ~/.profile
# Should display:
# ********************************************************
#    THIS IS FCCM SKND SETUP,PLEASE DO NOT MAKE ANY CHANGE   
#            UNAUTHORISED ACCESS PROHIBITED             
#                                                      
# ********************************************************
# PROFILE EXECUTED
# /u01/jdk-11.0.16/bin:/u01/app/oracle/product/19.0.0/client_1/bin:/sbin:/bin:/usr/bin:/usr/kerberos/bin:/usr/local/bin:/usr/sbin:...
# SHELL Check :: /bin/ksh

# Verify Java
java -version
# openjdk version "11.0.16" 2022-07-19

# Verify Oracle client
echo $ORACLE_HOME
# /u01/app/oracle/product/19.0.0/client_1

# Check directory structure
ls -la /u01/
# drwxr-xr-x oracle oinstall OFSAA/
# drwxr-xr-x oracle oinstall jdk-11.0.16/
# drwxr-xr-x oracle oinstall app/

# Test aliases
c  # Clears screen
p  # Shows processes for current user
```

---

## 🚀 **Complete Usage Example**

### **Scenario: Installing OFSAA on production server**

1. **Start Services:**
```bash
# Backend
cd backend && python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Frontend  
cd frontend && npm run dev
```

2. **Fill Installation Form:**
- Host: `192.168.10.50`
- Username: `root`
- Password: `prod_password`
- Custom ORACLE_SID: `OFSAADB`

3. **Monitor Progress:**
- Real-time logs show each step
- Total time: ~15-20 minutes
- WebSocket provides live updates

4. **Verification:**
```bash
ssh oracle@192.168.10.50
source ~/.profile
# Profile loads with security messages
java -version  # Java 11.0.16 confirmed
echo $ORACLE_SID  # OFSAADB confirmed
```

5. **Final State:**
```
✅ Oracle user and oinstall group created
✅ Mount point /u01 configured with proper structure  
✅ KSH and Git installed
✅ Complete FCCM SKND profile deployed
✅ Java 11.0.16 installed at /u01/jdk-11.0.16
✅ Oracle 19c client installed via terraform
✅ Environment variables customized per frontend input
✅ System ready for OFSAA application installation
```

---

## 📈 **Performance Metrics**

| Step | Typical Duration | Key Operations |
|------|-----------------|----------------|
| Step 1 | 30-60 seconds | User/group creation |
| Step 2 | 10-30 seconds | Directory creation |  
| Step 3 | 60-120 seconds | Package installation |
| Step 4 | 5-15 seconds | Profile creation |
| Step 5 | 3-8 minutes | Java download/install |
| Step 6 | 8-15 minutes | Oracle client terraform |
| Step 7 | 5-15 seconds | Variable updates |
| **Total** | **12-20 minutes** | **Complete installation** |

---

This system provides a complete, automated OFSAA environment setup with your exact production profile template while maintaining flexibility for environment-specific customizations through the frontend interface.