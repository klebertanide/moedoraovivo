#!/usr/bin/env python3
"""
MOEDOR AO VIVO - Versão para Deploy no Render.com
Sistema com webhook Hotmart e URL permanente
"""

from flask import Flask, render_template_string, send_from_directory, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
import os
import json
import hashlib
import hmac
from datetime import datetime, timedelta
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'moedor-ao-vivo-2024-secure')
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Lista inicial de compradores (será atualizada pelo webhook)
authorized_buyers = {
    'admin@moedor.com',
    'teste@moedor.com',
    'kaa.naomi25@gmail.com',  # Para teste inicial
}

# Log de webhooks recebidos
webhook_logs = []
hotmart_buyers = set()  # Compradores vindos da Hotmart

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

def is_authorized_buyer(email):
    """Verifica se o email está autorizado (lista inicial + Hotmart)"""
    email = email.lower().strip()
    
    # Combinar lista inicial + compradores da Hotmart
    all_buyers = authorized_buyers.union(hotmart_buyers)
    
    print(f"\n🔍 === VERIFICAÇÃO DE COMPRADOR ===")
    print(f"📧 Email: '{email}'")
    print(f"📋 Compradores iniciais: {len(authorized_buyers)}")
    print(f"🛒 Compradores Hotmart: {len(hotmart_buyers)}")
    print(f"📊 Total autorizado: {len(all_buyers)}")
    print(f"✅ Autorizado: {email in all_buyers}")
    print(f"================================\n")
    
    return email in all_buyers

