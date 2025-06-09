@echo off
REM 🪟 MOEDOR AO VIVO - Instalação Automática para Windows
REM Execute: INSTALAR-WINDOWS.bat

echo 🪟 MOEDOR AO VIVO - Instalação Completa para Windows
echo ===================================================

REM Verificar Python
echo 🔍 Verificando Python...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ Python não encontrado!
    echo 📦 Por favor, instale Python 3.8+ de https://python.org
    echo ✅ Marque a opção "Add Python to PATH" durante a instalação
    pause
    exit /b 1
) else (
    for /f "tokens=*" %%i in ('python --version') do echo ✅ %%i encontrado
)

REM Verificar pip
echo 🔍 Verificando pip...
pip --version >nul 2>&1
if %errorlevel% neq 0 (
    echo ❌ pip não encontrado!
    echo 📦 Reinstale Python com pip incluído
    pause
    exit /b 1
) else (
    echo ✅ pip encontrado
)

REM Limpar instalação anterior
echo 🧹 Limpando instalação anterior...
if exist venv rmdir /s /q venv

REM Criar ambiente virtual
echo 🐍 Criando ambiente virtual...
python -m venv venv

REM Ativar ambiente virtual
echo 🔄 Ativando ambiente virtual...
call venv\Scripts\activate.bat

REM Atualizar pip
echo 📦 Atualizando pip...
python -m pip install --upgrade pip

REM Instalar dependências
echo 📦 Instalando dependências...
pip install -r requirements.txt

REM Configurar arquivo .env
echo ⚙️ Configurando variáveis de ambiente...
if not exist .env (
    copy .env.exemplo .env
    echo ✅ Arquivo .env criado a partir do exemplo
    echo 📝 IMPORTANTE: Edite o arquivo .env com suas chaves de API
) else (
    echo ✅ Arquivo .env já existe
)

REM Inicializar banco de dados
echo 🗄️ Inicializando banco de dados...
python CRIAR-BANCO.py

echo.
echo 🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!
echo ===================================
echo.
echo 📋 PRÓXIMOS PASSOS:
echo 1. Edite o arquivo .env com suas chaves de API
echo 2. Execute: EXECUTAR.bat
echo 3. Acesse: http://localhost:5000
echo.
echo 🧪 TESTE RÁPIDO (sem APIs):
echo - Login: teste@moedor.com
echo - Todas as funcionalidades básicas funcionam
echo.
echo 📞 Suporte: Consulte MANUAL-COMPLETO.md
echo.
echo ⚠️ NOTA: Para Whisper funcionar, instale FFmpeg:
echo https://ffmpeg.org/download.html#build-windows
echo.
pause

