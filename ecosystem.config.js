// PM2 process configuration for OFSAA Installation Automation
// Set SERVER_IP, BACKEND_PORT, FRONTEND_PORT as environment variables, or edit defaults below.

const SERVER_IP = process.env.SERVER_IP || 'localhost';
const BACKEND_PORT = process.env.BACKEND_PORT || 8000;
const FRONTEND_PORT = process.env.FRONTEND_PORT || 3000;

module.exports = {
  apps: [
    {
      name: 'ofsaa-frontend',
      script: 'bun',
      args: `run start -- -H 0.0.0.0 -p ${FRONTEND_PORT}`,
      cwd: './frontend',
      env: {
        NODE_ENV: 'production',
        NEXT_PUBLIC_API_URL: `http://${SERVER_IP}:${BACKEND_PORT}`,
      },
      instances: 1,
      exec_mode: 'fork',
      watch: false,
      max_memory_restart: '1G',
      merge_logs: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
    },
    {
      name: 'ofsaa-backend',
      script: 'uv',
      args: `run python -m uvicorn main:app --host 0.0.0.0 --port ${BACKEND_PORT}`,
      cwd: './backend',
      interpreter: 'none',
      env: {
        PYTHONUNBUFFERED: '1',
        ALLOWED_ORIGIN: `http://${SERVER_IP}:${FRONTEND_PORT}`,
      },
      instances: 1,
      exec_mode: 'fork',
      watch: false,
      max_memory_restart: '1G',
      merge_logs: true,
      autorestart: true,
      max_restarts: 10,
      min_uptime: '10s',
    },
  ],
};