def log_webhook(data, source="unknown"):
    """Registra webhook recebido"""
    webhook_logs.append({
        'timestamp': datetime.now().isoformat(),
        'source': source,
        'data': data,
        'headers': dict(request.headers) if request else {}
    })
    
    # Manter apenas os últimos 50 logs
    if len(webhook_logs) > 50:
        webhook_logs.pop(0)

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
@app.route('/test-webhook')
def test_webhook_page():
    """Página para testar webhook manualmente"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste de Webhook - MOEDOR AO VIVO</title>
        <style>
            body { font-family: Arial; background: #000; color: #fff; padding: 20px; }
            .container { max-width: 800px; margin: 0 auto; }
            .form-group { margin: 15px 0; }
            label { display: block; margin-bottom: 5px; color: #00aa00; }
            input, textarea, select { width: 100%; padding: 10px; background: #111; border: 1px solid #333; color: #fff; }
            button { background: #00aa00; color: white; padding: 10px 20px; border: none; cursor: pointer; margin: 5px; }
            .log { background: #111; padding: 10px; margin: 10px 0; border-left: 3px solid #00aa00; }
            .error { border-left-color: #ff4444; }
            .success { border-left-color: #00aa00; }
            .header { text-align: center; margin-bottom: 30px; }
            .back-btn { background: #666; color: white; padding: 8px 15px; text-decoration: none; border-radius: 4px; }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🧪 Teste de Webhook Hotmart</h1>
                <a href="/" class="back-btn">← Voltar ao Sistema</a>
            </div>
            
            <form onsubmit="testWebhook(event)">
                <div class="form-group">
                    <label>Email do Comprador:</label>
                    <input type="email" id="buyerEmail" value="teste.comprador@email.com" required>
                </div>
                
                <div class="form-group">
                    <label>Evento:</label>
                    <select id="eventType">
                        <option value="PURCHASE_APPROVED">PURCHASE_APPROVED</option>
                        <option value="PURCHASE_COMPLETE">PURCHASE_COMPLETE</option>
                        <option value="PURCHASE_BILLET_PRINTED">PURCHASE_BILLET_PRINTED</option>
                    </select>
                </div>
                
                <button type="submit">🚀 Simular Webhook</button>
                <button type="button" onclick="loadStatus()">🔄 Atualizar Status</button>
                <button type="button" onclick="loadLogs()">📝 Carregar Logs</button>
            </form>
            
            <h2>📊 Status do Sistema</h2>
            <div id="status"></div>
            
            <h2>📝 Logs de Webhook (Últimos 10)</h2>
            <div id="logs"></div>
            
            <h2>👥 Compradores Autorizados</h2>
            <div id="buyers"></div>
        </div>
        
        <script>
            function testWebhook(event) {
                event.preventDefault();
                
                const email = document.getElementById('buyerEmail').value;
                const eventType = document.getElementById('eventType').value;
                
                const webhookData = {
                    event: eventType,
                    data: {
                        buyer: {
                            email: email,
                            name: "Comprador Teste"
                        },
                        product: {
                            id: "123456",
                            name: "MOEDOR"
                        }
                    }
                };
                
                fetch('/webhook/hotmart', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(webhookData)
                })
                .then(response => response.json())
                .then(data => {
                    alert('✅ Webhook enviado com sucesso!');
                    loadStatus();
                    loadLogs();
                })
                .catch(error => {
                    alert('❌ Erro: ' + error);
                });
            }
            
            function loadStatus() {
                fetch('/api/status')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('status').innerHTML = `
                        <div class="log success">
                            <strong>📊 Compradores Autorizados:</strong> ${data.total_buyers}<br>
                            <strong>📋 Iniciais:</strong> ${data.initial_buyers}<br>
                            <strong>🛒 Da Hotmart:</strong> ${data.hotmart_buyers}<br>
                            <strong>📝 Webhooks Recebidos:</strong> ${data.webhook_count}<br>
                            <strong>👥 Usuários Online:</strong> ${data.users_online}
                        </div>
                    `;
                    
                    const buyersHtml = data.buyers_list.map(email => `
                        <div class="log">📧 ${email}</div>
                    `).join('');
                    document.getElementById('buyers').innerHTML = buyersHtml;
                });
            }
            
            function loadLogs() {
                fetch('/api/webhook-logs')
                .then(response => response.json())
                .then(data => {
                    const logsHtml = data.logs.map(log => `
                        <div class="log ${log.source === 'error' ? 'error' : 'success'}">
                            <strong>⏰ ${log.timestamp}</strong> - 📡 ${log.source}<br>
                            <pre>${JSON.stringify(log.data, null, 2)}</pre>
                        </div>
                    `).join('');
                    document.getElementById('logs').innerHTML = logsHtml || '<div class="log">Nenhum log ainda</div>';
                });
            }
            
            // Carregar dados iniciais
            loadStatus();
            loadLogs();
            
            // Atualizar a cada 5 segundos
            setInterval(() => {
                loadStatus();
                loadLogs();
            }, 5000);
        </script>
    </body>
    </html>
    '''

@app.route('/api/status')
def api_status():
    """Status do sistema em JSON"""
    all_buyers = authorized_buyers.union(hotmart_buyers)
    return jsonify({
        'total_buyers': len(all_buyers),
        'initial_buyers': len(authorized_buyers),
        'hotmart_buyers': len(hotmart_buyers),
        'webhook_count': len(webhook_logs),
        'users_online': len(authenticated_users),
        'buyers_list': sorted(list(all_buyers))
    })

@app.route('/api/webhook-logs')
def api_webhook_logs():
    """Logs de webhook em JSON"""
    return jsonify({
        'logs': webhook_logs[-10:],  # Últimos 10 logs
        'total': len(webhook_logs)
    })

# WEBHOOK DA HOTMART - VERSÃO COM DEBUG COMPLETO
@app.route('/webhook/hotmart', methods=['POST', 'GET'])
def hotmart_webhook():
    """Webhook para receber notificações da Hotmart"""
    
    if request.method == 'GET':
        return jsonify({
            'status': 'Webhook ativo',
            'method': 'POST esperado',
            'url': request.url,
            'timestamp': datetime.now().isoformat()
        })
    
    try:
        # Log da requisição completa
        print(f"\n🔔 === WEBHOOK RECEBIDO ===")
        print(f"⏰ Timestamp: {datetime.now()}")
        print(f"🌐 URL: {request.url}")
        print(f"📋 Headers: {dict(request.headers)}")
        print(f"📦 Content-Type: {request.content_type}")
        
        # Tentar diferentes formatos de dados
        webhook_data = None
        
        if request.content_type == 'application/json':
            webhook_data = request.get_json()
            print(f"📄 JSON Data: {webhook_data}")
        elif request.content_type == 'application/x-www-form-urlencoded':
            webhook_data = dict(request.form)
            print(f"📄 Form Data: {webhook_data}")
        else:
            # Tentar como texto
            raw_data = request.get_data(as_text=True)
            print(f"📄 Raw Data: {raw_data}")
            try:
                webhook_data = json.loads(raw_data)
            except:
                webhook_data = {'raw': raw_data}
        
        # Registrar no log
        log_webhook(webhook_data, 'hotmart')
        
        # Processar dados se for evento de compra
        if webhook_data and isinstance(webhook_data, dict):
            event = webhook_data.get('event', '').upper()
            print(f"🎯 Evento: {event}")
            
            if event in ['PURCHASE_APPROVED', 'PURCHASE_COMPLETE', 'PURCHASE_BILLET_PRINTED']:
                # Tentar extrair email do comprador
                buyer_email = None
                
                # Formato padrão da Hotmart
                if 'data' in webhook_data and 'buyer' in webhook_data['data']:
                    buyer_email = webhook_data['data']['buyer'].get('email')
                
                # Formato alternativo
                elif 'buyer' in webhook_data:
                    buyer_email = webhook_data['buyer'].get('email')
                
                # Formato direto
                elif 'email' in webhook_data:
                    buyer_email = webhook_data['email']
                
                if buyer_email:
                    buyer_email = buyer_email.lower().strip()
                    hotmart_buyers.add(buyer_email)
                    
                    print(f"✅ NOVO COMPRADOR ADICIONADO: {buyer_email}")
                    print(f"📊 Total de compradores Hotmart: {len(hotmart_buyers)}")
                    
                    # Notificar via WebSocket
                    socketio.emit('new_buyer', {
                        'email': buyer_email,
                        'timestamp': datetime.now().isoformat(),
                        'event': event,
                        'source': 'hotmart'
                    })
                else:
                    print(f"❌ Email do comprador não encontrado nos dados")
            else:
                print(f"ℹ️ Evento ignorado: {event}")
        
        print(f"========================\n")
        
        return jsonify({'status': 'success', 'timestamp': datetime.now().isoformat()}), 200
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ ERRO NO WEBHOOK: {error_msg}")
        
        log_webhook({'error': error_msg}, 'error')
        
        return jsonify({'status': 'error', 'message': error_msg}), 400

# TESTE DE CONECTIVIDADE
@app.route('/ping')
def ping():
    """Endpoint simples para testar conectividade"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'message': 'MOEDOR AO VIVO está funcionando!',
        'url': request.url,
        'ip': request.remote_addr,
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
                error="Email não encontrado na lista de compradores. Aguarde alguns minutos se você acabou de comprar, ou entre em contato com o suporte.")
    
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
    all_buyers = authorized_buyers.union(hotmart_buyers)
    return render_template_string(admin_template, 
                                authorized_count=len(all_buyers),
                                authenticated_users=authenticated_users,
                                messages=messages,
                                webhook_count=len(webhook_logs),
                                hotmart_buyers=len(hotmart_buyers))

