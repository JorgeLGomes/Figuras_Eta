@echo off
REM git_push.bat -- Envia commits pendentes para o repositorio remoto
REM
REM   feat: parametros COG configuráveis via config.yaml
REM     - config.yaml: nova secao cog: compress/zlevel/predictor/tile_size
REM     - config.py: le cog: e expoe COG_COMPRESS, COG_ZLEVEL, etc.
REM     - export_cog.py: write_cog usa _cog_params() em vez de constantes
REM
REM   perf: ZLEVEL 6->1 + acumulados COG em paralelo (ProcessPoolExecutor)
REM   fix(accumulate/reader): suprimir overflow/invalid em numpy

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
