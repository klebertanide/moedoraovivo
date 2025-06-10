#!/usr/bin/env python3
"""
MOEDOR AO VIVO - Sistema com OAuth Hotmart (Versão Debug)
Autenticação automática de compradores via API da Hotmart
"""

from flask import Flask, render_template_string, send_from_directory, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
import os
import json
import hashlib
import hmac
import requests
import base64
from datetime import datetime, timedelta
from functools import wraps
from urllib.parse import urlencode

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'moedor-ao-vivo-2024-secure')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Configurações da Hotmart (via variáveis de ambiente)
HOTMART_CLIENT_ID = os.environ.get('HOTMART_CLIENT_ID', '')
HOTMART_CLIENT_SECRET = os.environ.get('HOTMART_CLIENT_SECRET', '')
HOTMART_BASIC_TOKEN = os.environ.get('HOTMART_BASIC_TOKEN', '')
HOTMART_PRODUCT_ID = os.environ.get('HOTMART_PRODUCT_ID', '')

# URLs da API Hotmart
HOTMART_AUTH_URL = "https://api-sec-vlc.hotmart.com/security/oauth/token"
HOTMART_SUBSCRIPTIONS_URL = "https://developers.hotmart.com/payments/api/v1/subscriptions"
HOTMART_SALES_URL = "https://developers.hotmart.com/payments/api/v1/sales"

# Cache de tokens e compradores
hotmart_access_token = None
token_expires_at = None
verified_buyers = set()
cache_expires_at = None

# Lista local para testes (enquanto API não funciona)
local_authorized_buyers = {
    'admin@moedor.com',
    'teste@moedor.com'
}

# Dados em memória
users_online = 0
messages = []
authenticated_users = {}