# Templates
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
            cursor: pointer;
            font-family: 'ZURITA', 'Impact', monospace;
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            margin-top: 10px;
        }
        
        .login-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(255, 68, 68, 0.4);
            background: linear-gradient(135deg, #ff6666, #ee0000);
        }
        
        .subscribe-btn {
            background: linear-gradient(135deg, #00aa00, #006600);
            border: none;
            color: white;
            padding: 15px 30px;
            border-radius: 8px;
            cursor: pointer;
            font-family: 'ZURITA', 'Impact', monospace;
            font-size: 1.1rem;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            margin-top: 15px;
            text-decoration: none;
            display: inline-block;
            width: 100%;
            text-align: center;
        }
        
        .subscribe-btn:hover {
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 170, 0, 0.4);
            background: linear-gradient(135deg, #00cc00, #008800);
        }
        
        .error-message {
            background: rgba(255, 68, 68, 0.1);
            border: 1px solid #ff4444;
            color: #ff6666;
            padding: 12px;
            border-radius: 6px;
            margin-bottom: 20px;
            font-size: 0.9rem;
            text-align: left;
            line-height: 1.4;
        }
        
        .info-box {
            background: rgba(0, 170, 0, 0.1);
            border: 1px solid #00aa00;
            color: #00cc00;
            padding: 15px;
            border-radius: 6px;
            margin-top: 20px;
            font-size: 0.85rem;
            line-height: 1.4;
        }
        
        .debug-links {
            margin-top: 20px;
            display: flex;
            gap: 10px;
            justify-content: center;
        }
        
        .debug-link {
            background: #666;
            border: none;
            color: white;
            padding: 8px 12px;
            border-radius: 4px;
            cursor: pointer;
            font-size: 0.8rem;
            text-decoration: none;
            transition: all 0.3s ease;
        }
        
        .debug-link:hover {
            background: #888;
        }
        
        .divider {
            margin: 25px 0;
            text-align: center;
            position: relative;
        }
        
        .divider::before {
            content: '';
            position: absolute;
            top: 50%;
            left: 0;
            right: 0;
            height: 1px;
            background: #333;
        }
        
        .divider span {
            background: rgba(17, 17, 17, 0.95);
            padding: 0 15px;
            color: #666;
            font-size: 0.9rem;
        }
        
        @media (max-width: 480px) {
            .login-container {
                padding: 30px 20px;
            }
            .logo-image {
                width: 120px;
                height: 120px;
            }
            .debug-links {
                flex-direction: column;
            }
        }
    </style>
</head>
<body>
    <div class="login-container">
        <div class="logo-container">
            <img src="/logo.png" alt="MOEDOR AO VIVO" class="logo-image" 
                 onerror="this.style.display='none'; document.querySelector('.logo-text').style.display='block';">
            <h1 class="logo-text" style="display: none;">MOEDOR AO VIVO</h1>
            <p class="subtitle">Acesso Exclusivo para Compradores</p>
        </div>
        
        {% if error %}
        <div class="error-message">
            ❌ {{ error }}
        </div>
        {% endif %}
        
        <form class="login-form" method="POST">
            <div class="form-group">
                <label class="form-label" for="email">📧 Email da Compra</label>
                <input type="email" 
                       id="email" 
                       name="email" 
                       class="form-input" 
                       placeholder="Digite o email usado na compra..."
                       required
                       autocomplete="email">
            </div>
            
            <button type="submit" class="login-btn">
                🔓 Acessar MOEDOR AO VIVO
            </button>
        </form>
        
        <div class="divider">
            <span>ou</span>
        </div>
        
        <a href="https://moedor.com" class="subscribe-btn" target="_blank">
            🚀 Assinar o MOEDOR Agora
        </a>
        
        <div class="debug-links">
            <a href="/test-webhook" class="debug-link">
                🧪 Testar Webhook
            </a>
            <a href="/api/status" class="debug-link">
                📊 Status
            </a>
            <a href="/ping" class="debug-link">
                🏓 Ping
            </a>
        </div>
        
        <div class="info-box">
            🔒 <strong>Sistema Hospedado no Render.com</strong><br>
            URL permanente e webhook estável. Compradores são adicionados automaticamente.
        </div>
    </div>
    
    <script>
        document.getElementById('email' ).focus();
        
        document.getElementById('email').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.querySelector('.login-form').submit();
            }
        });
        
        document.querySelector('.login-form').addEventListener('submit', function() {
            const btn = document.querySelector('.login-btn');
            btn.innerHTML = '🔄 Verificando compra...';
            btn.disabled = true;
        });
    </script>
