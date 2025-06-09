@echo off
REM ▶️ MOEDOR AO VIVO - Executar Servidor
REM Execute: EXECUTAR.bat

echo 🚀 MOEDOR AO VIVO - Iniciando Servidor Completo
echo ==============================================

REM Verificar se está no diretório correto
if not exist SERVIDOR-PRINCIPAL.py (
    echo ❌ Erro: Execute na pasta MOEDOR-AO-VIVO-COMPLETO-ORGANIZADO
    pause
    exit /b 1
)

REM Verificar ambiente virtual
if not exist venv (
    echo ❌ Ambiente virtual não encontrado!
    echo 🔧 Execute primeiro: INSTALAR-WINDOWS.bat
    pause
    exit /b 1
)

REM Ativar ambiente virtual
echo 🔄 Ativando ambiente virtual...
call venv\Scripts\activate.bat

REM Verificar dependências
echo 🔍 Verificando dependências...
python -c "import flask, flask_socketio, flask_sqlalchemy" >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Dependências não instaladas!
    echo 🔧 Execute: INSTALAR-WINDOWS.bat
    pause
    exit /b 1
)

echo ✅ Tudo pronto!
echo.
echo 🌐 Servidor será iniciado em: http://localhost:5000
echo 🎛️ Painel Admin: http://localhost:5000/admin
echo 📺 Overlays OBS: http://localhost:5000/overlays/
echo 🧪 Login de teste: teste@moedor.com
echo ⏹️ Pressione Ctrl+C para parar
echo.

REM Executar o servidor
python SERVIDOR-PRINCIPAL.py

