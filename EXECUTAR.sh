#!/bin/bash
# ▶️ MOEDOR AO VIVO - Executar Servidor
# Execute: ./EXECUTAR.sh

echo "🚀 MOEDOR AO VIVO - Iniciando Servidor Completo"
echo "=============================================="

# Verificar se está no diretório correto
if [ ! -f "SERVIDOR-PRINCIPAL.py" ]; then
    echo "❌ Erro: Execute na pasta MOEDOR-AO-VIVO-COMPLETO-ORGANIZADO"
    exit 1
fi

# Verificar ambiente virtual
if [ ! -d "venv" ]; then
    echo "❌ Ambiente virtual não encontrado!"
    echo "🔧 Execute primeiro: ./INSTALAR-MAC.sh"
    exit 1
fi

# Ativar ambiente virtual
echo "🔄 Ativando ambiente virtual..."
source venv/bin/activate

# Verificar dependências
echo "🔍 Verificando dependências..."
python3 -c "import flask, flask_socketio, flask_sqlalchemy" 2>/dev/null
if [ $? -ne 0 ]; then
    echo "❌ Dependências não instaladas!"
    echo "🔧 Execute: ./INSTALAR-MAC.sh"
    exit 1
fi

echo "✅ Tudo pronto!"
echo ""
echo "🌐 Servidor será iniciado em: http://localhost:5000"
echo "🎛️ Painel Admin: http://localhost:5000/admin"
echo "📺 Overlays OBS: http://localhost:5000/overlays/"
echo "🧪 Login de teste: teste@moedor.com"
echo "⏹️ Pressione Ctrl+C para parar"
echo ""

# Executar o servidor
python3 SERVIDOR-PRINCIPAL.py