</body>
</html>
'''

# Template principal simplificado
main_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>MOEDOR AO VIVO</title>
    <style>
        body { background: #000; color: #fff; font-family: Arial; padding: 20px; }
        .container { max-width: 1200px; margin: 0 auto; }
        .header { text-align: center; margin-bottom: 30px; }
        .cameras { display: grid; grid-template-columns: 1fr 1fr; gap: 20px; margin-bottom: 30px; }
        .camera { background: #111; border: 2px solid #ff4444; border-radius: 10px; padding: 20px; text-align: center; }
        .chat { background: #111; border: 2px solid #00aa00; border-radius: 10px; padding: 20px; }
        .logout-btn { position: absolute; top: 20px; right: 20px; background: #666; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <a href="/logout" class="logout-btn">🚪 Sair</a>
    
    <div class="container">
        <div class="header">
            <h1>🎥 MOEDOR AO VIVO</h1>
            <p>Sistema funcionando no Render.com!</p>
        </div>
        
        <div class="cameras">
            <div class="camera">
                <h3>📹 Câmera 1</h3>
                <p>Stream principal</p>
                <button style="background: #ff4444; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px;">
                    💰 Envergonhar Apresentador (R$ 20)
                </button>
            </div>
            
            <div class="camera">
                <h3>📹 Câmera 2</h3>
                <p>Stream secundário</p>
                <button style="background: #00aa00; color: white; padding: 10px 20px; border: none; border-radius: 5px; margin: 5px;">
                    🛒 Enviar uma Grana pra Participar
                </button>
            </div>
        </div>
        
        <div class="chat">
            <h3>💬 Chat ao Vivo</h3>
            <div style="background: #000; padding: 15px; border-radius: 5px; margin: 10px 0; min-height: 200px;">
                <p>💬 Sistema de chat funcionando!</p>
                <p>🔗 Webhook integrado com Hotmart</p>
                <p>✅ Deploy realizado com sucesso no Render.com</p>
            </div>
            
            <div style="display: flex; gap: 10px; margin-top: 15px;">
                <input type="text" placeholder="Digite sua mensagem..." style="flex: 1; padding: 10px; background: #222; border: 1px solid #444; color: #fff; border-radius: 5px;">
                <button style="background: #00aa00; color: white; padding: 10px 20px; border: none; border-radius: 5px;">Enviar</button>
            </div>
        </div>
        
        <div style="text-align: center; margin-top: 30px; padding: 20px; background: #111; border-radius: 10px;">
            <h3>🎯 Sistema Funcionando!</h3>
            <p>✅ Deploy no Render.com realizado com sucesso</p>
            <p>✅ Webhook da Hotmart configurado</p>
            <p>✅ Sistema de login funcionando</p>
            <p>✅ URL permanente ativa</p>
            
            <div style="margin-top: 20px;">
                <a href="/admin" style="background: #666; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                    🎛️ Painel Admin
                </a>
                <a href="/test-webhook" style="background: #666; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                    🧪 Testar Webhook
                </a>
                <a href="/api/status" style="background: #666; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                    📊 Status
                </a>
            </div>
        </div>
    </div>
</body>
</html>
'''

