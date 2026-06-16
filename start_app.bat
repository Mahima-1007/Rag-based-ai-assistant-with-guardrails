@echo off
echo ========================================================
echo           Starting RAG AI Assistant
echo ========================================================
echo.

echo [1/3] Starting backend services (Docker)...
docker start rag-redis rag-qdrant rag-backend

echo.
echo [2/3] Starting frontend server...
start "RAG Frontend" cmd /k "cd /d d:\Rag-Based-Ai-Assistant-pro\frontend && npm run dev"

echo.
echo [3/3] Launching application in your browser...
timeout /t 4 /nobreak > NUL
start http://localhost:5173

echo.
echo Done! The app should now be open in your browser.
echo You can safely close this script window.
timeout /t 5 > NUL
