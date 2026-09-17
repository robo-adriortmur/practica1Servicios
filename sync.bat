@echo off
echo Guardando y subiendo cambios a GitHub...

git add .
git commit -m "Auto-guardado: %date% %time%"
git push origin main

echo.
echo Sincronizacion completada.
pause