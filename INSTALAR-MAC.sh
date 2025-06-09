#!/bin/bash
# 🍎 MOEDOR AO VIVO - Instalação Automática para macOS
# Execute: chmod +x INSTALAR-MAC.sh && ./INSTALAR-MAC.sh

echo "🍎 MOEDOR AO VIVO - Instalação Completa para Mac"
echo "=============================================="

# Verificar se está no diretório correto
if [ ! -f "requirements.txt" ]; then
    echo "❌ Erro: Execute este script na pasta MOEDOR-AO-VIVO-COMPLETO-ORGANIZADO"
    exit 1
fi

# Verificar Python3
echo "🔍 Verificando Python3..."
if command -v python3 &> /dev/null; then
    PYTHON_VERSION=$(python3 --version)
    echo "✅ $PYTHON_VERSION encontrado"
else
    echo "❌ Python3 não encontrado!"
    echo "📦 Instalando Python via Homebrew..."
    if ! command -v brew &> /dev/null; then
        echo "Instalando Homebrew..."
        /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    fi
    brew install python
fi

# Verificar FFmpeg (necessário para Whisper)
echo "🔍 Verificando FFmpeg..."
if command -v ffmpeg &> /dev/null; then
    echo "✅ FFmpeg encontrado"
else
    echo "📦 Instalando FFmpeg..."
    if command -v brew &> /dev/null; then
        brew install ffmpeg
    else
        echo "⚠️ Instale FFmpeg manualmente para usar Whisper"
    fi
fi

# Limpar instalação anterior
echo "🧹 Limpando instalação anterior..."
rm -rf venv

# Criar ambiente virtual
echo "🐍 Criando ambiente virtual..."
python3 -m venv venv

# Ativar ambiente virtual
echo "🔄 Ativando ambiente virtual..."
source venv/bin/activate

# Atualizar pip
echo "📦 Atualizando pip..."
pip install --upgrade pip

# Instalar dependências
echo "📦 Instalando dependências..."
pip install -r requirements.txt

# Configurar arquivo .env
echo "⚙️ Configurando variáveis de ambiente..."
if [ ! -f .env ]; then
    cp .env.exemplo .env
    echo "✅ Arquivo .env criado a partir do exemplo"
    echo "📝 IMPORTANTE: Edite o arquivo .env com suas chaves de API"
else
    echo "✅ Arquivo .env já existe"
fi

# Inicializar banco de dados
echo "🗄️ Inicializando banco de dados..."
python CRIAR-BANCO.py

echo ""
echo "🎉 INSTALAÇÃO CONCLUÍDA COM SUCESSO!"
echo "=================================="
echo ""
echo "📋 PRÓXIMOS PASSOS:"
echo "1. Edite o arquivo .env com suas chaves de API"
echo "2. Execute: ./EXECUTAR.sh"
echo "3. Acesse: http://localhost:5000"
echo ""
echo "🧪 TESTE RÁPIDO (sem APIs):"
echo "- Login: teste@moedor.com"
echo "- Todas as funcionalidades básicas funcionam"
echo ""
echo "📞 Suporte: Consulte MANUAL-COMPLETO.md"

