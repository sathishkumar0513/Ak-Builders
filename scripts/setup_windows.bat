@echo off
REM One-time local setup on Windows. Run from the project root:  scripts\setup_windows.bat
REM Needs: Python 3.11+, Node.js 20+, PostgreSQL 16 (password in backend\.env)

echo === Creating database (if missing) ===
for /f "tokens=1,* delims==" %%a in (backend\.env) do if "%%a"=="DB_PASSWORD" set PGPASSWORD=%%b
psql -U postgres -h localhost -tc "SELECT 1 FROM pg_database WHERE datname='arbuilders'" | find "1" >nul || psql -U postgres -h localhost -c "CREATE DATABASE arbuilders"
set PGPASSWORD=

echo === Backend ===
cd backend
python -m venv venv
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements-dev.txt
python manage.py migrate
python manage.py seed_data
call deactivate
cd ..

echo === Frontend ===
cd frontend
call npm install
cd ..

echo.
echo Setup complete. Start the app with scripts\run_dev.bat
pause
