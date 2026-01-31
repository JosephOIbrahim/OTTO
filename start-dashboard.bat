@echo off
echo ========================================
echo  Otto Dashboard - Starting...
echo ========================================
echo.

:: Start WebSocket server in background
echo Starting WebSocket server on port 8081...
start /B python src\otto\websocket_server.py --port 8081

:: Wait a moment for WebSocket to start
timeout /t 2 /nobreak >nul

:: Start the dashboard
echo Starting Dashboard on port 5050...
cd src\dashboard
npm run dev

pause
