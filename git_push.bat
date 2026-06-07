@echo off
REM git_push.bat -- Envia commits pendentes para o repositorio remoto
REM
REM   fix(accumulate): suprimir overflow em acc + field
REM     - np.errstate(over='ignore') na soma acumulada
REM
REM   fix: suprimir RuntimeWarning NaN/overflow em numpy
REM     - reader.py: errstate em read_all_fields
REM     - export_cog.py: errstate na conversao m->mm
REM
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
