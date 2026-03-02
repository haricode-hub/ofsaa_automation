@echo off
REM OFSAA Installation - PM2 Quick Start Script for Windows
REM Usage: start-pm2.bat

echo.
echo ======================================
echo OFSAA Installation - PM2 Setup
echo ======================================
echo.

REM Check if PM2 is installed
where pm2 >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: PM2 is not installed
    echo Install it with: npm install -g pm2
    exit /b 1
)

REM Check if uv is installed
where uv >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: uv is not installed (Python package manager)
    echo Install it with: pip install uv
    exit /b 1
)

REM Check if Bun is installed
where bun >nul 2>nul
if %ERRORLEVEL% NEQ 0 (
    echo ERROR: bun is not installed
    echo Install it with: npm install -g bun
    exit /b 1
)

echo ✓ All prerequisites found
echo.

REM Step 1: Setup Frontend
echo Step 1: Installing frontend dependencies...
cd frontend
call bun install
if errorlevel 1 (
    echo ERROR: Failed to install frontend dependencies
    cd ..
    exit /b 1
)

if not exist ".env.local" (
    echo Creating .env.local with API URL...
    (
        echo NEXT_PUBLIC_API_URL=http://192.168.0.165:8000
    ) > .env.local
)
cd ..
echo ✓ Frontend setup complete
echo.

REM Step 2: Build Frontend
echo Step 2: Building frontend for production...
cd frontend
call bun run build
if errorlevel 1 (
    echo ERROR: Failed to build frontend
    cd ..
    exit /b 1
)
cd ..
echo ✓ Frontend build complete
echo.

REM Step 3: Setup Backend
echo Step 3: Installing backend dependencies...
cd backend
call uv sync
if errorlevel 1 (
    echo ERROR: Failed to install backend dependencies
    cd ..
    exit /b 1
)

if not exist ".env" (
    echo Creating .env file...
    copy .env.example .env>nul
    echo ⚠ Please edit backend\.env with your Git and database credentials
)
cd ..
echo ✓ Backend setup complete
echo.

REM Step 4: Check ecosystem.config.js
if not exist "ecosystem.config.js" (
    echo ERROR: ecosystem.config.js not found in project root
    exit /b 1
)
echo ✓ PM2 configuration file found
echo.

REM Step 5: Start with PM2
echo Step 5: Starting services with PM2...
call pm2 delete all 2>nul
call pm2 start ecosystem.config.js
if errorlevel 1 (
    echo ERROR: Failed to start services with PM2
    exit /b 1
)
echo ✓ Services started
echo.

REM Step 6: Save PM2 config for auto-start
echo Step 6: Saving PM2 configuration...
call pm2 startup
call pm2 save
echo ✓ PM2 auto-start configured
echo.

echo ======================================
echo Setup Complete!
echo ======================================
echo.
echo Access the application at:
echo   Frontend: http://192.168.0.165:3000
echo   Backend:  http://192.168.0.165:8000
echo.
echo View logs:
echo   pm2 logs
echo   pm2 logs frontend
echo   pm2 logs backend
echo.
echo Monitor services:
echo   pm2 monit
echo.

pause
