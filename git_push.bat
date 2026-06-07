@echo off
REM git_push.bat -- Envia commits pendentes para o repositorio remoto
REM Execute este arquivo no Windows para fazer o push do branch main.
REM
REM Alteracoes incluidas neste push:
REM
REM   fix: suprimir RuntimeWarning de NaN/overflow em numpy
REM     - reader.py: np.errstate(invalid='ignore') em read_all_fields
REM     - export_cog.py: np.errstate(over='ignore') na conversao m->mm
REM
REM   fix(reader): restaurar linha truncada em list_available_timestamps
REM     - Corrige SyntaxError '[' was never closed ao importar reader.py
REM
REM   fix(reader): VARIABLES e lista de dicts apos refatoracao YAML
REM     - Corrige "too many values to unpack (expected 3)"
REM
REM   fix(run.sh): reescrever completo -- restaurar secao de execucao truncada
REM     - Corrige "line 167: A: command not found"

echo Enviando commits pendentes para origin/main...
git push origin main
if %ERRORLEVEL% neq 0 (
    echo ERRO: git push falhou.
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo OK -- push concluido.
pause
