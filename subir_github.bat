@echo off
echo ========================================
echo   Subir proyecto a GitHub
echo ========================================
echo.

cd /d "%~dp0"

echo Paso 1: Autenticando con GitHub...
echo Presiona Enter para continuar con HTTPS
C:\Users\HP\Desktop\gh\bin\gh.exe auth login

echo.
echo Paso 2: Creando repositorio...
C:\Users\HP\Desktop\gh\bin\gh.exe repo create inventario-web --public --source=. --push

echo.
echo ========================================
echo ¡Listo! Tu repositorio está en:
echo https://github.com/TU_USUARIO/inventario-web
echo ========================================
pause
