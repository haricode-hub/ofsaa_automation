# OFSAA Installation App — Run Guide

## How Environment Switching Works

No code changes needed between local and production. Everything is controlled by env files:

| File | When used | Controls |
|------|-----------|----------|
| `frontend/.env.local` | `bun run dev` (local) | Frontend calls `localhost:8000` |
| `frontend/.env.production` | `bun run build` (server) | Frontend calls `192.168.0.166:8000` |
| `ALLOWED_ORIGIN` env var | Backend at runtime | Which origins CORS allows |

---

## Option 1 — Local Development (your laptop)

### Prerequisites
```bash
bun --version      # https://bun.sh
uv --version       # https://astral.sh/uv
```

### Run

```bash
# Terminal 1 — Backend
cd backend
cp .env.example .env      # first time only — fill in your values
uv sync                   # first time only
uv run python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000

# Terminal 2 — Frontend
cd frontend
bun install               # first time only
bun run dev
```

Open: **`http://localhost:3000`**

### How it works locally
- `frontend/.env.local` has `NEXT_PUBLIC_API_URL=http://localhost:8000`
- `bun run dev` picks this up automatically — no build needed
- Backend CORS allows `localhost:3000` by default (`ALLOWED_ORIGIN` not needed)

---

## Option 2 — Production Server (192.168.0.166) via PM2

### Prerequisites
```bash
npm install -g pm2
bun --version
uv --version
```

### One-Time Setup (run once on the server)

**1. Set up backend env:**
```bash
cp backend/.env.example backend/.env
vi backend/.env   # fill in Git repo URL, credentials, etc.
```

Key values in `backend/.env`:
```dotenv
ALLOWED_ORIGIN=http://192.168.0.166      # allows browser at :3000 to reach backend
OFSAA_REPO_URL=https://github.com/yourorg/ofsaa-repo.git
OFSAA_REPO_DIR=/u01/OFSAA_REPO
OFSAA_GIT_USERNAME=your_git_username
OFSAA_GIT_PASSWORD=your_git_password
OFSAA_INSTALLER_ZIP_NAME=OFS_BD_PACK.zip
OFSAA_JAVA_ARCHIVE_HINT=jdk-11
OFSAA_FAST_CONFIG_APPLY=1
OFSAA_ENABLE_CONFIG_PUSH=0
```

**2. Install dependencies:**
```bash
cd backend && uv sync && cd ..
cd frontend && bun install && cd ..
```

**3. Build frontend:**
```bash
cd frontend && bun run build && cd ..
# Picks up frontend/.env.production → NEXT_PUBLIC_API_URL=http://192.168.0.166:8000
```

**4. Start with PM2:**
```bash
pm2 start ecosystem.config.js
```

Expected output:
```
┌────┬──────────┬──────┬────────┐
│ id │ name     │ mode │ status │
├────┼──────────┼──────┼────────┤
│ 0  │ frontend │ fork │ online │
│ 1  │ backend  │ fork │ online │
└────┴──────────┴──────┴────────┘
```

Open: **`http://192.168.0.166:3000`**

**5. Auto-start on reboot (optional):**
```bash
pm2 save
pm2 startup   # run the command it outputs as root
```

---

## Redeploy After Code Changes (server)

```bash
git pull

# Only if frontend files changed:
cd frontend && bun run build && cd ..

# Only if pyproject.toml changed:
cd backend && uv sync && cd ..

pm2 restart all
```

---

## Changing the Server IP

If the server IP changes:

```bash
# 1. Update frontend/.env.production
echo "NEXT_PUBLIC_API_URL=http://<NEW_IP>:8000" > frontend/.env.production

# 2. Update backend/.env  → ALLOWED_ORIGIN=http://<NEW_IP>

# 3. Rebuild and restart
cd frontend && bun run build && cd ..
pm2 restart all
```

---

## PM2 Commands Reference

```bash
pm2 status                  # Show all processes
pm2 logs                    # Live logs (Ctrl+C to exit)
pm2 logs frontend           # Frontend logs only
pm2 logs backend            # Backend logs only
pm2 restart all             # Restart both
pm2 restart backend         # Restart backend only
pm2 stop all                # Stop both
pm2 delete all              # Remove from PM2 list
```

---

## File Reference

| File | Purpose |
|------|---------|
| `frontend/.env.local` | Local dev — `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| `frontend/.env.production` | Server build — `NEXT_PUBLIC_API_URL=http://192.168.0.166:8000` |
| `backend/.env` | Backend secrets + `ALLOWED_ORIGIN=http://192.168.0.166` |
| `backend/.env.example` | Template for `backend/.env` |
| `ecosystem.config.js` | PM2 process config for server |

---

## Troubleshooting

**"Connection Failed" on submit**
- Open DevTools → Network tab → click Deploy
- If **no request fires** → form validation error (DB SYS password or JDBC service field is empty)
- If **request fires and fails** → check: `pm2 logs backend --lines 20`

**`ERR_CONNECTION_TIMED_OUT` in browser console**
- Port 8000 is blocked by firewall:
```bash
sudo firewall-cmd --add-port=8000/tcp --permanent
sudo firewall-cmd --add-port=3000/tcp --permanent
sudo firewall-cmd --reload
# or iptables:
sudo iptables -I INPUT -p tcp --dport 8000 -j ACCEPT
sudo iptables -I INPUT -p tcp --dport 3000 -j ACCEPT
```

**`No route to host` on curl**
```bash
curl http://localhost:8000/     # if this works, it's a firewall issue on the IP
# Apply iptables rules above
```

**pm2 shows `errored`**
```bash
pm2 logs backend --lines 50
pm2 logs frontend --lines 50
```

**Frontend built with wrong IP (still calling localhost in production)**
```bash
grep -r "192.168.0.166" frontend/.next/static --include="*.js" -l
# If no results → rebuild: cd frontend && bun run build
```
