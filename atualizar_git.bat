@echo off
chcp 65001 >nul
cd /d "%APPDATA%\pyRevit\Extensions\ELE-Tools.extension"

echo === Status Atual do Git ===
git status

echo.
echo === Adicionando alteracoes ao Git ===
git add -A

echo.
echo === Criando Commit ===
git commit -m "Renomear ferramentas para PumpSpec, ConduitLocator e WireMaster"

echo.
echo === Enviando para o repositorio remoto (Push) ===
git push origin main

echo.
echo === Concluido! ===
pause