def login_required(f):
    """Decorator para proteger rotas que precisam de autenticação"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_email' not in session or not session.get('authenticated'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def create_basic_auth_token(client_id, client_secret):
    """Cria token Basic Auth a partir do client_id e client_secret"""
    credentials = f"{client_id}:{client_secret}"
    encoded_credentials = base64.b64encode(credentials.encode('utf-8')).decode('utf-8')
    return encoded_credentials

def get_hotmart_access_token():
    """Obtém access token da Hotmart com múltiplos métodos"""
    global hotmart_access_token, token_expires_at
    
    # Verificar se token ainda é válido
    if hotmart_access_token and token_expires_at and datetime.now() < token_expires_at:
        return hotmart_access_token
    
    if not HOTMART_CLIENT_ID or not HOTMART_CLIENT_SECRET:
        print("❌ Client ID ou Client Secret não configurados")
        return None
    
    try:
        print("🔑 Obtendo access token da Hotmart...")
        print(f"🔧 Client ID: {HOTMART_CLIENT_ID[:10]}...")
        print(f"🔧 Client Secret: {HOTMART_CLIENT_SECRET[:10]}...")
        
        # Método 1: Usar Basic Token fornecido
        if HOTMART_BASIC_TOKEN:
            print("📡 Tentativa 1: Usando Basic Token fornecido")
            
            data = {
                'grant_type': 'client_credentials',
                'client_id': HOTMART_CLIENT_ID,
                'client_secret': HOTMART_CLIENT_SECRET
            }
            
            headers = {
                'Content-Type': 'application/x-www-form-urlencoded',
                'Authorization': f'Basic {HOTMART_BASIC_TOKEN}'
            }
            
            print(f"🔧 Headers: {headers}")
            print(f"🔧 Data: {data}")
            
            response = requests.post(HOTMART_AUTH_URL, data=data, headers=headers, timeout=30)
            
            print(f"📡 Status: {response.status_code}")
            print(f"📡 Response: {response.text}")
            
            if response.status_code == 200:
                token_data = response.json()
                hotmart_access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)
                token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
                print(f"✅ Token obtido com método 1!")
                return hotmart_access_token
        
        # Método 2: Criar Basic Token automaticamente
        print("📡 Tentativa 2: Criando Basic Token automaticamente")
        
        auto_basic_token = create_basic_auth_token(HOTMART_CLIENT_ID, HOTMART_CLIENT_SECRET)
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': HOTMART_CLIENT_ID,
            'client_secret': HOTMART_CLIENT_SECRET
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded',
            'Authorization': f'Basic {auto_basic_token}'
        }
        
        print(f"🔧 Auto Basic Token: {auto_basic_token[:20]}...")
        print(f"🔧 Headers: {headers}")
        
        response = requests.post(HOTMART_AUTH_URL, data=data, headers=headers, timeout=30)
        
        print(f"📡 Status: {response.status_code}")
        print(f"📡 Response: {response.text}")
        
        if response.status_code == 200:
            token_data = response.json()
            hotmart_access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
            print(f"✅ Token obtido com método 2!")
            return hotmart_access_token
        
        # Método 3: Sem Basic Auth, apenas form data
        print("📡 Tentativa 3: Apenas form data")
        
        data = {
            'grant_type': 'client_credentials',
            'client_id': HOTMART_CLIENT_ID,
            'client_secret': HOTMART_CLIENT_SECRET
        }
        
        headers = {
            'Content-Type': 'application/x-www-form-urlencoded'
        }
        
        response = requests.post(HOTMART_AUTH_URL, data=data, headers=headers, timeout=30)
        
        print(f"📡 Status: {response.status_code}")
        print(f"📡 Response: {response.text}")
        
        if response.status_code == 200:
            token_data = response.json()
            hotmart_access_token = token_data.get('access_token')
            expires_in = token_data.get('expires_in', 3600)
            token_expires_at = datetime.now() + timedelta(seconds=expires_in - 300)
            print(f"✅ Token obtido com método 3!")
            return hotmart_access_token
        
        print(f"❌ Todos os métodos falharam")
        return None
            
    except Exception as e:
        print(f"❌ Erro na requisição do token: {str(e)}")
        return None

def verify_buyer_in_hotmart(email):
    """Verifica se o email é um comprador válido na Hotmart"""
    global verified_buyers, cache_expires_at
    
    # Verificar cache (válido por 10 minutos)
    if cache_expires_at and datetime.now() < cache_expires_at:
        return email.lower() in verified_buyers
    
    # Obter token de acesso
    access_token = get_hotmart_access_token()
    if not access_token:
        print("❌ Não foi possível obter token da Hotmart")
        return False
    
    try:
        print(f"🔍 Verificando comprador na Hotmart: {email}")
        
        headers = {
            'Authorization': f'Bearer {access_token}',
            'Content-Type': 'application/json'
        }
        
        # Buscar nas assinaturas ativas
        subscription_params = {
            'subscriber_email': email,
            'status': 'ACTIVE',
            'max_results': 50
        }
        
        if HOTMART_PRODUCT_ID:
            subscription_params['product_id'] = HOTMART_PRODUCT_ID
        
        print(f"📡 Buscando assinaturas para: {email}")
        subscription_response = requests.get(
            HOTMART_SUBSCRIPTIONS_URL, 
            headers=headers, 
            params=subscription_params,
            timeout=30
        )
        
        print(f"📊 Status assinaturas: {subscription_response.status_code}")
        print(f"📊 Response assinaturas: {subscription_response.text[:200]}...")
        
        if subscription_response.status_code == 200:
            subscription_data = subscription_response.json()
            items = subscription_data.get('items', [])
            
            if items:
                print(f"✅ Encontradas {len(items)} assinaturas ativas para {email}")
                verified_buyers.add(email.lower())
                cache_expires_at = datetime.now() + timedelta(minutes=10)
                return True
        
        # Se não encontrou assinaturas, buscar nas vendas
        print(f"📡 Buscando vendas para: {email}")
        
        # Buscar vendas dos últimos 365 dias
        end_date = datetime.now()
        start_date = end_date - timedelta(days=365)
        
        sales_params = {
            'buyer_email': email,
            'start_date': int(start_date.timestamp() * 1000),
            'end_date': int(end_date.timestamp() * 1000),
            'max_results': 50
        }
        
        if HOTMART_PRODUCT_ID:
            sales_params['product_id'] = HOTMART_PRODUCT_ID
        
        sales_response = requests.get(
            HOTMART_SALES_URL,
            headers=headers,
            params=sales_params,
            timeout=30
        )
        
        print(f"📊 Status vendas: {sales_response.status_code}")
        print(f"📊 Response vendas: {sales_response.text[:200]}...")
        
        if sales_response.status_code == 200:
            sales_data = sales_response.json()
            items = sales_data.get('items', [])
            
            # Verificar se há vendas aprovadas
            approved_sales = [
                item for item in items 
                if item.get('purchase', {}).get('status') in ['APPROVED', 'COMPLETE']
            ]
            
            if approved_sales:
                print(f"✅ Encontradas {len(approved_sales)} vendas aprovadas para {email}")
                verified_buyers.add(email.lower())
                cache_expires_at = datetime.now() + timedelta(minutes=10)
                return True
        
        print(f"❌ Nenhuma compra encontrada na Hotmart para {email}")
        return False
        
    except Exception as e:
        print(f"❌ Erro ao verificar comprador na Hotmart: {str(e)}")
        return False

def is_authorized_buyer(email):
    """Verifica se o email está autorizado (lista local + Hotmart)"""
    email = email.lower().strip()
    
    print(f"\n🔍 === VERIFICAÇÃO DE COMPRADOR ===")
    print(f"📧 Email: '{email}'")
    
    # Verificar lista local primeiro (para garantir que funciona)
    if email in local_authorized_buyers:
        print(f"✅ Autorizado pela lista local")
        print(f"================================\n")
        return True
    
    # Verificar na Hotmart (se configurado)
    if HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET:
        print(f"🔍 Verificando na Hotmart...")
        if verify_buyer_in_hotmart(email):
            print(f"✅ Autorizado pela Hotmart")
            print(f"================================\n")
            return True
    else:
        print(f"⚠️ Hotmart não configurado, usando apenas lista local")
    
    print(f"❌ Não autorizado")
    print(f"================================\n")
    return False

# Servir arquivos estáticos
@app.route('/<path:filename>')
def serve_files(filename):
    if filename in ['logo.png', 'ZURITA.otf']:
        return send_from_directory('.', filename)
    return "File not found", 404

# PÁGINA INICIAL - REDIRECIONA PARA LOGIN
@app.route('/')
def index():
    if 'user_email' in session and session.get('authenticated'):
        return render_template_string(main_template)
    return redirect(url_for('login'))

# ENDPOINTS DE TESTE E DEBUG
@app.route('/debug')
def debug():
    """Página de debug com informações do sistema"""
    return render_template_string(debug_template, 
                                hotmart_configured=bool(HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET),
                                verified_buyers=len(verified_buyers),
                                local_buyers=len(local_authorized_buyers),
                                cache_expires=cache_expires_at.isoformat() if cache_expires_at else None,
                                token_expires=token_expires_at.isoformat() if token_expires_at else None)

@app.route('/test-hotmart')
def test_hotmart():
    """Testa conexão com a API da Hotmart"""
    token = get_hotmart_access_token()
    
    if not token:
        return jsonify({
            'status': 'error',
            'message': 'Não foi possível obter token da Hotmart',
            'configured': bool(HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET),
            'client_id_present': bool(HOTMART_CLIENT_ID),
            'client_secret_present': bool(HOTMART_CLIENT_SECRET),
            'basic_token_present': bool(HOTMART_BASIC_TOKEN)
        })
    
    return jsonify({
        'status': 'success',
        'message': 'Conexão com Hotmart funcionando',
        'token_expires': token_expires_at.isoformat() if token_expires_at else None,
        'verified_buyers': len(verified_buyers)
    })

@app.route('/api/status')
def api_status():
    """Status do sistema em JSON"""
    return jsonify({
        'hotmart_configured': bool(HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET),
        'verified_buyers': len(verified_buyers),
        'local_buyers': len(local_authorized_buyers),
        'users_online': len(authenticated_users),
        'cache_expires': cache_expires_at.isoformat() if cache_expires_at else None,
        'token_expires': token_expires_at.isoformat() if token_expires_at else None
    })

# TESTE DE CONECTIVIDADE
@app.route('/ping')
def ping():
    """Endpoint simples para testar conectividade"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'message': 'MOEDOR AO VIVO com OAuth Hotmart está funcionando!',
        'hotmart_configured': bool(HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET),
        'environment': 'render' if os.environ.get('RENDER') else 'local'
    })

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        print(f"\n🔐 === TENTATIVA DE LOGIN ===")
        print(f"📧 Email: '{email}'")
        
        if not email:
            return render_template_string(login_template, error="Digite seu email de compra")
        
        if '@' not in email or '.' not in email:
            return render_template_string(login_template, error="Digite um email válido")
        
        # Verificar se é comprador autorizado
        if is_authorized_buyer(email):
            session['user_email'] = email
            session['authenticated'] = True
            session['login_time'] = datetime.now().isoformat()
            session.permanent = True
            
            authenticated_users[email] = {
                'email': email,
                'login_time': datetime.now(),
                'last_activity': datetime.now()
            }
            
            print(f"✅ LOGIN AUTORIZADO: {email}")
            print(f"==============================\n")
            return redirect(url_for('index'))
        else:
            print(f"❌ LOGIN NEGADO: {email}")
            print(f"==============================\n")
            return render_template_string(login_template, 
                error="Email não encontrado na lista de compradores. Verifique se você possui uma assinatura ativa do MOEDOR ou entre em contato com o suporte.")
    
    return render_template_string(login_template)

