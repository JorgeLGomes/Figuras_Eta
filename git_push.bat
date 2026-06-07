@echo off
REM git_push.bat -- Envia commits pendentes para o repositorio remoto
REM Execute este arquivo no Windows para fazer o push do branch main.
REM
REM Alteracoes incluidas neste push:
REM
REM   fix(reader): restaurar linha truncada em list_available_timestamps
REM     - Linha final de list_available_timestamps foi truncada durante edicao
REM     - Restaurado: return [t for t in config.TIMESTAMPS if file_exists(...)]
REM     - Corrige SyntaxError: '[' was never closed ao importar reader.py
REM
REM   fix(reader): VARIABLES e lista de dicts apos refatoracao YAML
REM     - read_all_fields iterava (name, _, _) esperando tupla de 3 elementos
REM     - Apos refatoracao para YAML, config.VARIABLES e lista de dicts
REM     - Corrigido para v["name"] -- elimina "too many values to unpack (expected 3)"
REM
REM   fix(run.sh): reescrever completo -- restaurar secao de execucao truncada
REM     - Arquivo foi truncado por falha no find() com caracteres box-drawing (U+2500)
REM     - src[end:] retornou src[-1:] = ultimo byte do arquivo original
REM     - Toda a secao de log/execucao/exit estava ausente (linha 167: A: command not found)
REM     - Reescrito do zero via heredoc: secao de log, chamada python, tee, EXIT_CODE,
REM       tempo decorrido formatado, todos os if/then/fi ja corrigidos

echo Enviando commits pendentes para origin/main...
git push origin main
if %ERRORLEVEL% neq 0 (
    echo ERRO: git push falhou. Verifique sua conexao e credenciais SSH.
    pause
    exit /b %ERRORLEVEL%
)
echo.
echo OK -- push concluido.
pause