# Template admin simplificado
admin_template = '''
<!DOCTYPE html>
<html>
<head>
    <title>Admin - MOEDOR AO VIVO</title>
    <style>
        body { background: #000; color: #fff; font-family: Arial; padding: 20px; }
        .container { max-width: 1000px; margin: 0 auto; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 20px; margin-bottom: 30px; }
        .stat-card { background: #111; border: 2px solid #00aa00; border-radius: 10px; padding: 20px; text-align: center; }
        .back-btn { background: #666; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; }
    </style>
</head>
<body>
    <div class="container">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 30px;">
            <h1>🎛️ Painel Administrativo</h1>
            <a href="/" class="back-btn">← Voltar</a>
        </div>
        
        <div class="stats">
            <div class="stat-card">
                <h3>👥 Compradores</h3>
                <p style="font-size: 2rem; margin: 10px 0;">{{ authorized_count }}</p>
                <p>Total autorizados</p>
            </div>
            
            <div class="stat-card">
                <h3>🔗 Webhooks</h3>
                <p style="font-size: 2rem; margin: 10px 0;">{{ webhook_count }}</p>
                <p>Recebidos da Hotmart</p>
            </div>
            
            <div class="stat-card">
                <h3>🛒 Hotmart</h3>
                <p style="font-size: 2rem; margin: 10px 0;">{{ hotmart_buyers }}</p>
                <p>Compradores via webhook</p>
            </div>
            
            <div class="stat-card">
                <h3>💬 Mensagens</h3>
                <p style="font-size: 2rem; margin: 10px 0;">{{ messages|length }}</p>
                <p>Total no chat</p>
            </div>
        </div>
        
        <div style="background: #111; border: 2px solid #ff4444; border-radius: 10px; padding: 20px;">
            <h3>📊 Status do Sistema</h3>
            <p>✅ Sistema rodando no Render.com</p>
            <p>✅ Webhook da Hotmart ativo</p>
            <p>✅ Sistema de login funcionando</p>
            <p>✅ URL permanente configurada</p>
            
            <div style="margin-top: 20px;">
                <a href="/test-webhook" style="background: #00aa00; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                    🧪 Testar Webhook
                </a>
                <a href="/api/status" style="background: #00aa00; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                    📊 Ver Status JSON
                </a>
                <a href="/api/webhook-logs" style="background: #00aa00; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; margin: 5px;">
                    📝 Ver Logs
                </a>
            </div>
        </div>
    </div>
</body>
</html>
'''

# WebSocket events
@socketio.on('send_message')
def handle_message(data):
    global messages
    if 'user_email' not in session or not session.get('authenticated'):
        return
    
    data['user_email'] = session['user_email']
    messages.append(data)
    emit('new_message', data, broadcast=True)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5001))
    
    print("🚀 MOEDOR AO VIVO - Versão Render.com")
    print("=" * 60)
    print("🌐 DEPLOY PERMANENTE:")
    print("   - URL fixa que nunca muda")
    print("   - Webhook estável")
    print("   - Sem necessidade de ngrok")
    print()
    print("🔧 FUNCIONALIDADES:")
    print("   - Logs detalhados de webhook")
    print("   - Página de teste: /test-webhook")
    print("   - Status da API: /api/status")
    print("   - Teste de conectividade: /ping")
    print()
    print("✅ COMPRADORES INICIAIS:")
    for email in sorted(authorized_buyers):
        print(f"   📧 {email}")
    print()
    print(f"🌐 Porta: {port}")
    print("⏹️ Pressione Ctrl+C para parar")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=port, debug=False)