@app.route('/logout')
def logout():
    email = session.get('user_email')
    if email and email in authenticated_users:
        del authenticated_users[email]
    
    session.clear()
    return redirect(url_for('login'))

@app.route('/admin')
@login_required
def admin():
    return render_template_string(admin_template, 
                                verified_buyers=len(verified_buyers),
                                local_buyers=len(local_authorized_buyers),
                                authenticated_users=authenticated_users,
                                messages=messages,
                                hotmart_configured=bool(HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET))

# Templates (mantendo os mesmos do arquivo anterior)
login_template = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MOEDOR AO VIVO - Login</title>
    <style>
        @font-face {
            font-family: 'ZURITA';
            src: url('/ZURITA.otf') format('opentype');
            font-weight: normal;
            font-style: normal;
            font-display: swap;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Helvetica Neue', 'Helvetica', Arial, sans-serif;
            background: linear-gradient(135deg, #000, #1a0000, #000);
            background-size: 400% 400%;
            animation: gradientShift 8s ease infinite;
            color: #fff;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        @keyframes gradientShift {
            0%, 100% { background-position: 0% 50%; }
            50% { background-position: 100% 50%; }
        }
        
        .login-container {
            background: rgba(17, 17, 17, 0.95);
            border-radius: 15px;
            padding: 40px;
            border: 2px solid #ff4444;
            box-shadow: 0 0 30px rgba(255, 68, 68, 0.3);
            max-width: 450px;
            width: 90%;
            text-align: center;
            backdrop-filter: blur(10px);
        }
        
        .logo-container {
            margin-bottom: 30px;
        }
        
        .logo-image {
            width: 150px;
            height: 150px;
            object-fit: contain;
            border-radius: 15px;
            margin-bottom: 20px;
            border: 3px solid #ff4444;
            background: rgba(255, 255, 255, 0.1);
            padding: 10px;
        }
        
        .logo-text {
            font-family: 'ZURITA', 'Impact', monospace;
            font-size: 2.5rem;
            font-weight: 900;
            color: #fff;
            letter-spacing: 2px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
            margin-bottom: 10px;
        }
        
        .subtitle {
            color: #999;
            font-size: 1.1rem;
            margin-bottom: 30px;
            font-weight: 300;
        }
        
        .login-form {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .form-group {
            text-align: left;
        }
        
        .form-label {
            display: block;
            color: #fff;
            font-weight: 600;
            margin-bottom: 8px;
            font-size: 0.9rem;
        }
        
        .form-input {
            width: 100%;
            padding: 15px;
            background: #1a1a1a;
            border: 2px solid #333;
            border-radius: 8px;
            color: #fff;
            font-size: 1rem;
            transition: all 0.3s ease;
        }
        
        .form-input:focus {
            outline: none;
            border-color: #ff4444;
            box-shadow: 0 0 10px rgba(255, 68, 68, 0.3);
        }
        
        .form-input::placeholder {
            color: #666;
        }
        
        .login-btn {
            background: linear-gradient(135deg, #ff4444, #cc0000);
            border: none;
            color: white;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .login-btn:hover {
            background: linear-gradient(135deg, #cc0000, #990000);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 68, 68, 0.4);
        }
        
        .error-message {
            background: rgba(255, 68, 68, 0.1);
            border: 1px solid #ff4444;
            color: #ff6666;
            padding: 12px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 0.9rem;
        }
        
        .subscribe-btn {
            background: linear-gradient(135deg, #00aa00, #008800);
            border: none;
            color: white;
            padding: 12px 25px;
            border-radius: 8px;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            margin-top: 15px;
        }
        
        .subscribe-btn:hover {
            background: linear-gradient(135deg, #008800, #006600);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(0, 170, 0, 0.4);
        }
        
        .footer-text {
            color: #666;
            font-size: 0.8rem;
            margin-top: 20px;
        }
        
        .debug-btn {
            background: #333;
            color: #ccc;
            border: 1px solid #555;
            padding: 8px 15px;
            border-radius: 5px;
            font-size: 0.8rem;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            margin-top: 10px;
        }
        
        .debug-btn:hover {
            background: #444;
            color: #fff;
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo-container">
            <img src="/logo.png" alt="MOEDOR AO VIVO" class="logo-image" onerror="this.style.display='none'; document.querySelector('.logo-text').style.display='block';">
            <div class="logo-text" style="display: none;">MOEDOR AO VIVO</div>
        </div>
        
        <h2 class="subtitle">Acesso Exclusivo para Assinantes</h2>
        
        {% if error %}
        <div class="error-message">{{ error }}</div>
        {% endif %}
        
        <form method="POST" class="login-form">
            <div class="form-group">
                <label for="email" class="form-label">Email de Compra:</label>
                <input type="email" id="email" name="email" class="form-input" 
                       placeholder="Digite o email usado na compra" required>
            </div>
            
            <button type="submit" class="login-btn">Entrar no Sistema</button>
        </form>
        
        <a href="https://moedor.com" class="subscribe-btn">
            🚀 Assinar o MOEDOR Agora
        </a>
        
        <div class="footer-text">
            Sistema com verificação automática via Hotmart<br>
            Apenas assinantes ativos podem acessar
        </div>
        
        <a href="/debug" class="debug-btn">Debug do Sistema</a>
    </div>
    
    <script>
        // Verificar se logo carregou
        document.querySelector('.logo-image').onload = function() {
            console.log('✅ Logo carregado!');
            this.style.display = 'block';
            document.querySelector('.logo-text').style.display = 'none';
        };
        
        // Verificar se fonte carregou
        document.fonts.ready.then(function() {
            console.log('✅ Fontes carregadas!');
        });
    </script>
</body>
</html>
'''

debug_template = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Debug - MOEDOR AO VIVO</title>
    <style>
        body { font-family: Arial; background: #000; color: #fff; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .status-box { background: #111; padding: 15px; margin: 10px 0; border-radius: 8px; border-left: 4px solid #00aa00; }
        .error-box { border-left-color: #ff4444; }
        .warning-box { border-left-color: #ffaa00; }
        .header { text-align: center; margin-bottom: 30px; }
        .back-btn { background: #666; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; }
        pre { background: #222; padding: 10px; border-radius: 4px; overflow-x: auto; }
        .test-btn { background: #00aa00; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; margin: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🔍 Debug - MOEDOR AO VIVO com OAuth Hotmart</h1>
            <a href="/" class="back-btn">← Voltar ao Sistema</a>
        </div>
        
        <div class="status-box {% if not hotmart_configured %}warning-box{% endif %}">
            <h3>🔑 Configuração Hotmart</h3>
            <p><strong>Status:</strong> {% if hotmart_configured %}✅ Configurado{% else %}⚠️ Não configurado{% endif %}</p>
            <p><strong>Client ID:</strong> {% if hotmart_configured %}✅ Presente{% else %}❌ Ausente{% endif %}</p>
            <p><strong>Client Secret:</strong> {% if hotmart_configured %}✅ Presente{% else %}❌ Ausente{% endif %}</p>
        </div>
        
        <div class="status-box">
            <h3>👥 Compradores Autorizados</h3>
            <p><strong>Lista Local:</strong> {{ local_buyers }}</p>
            <p><strong>Verificados Hotmart:</strong> {{ verified_buyers }}</p>
            <p><strong>Cache expira:</strong> {{ cache_expires or 'Não definido' }}</p>
        </div>
        
        <div class="status-box">
            <h3>🔐 Token de Acesso</h3>
            <p><strong>Token expira:</strong> {{ token_expires or 'Não obtido' }}</p>
        </div>
        
        <div class="status-box">
            <h3>🧪 Testes</h3>
            <button class="test-btn" onclick="testHotmart()">Testar Conexão Hotmart</button>
            <button class="test-btn" onclick="testBuyer()">Testar Verificação de Comprador</button>
            <div id="test-results"></div>
        </div>
        
        <div class="status-box">
            <h3>📋 Variáveis de Ambiente Necessárias</h3>
            <pre>
HOTMART_CLIENT_ID=seu_client_id_aqui
HOTMART_CLIENT_SECRET=seu_client_secret_aqui  
HOTMART_BASIC_TOKEN=seu_basic_token_aqui
HOTMART_PRODUCT_ID=seu_product_id_aqui (opcional)
            </pre>
        </div>
        
        <div class="status-box">
            <h3>ℹ️ Informações Importantes</h3>
            <p>• O sistema usa uma lista local para garantir acesso mesmo se a API da Hotmart falhar</p>
            <p>• Email <strong>leo-brde@hotmail.com</strong> foi adicionado à lista local para teste</p>
            <p>• Verifique os logs do servidor para detalhes sobre tentativas de autenticação</p>
        </div>
    </div>
    
    <script>
        function testHotmart() {
            fetch('/test-hotmart')
            .then(response => response.json())
            .then(data => {
                document.getElementById('test-results').innerHTML = `
                    <div style="background: ${data.status === 'success' ? '#004400' : '#440000'}; padding: 10px; margin: 10px 0; border-radius: 4px;">
                        <strong>Teste Hotmart:</strong> ${data.message}<br>
                        <strong>Status:</strong> ${data.status}<br>
                        ${data.client_id_present !== undefined ? '<strong>Client ID:</strong> ' + (data.client_id_present ? 'Presente' : 'Ausente') + '<br>' : ''}
                        ${data.client_secret_present !== undefined ? '<strong>Client Secret:</strong> ' + (data.client_secret_present ? 'Presente' : 'Ausente') + '<br>' : ''}
                        ${data.basic_token_present !== undefined ? '<strong>Basic Token:</strong> ' + (data.basic_token_present ? 'Presente' : 'Ausente') + '<br>' : ''}
                    </div>
                `;
            });
        }
        
        function testBuyer() {
            const email = prompt('Digite um email para testar:', 'leo-brde@hotmail.com');
            if (email) {
                fetch('/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/x-www-form-urlencoded'},
                    body: `email=${encodeURIComponent(email)}`
                })
                .then(response => {
                    if (response.redirected) {
                        document.getElementById('test-results').innerHTML = `
                            <div style="background: #004400; padding: 10px; margin: 10px 0; border-radius: 4px;">
                                <strong>Teste Comprador:</strong> ✅ Email ${email} é um comprador válido!
                            </div>
                        `;
                    } else {
                        document.getElementById('test-results').innerHTML = `
                            <div style="background: #440000; padding: 10px; margin: 10px 0; border-radius: 4px;">
                                <strong>Teste Comprador:</strong> ❌ Email ${email} não é um comprador válido
                            </div>
                        `;
                    }
                });
            }
        }
    </script>
</body>
</html>
'''

main_template = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MOEDOR AO VIVO</title>
    <style>
        @font-face {
            font-family: 'ZURITA';
            src: url('/ZURITA.otf') format('opentype');
            font-weight: normal;
            font-style: normal;
            font-display: swap;
        }
        
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            background: #000;
            color: #fff;
            overflow-x: hidden;
        }
        
        .header {
            background: linear-gradient(135deg, #ff4444, #cc0000);
            padding: 20px;
            text-align: center;
            box-shadow: 0 2px 10px rgba(255, 68, 68, 0.3);
        }
        
        .logo {
            font-family: 'ZURITA', 'Impact', monospace;
            font-size: 3rem;
            font-weight: 900;
            color: #fff;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
            margin-bottom: 10px;
        }
        
        .subtitle {
            font-size: 1.2rem;
            color: #ffcccc;
            font-weight: 300;
        }
        
        .main-content {
            display: grid;
            grid-template-columns: 2fr 1fr;
            gap: 20px;
            padding: 20px;
            min-height: calc(100vh - 120px);
        }
        
        .video-section {
            background: #111;
            border-radius: 15px;
            padding: 20px;
            border: 2px solid #333;
        }
        
        .cameras-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-bottom: 20px;
        }
        
        .camera-feed {
            background: #000;
            border: 2px solid #ff4444;
            border-radius: 10px;
            aspect-ratio: 16/9;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            font-size: 1.1rem;
            position: relative;
            overflow: hidden;
        }
        
        .camera-label {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(255, 68, 68, 0.8);
            color: #fff;
            padding: 5px 10px;
            border-radius: 5px;
            font-size: 0.8rem;
            font-weight: 600;
        }
        
        .action-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 15px;
            margin-top: 20px;
        }
        
        .action-btn {
            background: linear-gradient(135deg, #ff4444, #cc0000);
            border: none;
            color: white;
            padding: 15px 20px;
            border-radius: 10px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .action-btn:hover {
            background: linear-gradient(135deg, #cc0000, #990000);
            transform: translateY(-2px);
            box-shadow: 0 5px 15px rgba(255, 68, 68, 0.4);
        }
        
        .action-btn.expensive {
            background: linear-gradient(135deg, #ffaa00, #ff8800);
        }
        
        .action-btn.expensive:hover {
            background: linear-gradient(135deg, #ff8800, #ff6600);
            box-shadow: 0 5px 15px rgba(255, 170, 0, 0.4);
        }
        
        .tooltip {
            position: absolute;
            bottom: 120%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.9);
            color: #fff;
            padding: 10px 15px;
            border-radius: 8px;
            font-size: 0.9rem;
            white-space: nowrap;
            opacity: 0;
            visibility: hidden;
            transition: all 0.3s ease;
            z-index: 1000;
            max-width: 300px;
            white-space: normal;
            text-align: center;
        }
        
        .action-btn:hover .tooltip {
            opacity: 1;
            visibility: visible;
        }
        
        .sidebar {
            display: flex;
            flex-direction: column;
            gap: 20px;
        }
        
        .chat-section, .mural-section {
            background: #111;
            border-radius: 15px;
            padding: 20px;
            border: 2px solid #333;
            flex: 1;
        }
        
        .section-title {
            font-family: 'ZURITA', 'Impact', monospace;
            font-size: 1.5rem;
            color: #ff4444;
            margin-bottom: 15px;
            text-align: center;
        }
        
        .chat-description {
            background: rgba(0, 170, 0, 0.1);
            border: 1px solid #00aa00;
            color: #00ff00;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 0.9rem;
            text-align: center;
        }
        
        .mural-description {
            background: rgba(255, 170, 0, 0.1);
            border: 1px solid #ffaa00;
            color: #ffaa00;
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 15px;
            font-size: 0.9rem;
            text-align: center;
        }
        
        .chat-input {
            width: 100%;
            padding: 12px;
            background: #222;
            border: 2px solid #444;
            border-radius: 8px;
            color: #fff;
            font-size: 1rem;
            margin-bottom: 10px;
        }
        
        .chat-input:focus {
            outline: none;
            border-color: #00aa00;
        }
        
        .send-btn {
            width: 100%;
            background: linear-gradient(135deg, #00aa00, #008800);
            border: none;
            color: white;
            padding: 12px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .send-btn:hover {
            background: linear-gradient(135deg, #008800, #006600);
            transform: translateY(-1px);
        }
        
        .messages {
            max-height: 200px;
            overflow-y: auto;
            margin-bottom: 15px;
            padding: 10px;
            background: #0a0a0a;
            border-radius: 8px;
        }
        
        .message {
            margin-bottom: 10px;
            padding: 8px;
            background: #1a1a1a;
            border-radius: 5px;
            border-left: 3px solid #00aa00;
        }
        
        .mural-grid {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .mural-item {
            background: #222;
            border: 2px solid #ffaa00;
            border-radius: 8px;
            aspect-ratio: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            font-size: 0.8rem;
            text-align: center;
        }
        
        .logout-btn {
            position: fixed;
            top: 20px;
            right: 20px;
            background: #666;
            color: white;
            border: none;
            padding: 10px 15px;
            border-radius: 5px;
            cursor: pointer;
            text-decoration: none;
            font-size: 0.9rem;
        }
        
        .logout-btn:hover {
            background: #888;
        }
        
        @media (max-width: 768px) {
            .main-content {
                grid-template-columns: 1fr;
            }
            
            .cameras-grid {
                grid-template-columns: 1fr;
            }
            
            .action-buttons {
                grid-template-columns: 1fr;
            }
            
            .logo {
                font-size: 2rem;
            }
        }
    </style>
</head>
<body>
    <a href="/logout" class="logout-btn">Sair</a>
    
    <div class="header">
        <div class="logo">MOEDOR AO VIVO</div>
        <div class="subtitle">Sistema Exclusivo para Assinantes</div>
    </div>
    
    <div class="main-content">
        <div class="video-section">
            <div class="cameras-grid">
                <div class="camera-feed">
                    <div class="camera-label">CÂMERA 1</div>
                    <div>Feed da Câmera Principal</div>
                </div>
                <div class="camera-feed">
                    <div class="camera-label">CÂMERA 2</div>
                    <div>Feed da Câmera Secundária</div>
                </div>
            </div>
            
            <div class="action-buttons">
                <button class="action-btn expensive">
                    🎭 Envergonhar Apresentador
                    <div class="tooltip">O programa será interrompido por uma verdade extremamente constrangedora sobre um dos apresentadores. Alguém ficará cinza de vergonha.</div>
                </button>
                <button class="action-btn">
                    💰 Enviar uma Grana pra Participar
                    <div class="tooltip">A qualquer momento podemos vender algo. Caneca exclusiva, pack do pé, camiseta ou algo que surgir durante a conversa.</div>
                </button>
            </div>
        </div>
        
        <div class="sidebar">
            <div class="chat-section">
                <div class="section-title">💬 Interaja com Nois!</div>
                <div class="chat-description">
                    Suas mensagens aparecerão na tela e serão pauta do nosso papo!
                </div>
                <div class="messages" id="messages">
                    <div class="message">Sistema iniciado! Envie sua mensagem.</div>
                </div>
                <input type="text" class="chat-input" id="messageInput" placeholder="Digite sua mensagem...">
                <button class="send-btn" onclick="sendMessage()">Enviar Mensagem</button>
            </div>
            
            <div class="mural-section">
                <div class="section-title">🫠 Mural do Derretimento</div>
                <div class="mural-description">
                    Prints capturados aleatoriamente quando um dos integrantes faz uma cara bizarra, leva um susto, grita, chora ou chupa um pênis.
                </div>
                <div class="mural-grid" id="muralGrid">
                    <div class="mural-item">Print 1</div>
                    <div class="mural-item">Print 2</div>
                    <div class="mural-item">Print 3</div>
                    <div class="mural-item">Print 4</div>
                </div>
            </div>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (message) {
                socket.emit('new_message', {
                    message: message,
                    timestamp: new Date().toISOString()
                });
                input.value = '';
            }
        }
        
        document.getElementById('messageInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        socket.on('message_received', function(data) {
            const messagesDiv = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';
            messageDiv.innerHTML = `<strong>Usuário:</strong> ${data.message}`;
            messagesDiv.appendChild(messageDiv);
            messagesDiv.scrollTop = messagesDiv.scrollHeight;
        });
        
        // Verificar se logo carregou
        console.log('✅ Sistema MOEDOR AO VIVO carregado!');
        
        // Verificar se fonte carregou
        document.fonts.ready.then(function() {
            console.log('✅ Fontes carregadas!');
        });
    </script>
</body>
</html>
'''

admin_template = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - MOEDOR AO VIVO</title>
    <style>
        body { font-family: Arial; background: #000; color: #fff; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .stats-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-box { background: #111; padding: 20px; border-radius: 10px; border-left: 4px solid #00aa00; }
        .stat-number { font-size: 2rem; font-weight: bold; color: #00aa00; }
        .stat-label { color: #ccc; margin-top: 5px; }
        .back-btn { background: #666; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎛️ Painel Administrativo - MOEDOR AO VIVO</h1>
            <a href="/" class="back-btn">← Voltar ao Sistema</a>
        </div>
        
        <div class="stats-grid">
            <div class="stat-box">
                <div class="stat-number">{{ local_buyers }}</div>
                <div class="stat-label">Compradores Lista Local</div>
            </div>
            
            <div class="stat-box">
                <div class="stat-number">{{ verified_buyers }}</div>
                <div class="stat-label">Verificados Hotmart</div>
            </div>
            
            <div class="stat-box">
                <div class="stat-number">{{ authenticated_users|length }}</div>
                <div class="stat-label">Usuários Online</div>
            </div>
            
            <div class="stat-box">
                <div class="stat-number">{% if hotmart_configured %}✅{% else %}❌{% endif %}</div>
                <div class="stat-label">Hotmart Configurado</div>
            </div>
        </div>
        
        <div style="background: #111; padding: 20px; border-radius: 10px;">
            <h3>👥 Usuários Autenticados</h3>
            {% for email, user in authenticated_users.items() %}
            <div style="background: #222; padding: 10px; margin: 5px 0; border-radius: 5px;">
                <strong>{{ email }}</strong> - Login: {{ user.login_time.strftime('%H:%M:%S') }}
            </div>
            {% endfor %}
        </div>
    </div>
</body>
</html>
'''

# WebSocket events
@socketio.on('new_message')
def handle_message(data):
    messages.append(data)
    emit('message_received', data, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    print(f"\n🚀 MOEDOR AO VIVO - Sistema com OAuth Hotmart (Debug)")
    print(f"======================================")
    print(f"🔒 CONFIGURAÇÃO:")
    print(f"   📡 Hotmart: {'✅ Configurado' if HOTMART_CLIENT_ID and HOTMART_CLIENT_SECRET else '❌ Não configurado'}")
    print(f"   👥 Lista Local: {len(local_authorized_buyers)} emails")
    print(f"   🌐 Porta: {port}")
    print(f"   🔗 URL: http://0.0.0.0:{port}")
    print(f"======================================\n")
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False)

