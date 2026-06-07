@echo off
REM git_push.bat -- Envia commits pendentes para o repositorio remoto
REM
REM   perf: reducao de tempo de geracao dos COGs
REM     - export_cog.py: ZLEVEL 6->1 (~3-5x mais rapido por write, lossless)
REM     - accumulate.py: acumulados COG agora paralelos (ProcessPoolExecutor)
REM       novo parametro workers= repassado de args.workers
REM
REM   fix(accumulate): suprimir overflow em acc + field (errstate over+invalid)
REM   fix(reader): restaurar lista_available_timestamps + VARIABLES dict fix
REM   fix(run.sh): reescrever completo (line 167: A: command not found)

echo Enviando commits para origin/main...
git push origin main
if %ERRORLEVEL% neq 0 (
    echo ERRO: git push falhou.
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo OK -- push concluido.
pause
