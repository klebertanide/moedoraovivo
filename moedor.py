#!/usr/bin/env python3
"""
MOEDOR AO VIVO - Sistema com Debug de Webhook Hotmart
Testando e corrigindo a integração com Hotmart
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
app.config['SECRET_KEY'] = 'moedor-ao-vivo-2024-secure'
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=30)
socketio = SocketIO(app, cors_allowed_origins="*")

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
    return send_from_directory('.', filename)

# ENDPOINTS DE TESTE E DEBUG
@app.route('/test-webhook')
def test_webhook_page():
    """Página para testar webhook manualmente"""
    return '''
    <!DOCTYPE html>
    <html>
    <head>
        <title>Teste de Webhook</title>
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
        </style>
    </head>
    <body>
        <div class="container">
            <h1>🧪 Teste de Webhook Hotmart</h1>
            
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

# TESTE DE CONECTIVIDADE DO NGROK
@app.route('/ping')
def ping():
    """Endpoint simples para testar conectividade"""
    return jsonify({
        'status': 'ok',
        'timestamp': datetime.now().isoformat(),
        'message': 'MOEDOR AO VIVO está funcionando!',
        'url': request.url,
        'ip': request.remote_addr
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
            return redirect(url_for('home'))
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

@app.route('/')
@login_required
def home():
    return render_template_string(main_template)

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

# Template de login
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
                 onerror="this.style.display='none';">
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
            <a href="/test-webhook" class="debug-link" target="_blank">
                🧪 Testar Webhook
            </a>
            <a href="/api/status" class="debug-link" target="_blank">
                📊 Status
            </a>
        </div>
        
        <div class="info-box">
            🔒 <strong>Sistema com Webhook Hotmart</strong><br>
            Compradores são adicionados automaticamente. Se você acabou de comprar, aguarde alguns minutos.
        </div>
    </div>
    
    <script>
        document.getElementById('email').focus();
        
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

# Template principal
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
            font-weight: 900;
            font-style: normal;
            font-display: swap;
        }
        
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }
        
        body {
            font-family: 'Helvetica', 'Arial', sans-serif;
            background: #000;
            color: #fff;
            min-height: 100vh;
            line-height: 1.4;
        }
        
        .header {
            background: #000;
            padding: 30px 20px;
            text-align: center;
            border-bottom: 1px solid #333;
        }
        
        .logo-container {
            display: flex;
            align-items: center;
            justify-content: center;
            gap: 20px;
            margin-bottom: 15px;
        }
        
        .logo-image {
            width: 120px;
            height: 120px;
            object-fit: contain;
            border: 3px solid #fff;
            background: #fff;
            border-radius: 10px;
            padding: 5px;
        }
        
        .logo-text {
            font-family: 'ZURITA', 'Courier New', monospace;
            font-size: 3.5rem;
            font-weight: 900;
            color: #fff;
            letter-spacing: 2px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
        }
        
        .subtitle {
            font-family: 'Helvetica', sans-serif;
            color: #999;
            font-size: 1rem;
            font-weight: normal;
        }
        
        .main-container {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 20px;
            padding: 20px;
            max-width: 1400px;
            margin: 0 auto;
        }
        
        .camera-section {
            background: #111;
            border: 2px solid #333;
            border-radius: 10px;
            padding: 20px;
            position: relative;
        }
        
        .camera-title {
            font-family: 'ZURITA', 'Courier New', monospace;
            font-size: 1.5rem;
            font-weight: 900;
            color: #fff;
            margin-bottom: 15px;
            text-align: center;
            text-transform: uppercase;
            letter-spacing: 1px;
        }
        
        .camera-feed {
            width: 100%;
            height: 300px;
            background: #000;
            border: 2px solid #444;
            border-radius: 8px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            font-size: 1.1rem;
            margin-bottom: 15px;
            position: relative;
        }
        
        .camera-overlay {
            position: absolute;
            top: 10px;
            left: 10px;
            background: rgba(255, 68, 68, 0.8);
            color: white;
            padding: 5px 10px;
            border-radius: 4px;
            font-size: 0.8rem;
            font-weight: bold;
        }
        
        .action-buttons {
            display: grid;
            grid-template-columns: 1fr 1fr;
            gap: 10px;
        }
        
        .action-btn {
            padding: 15px;
            border: none;
            border-radius: 8px;
            cursor: pointer;
            font-family: 'ZURITA', 'Courier New', monospace;
            font-size: 0.9rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }
        
        .embarrass-btn {
            background: linear-gradient(135deg, #ff4444, #cc0000);
            color: white;
            border: 2px solid #ff6666;
        }
        
        .embarrass-btn:hover {
            background: linear-gradient(135deg, #ff6666, #ee0000);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(255, 68, 68, 0.4);
        }
        
        .sell-btn {
            background: linear-gradient(135deg, #ffa500, #cc8400);
            color: white;
            border: 2px solid #ffcc00;
        }
        
        .sell-btn:hover {
            background: linear-gradient(135deg, #ffcc00, #ee9900);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(255, 165, 0, 0.4);
        }
        
        .action-btn:hover::after {
            content: attr(data-tooltip);
            position: absolute;
            bottom: 100%;
            left: 50%;
            transform: translateX(-50%);
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 8px 12px;
            border-radius: 6px;
            font-size: 0.8rem;
            white-space: nowrap;
            z-index: 1000;
            margin-bottom: 5px;
            max-width: 250px;
            white-space: normal;
            text-align: center;
        }
        
        .chat-section {
            grid-column: 1 / -1;
            background: #111;
            border: 2px solid #00aa00;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .chat-header {
            background: linear-gradient(135deg, #ff4444, #cc0000);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            text-align: center;
        }
        
        .chat-title {
            font-family: 'ZURITA', 'Courier New', monospace;
            font-size: 1.5rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }
        
        .chat-description {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        .messages-container {
            height: 300px;
            background: #000;
            border: 2px solid #333;
            border-radius: 8px;
            padding: 15px;
            overflow-y: auto;
            margin-bottom: 15px;
        }
        
        .message {
            background: rgba(0, 170, 0, 0.1);
            border: 1px solid #00aa00;
            border-radius: 8px;
            padding: 10px;
            margin-bottom: 10px;
        }
        
        .message-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 5px;
        }
        
        .message-email {
            font-weight: bold;
            color: #00cc00;
            font-size: 0.9rem;
        }
        
        .message-time {
            color: #666;
            font-size: 0.8rem;
        }
        
        .message-text {
            color: #fff;
            line-height: 1.4;
        }
        
        .chat-input-container {
            display: flex;
            gap: 10px;
        }
        
        .chat-input {
            flex: 1;
            padding: 15px;
            background: #000;
            border: 2px solid #333;
            border-radius: 8px;
            color: #fff;
            font-size: 1rem;
            font-family: 'Helvetica', sans-serif;
        }
        
        .chat-input:focus {
            outline: none;
            border-color: #00aa00;
            box-shadow: 0 0 10px rgba(0, 170, 0, 0.3);
        }
        
        .send-btn {
            background: linear-gradient(135deg, #00aa00, #006600);
            border: 2px solid #00cc00;
            color: white;
            padding: 15px 25px;
            border-radius: 8px;
            cursor: pointer;
            font-family: 'ZURITA', 'Courier New', monospace;
            font-size: 0.9rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
            transition: all 0.3s ease;
        }
        
        .send-btn:hover {
            background: linear-gradient(135deg, #00cc00, #008800);
            transform: translateY(-2px);
            box-shadow: 0 8px 25px rgba(0, 170, 0, 0.4);
        }
        
        .mural-section {
            grid-column: 1 / -1;
            background: #111;
            border: 2px solid #ffa500;
            border-radius: 10px;
            padding: 20px;
            margin-top: 20px;
        }
        
        .mural-header {
            background: linear-gradient(135deg, #ffa500, #cc8400);
            color: white;
            padding: 15px;
            border-radius: 8px;
            margin-bottom: 15px;
            text-align: center;
        }
        
        .mural-title {
            font-family: 'ZURITA', 'Courier New', monospace;
            font-size: 1.5rem;
            font-weight: 900;
            text-transform: uppercase;
            letter-spacing: 1px;
            margin-bottom: 5px;
        }
        
        .mural-description {
            font-size: 0.9rem;
            opacity: 0.9;
        }
        
        .mural-grid {
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
            gap: 15px;
        }
        
        .mural-item {
            background: #000;
            border: 2px solid #333;
            border-radius: 8px;
            padding: 15px;
            text-align: center;
            transition: all 0.3s ease;
        }
        
        .mural-item:hover {
            border-color: #ffa500;
            transform: translateY(-2px);
        }
        
        .mural-placeholder {
            width: 100%;
            height: 120px;
            background: #222;
            border: 1px dashed #444;
            border-radius: 6px;
            display: flex;
            align-items: center;
            justify-content: center;
            color: #666;
            font-size: 0.9rem;
            margin-bottom: 10px;
        }
        
        .mural-caption {
            color: #ffa500;
            font-size: 0.8rem;
            font-weight: bold;
        }
        
        .logout-btn {
            position: fixed;
            top: 20px;
            right: 20px;
            background: rgba(255, 68, 68, 0.8);
            border: 2px solid #ff4444;
            color: white;
            padding: 10px 15px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 0.9rem;
            text-decoration: none;
            transition: all 0.3s ease;
            font-family: 'ZURITA', monospace;
            font-weight: 900;
            text-transform: uppercase;
        }
        
        .logout-btn:hover {
            background: rgba(255, 68, 68, 1);
            transform: translateY(-1px);
        }
        
        @media (max-width: 768px) {
            .main-container {
                grid-template-columns: 1fr;
                padding: 10px;
            }
            
            .logo-text {
                font-size: 2.5rem;
            }
            
            .logo-container {
                flex-direction: column;
                gap: 10px;
            }
            
            .action-buttons {
                grid-template-columns: 1fr;
            }
        }
    </style>
</head>
<body>
    <a href="/logout" class="logout-btn">🚪 Sair</a>
    
    <div class="header">
        <div class="logo-container">
            <img src="/logo.png" alt="MOEDOR AO VIVO" class="logo-image" 
                 onerror="this.style.display='none';">
            <h1 class="logo-text">MOEDOR AO VIVO</h1>
        </div>
        <p class="subtitle">Sistema de Interação em Tempo Real</p>
    </div>
    
    <div class="main-container">
        <div class="camera-section">
            <h2 class="camera-title">📹 CÂMERA 1</h2>
            <div class="camera-feed">
                <div class="camera-overlay">● AO VIVO</div>
                🎥 Conectar OBS Studio aqui
            </div>
            <div class="action-buttons">
                <button class="action-btn embarrass-btn" 
                        data-tooltip="O programa será interrompido por uma verdade extremamente constrangedora sobre um dos apresentadores. Alguém ficará cinza de vergonha."
                        onclick="embarrassPresenter()">
                    🎭 Envergonhar Apresentador<br>R$20
                </button>
                <button class="action-btn sell-btn"
                        data-tooltip="A qualquer momento podemos vender algo. Caneca exclusiva, pack do pé, camiseta ou algo que surgir durante a conversa."
                        onclick="sellSomething()">
                    📦 Enviar uma Grana<br>pra Participar
                </button>
            </div>
        </div>
        
        <div class="camera-section">
            <h2 class="camera-title">📹 CÂMERA 2</h2>
            <div class="camera-feed">
                <div class="camera-overlay">● AO VIVO</div>
                🎥 Conectar OBS Studio aqui
            </div>
            <div class="action-buttons">
                <button class="action-btn embarrass-btn" 
                        data-tooltip="O programa será interrompido por uma verdade extremamente constrangedora sobre um dos apresentadores. Alguém ficará cinza de vergonha."
                        onclick="embarrassPresenter()">
                    🎭 Envergonhar Apresentador<br>R$20
                </button>
                <button class="action-btn sell-btn"
                        data-tooltip="A qualquer momento podemos vender algo. Caneca exclusiva, pack do pé, camiseta ou algo que surgir durante a conversa."
                        onclick="sellSomething()">
                    📦 Enviar uma Grana<br>pra Participar
                </button>
            </div>
        </div>
    </div>
    
    <div class="chat-section">
        <div class="chat-header">
            <h2 class="chat-title">💬 Interaja com Nois!</h2>
            <p class="chat-description">Suas mensagens aparecerão na tela e serão pauta do nosso papo!</p>
        </div>
        
        <div class="messages-container" id="messages">
            <!-- Mensagens aparecerão aqui -->
        </div>
        
        <div class="chat-input-container">
            <input type="text" 
                   id="messageInput" 
                   class="chat-input" 
                   placeholder="Digite sua mensagem..."
                   maxlength="200">
            <button onclick="sendMessage()" class="send-btn">
                📤 Enviar
            </button>
        </div>
    </div>
    
    <div class="mural-section">
        <div class="mural-header">
            <h2 class="mural-title">🫠 Mural do Derretimento</h2>
            <p class="mural-description">Prints capturados aleatoriamente quando um dos integrantes faz uma cara bizarra, leva um susto, grita, chora ou chupa um pênis.</p>
        </div>
        
        <div class="mural-grid" id="muralGrid">
            <div class="mural-item">
                <div class="mural-placeholder">
                    📸 Aguardando captures...
                </div>
                <div class="mural-caption">Primeiro derretimento</div>
            </div>
            <div class="mural-item">
                <div class="mural-placeholder">
                    📸 Aguardando captures...
                </div>
                <div class="mural-caption">Segundo derretimento</div>
            </div>
            <div class="mural-item">
                <div class="mural-placeholder">
                    📸 Aguardando captures...
                </div>
                <div class="mural-caption">Terceiro derretimento</div>
            </div>
        </div>
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        const socket = io();
        
        // Enviar mensagem
        function sendMessage() {
            const input = document.getElementById('messageInput');
            const message = input.value.trim();
            
            if (message) {
                socket.emit('send_message', {
                    text: message,
                    timestamp: new Date().toISOString()
                });
                input.value = '';
            }
        }
        
        // Enter para enviar
        document.getElementById('messageInput').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
        
        // Receber mensagens
        socket.on('new_message', function(data) {
            const messagesContainer = document.getElementById('messages');
            const messageDiv = document.createElement('div');
            messageDiv.className = 'message';
            
            const time = new Date(data.timestamp).toLocaleTimeString();
            
            messageDiv.innerHTML = `
                <div class="message-header">
                    <span class="message-email">${data.user_email}</span>
                    <span class="message-time">${time}</span>
                </div>
                <div class="message-text">${data.text}</div>
            `;
            
            messagesContainer.appendChild(messageDiv);
            messagesContainer.scrollTop = messagesContainer.scrollHeight;
        });
        
        // Receber notificação de novo comprador
        socket.on('new_buyer', function(data) {
            console.log('✅ Novo comprador adicionado:', data.email);
        });
        
        // Funções dos botões
        function embarrassPresenter() {
            if (confirm('Envergonhar apresentador por R$ 20,00?')) {
                alert('💳 Redirecionando para pagamento...');
                // Aqui integraria com sistema de pagamento
            }
        }
        
        function sellSomething() {
            alert('🛒 Abrindo loja de produtos exclusivos...');
            // Aqui integraria com loja
        }
        
        // Verificar fontes carregadas
        document.fonts.ready.then(function() {
            console.log('✅ Fontes carregadas!');
        });
        
        // Verificar logo carregado
        const logo = document.querySelector('.logo-image');
        if (logo) {
            logo.onload = function() {
                console.log('✅ Logo carregado!');
            };
            logo.onerror = function() {
                console.log('❌ Logo não encontrado');
            };
        }
    </script>
</body>
</html>
'''

# Template admin
admin_template = '''
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MOEDOR AO VIVO - Admin</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        
        body {
            font-family: 'Helvetica', Arial, sans-serif;
            background: #000;
            color: #fff;
            min-height: 100vh;
            padding: 20px;
        }
        
        .admin-container {
            max-width: 1200px;
            margin: 0 auto;
        }
        
        .admin-header {
            background: #111;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #ff4444;
            margin-bottom: 20px;
            text-align: center;
        }
        
        .admin-title {
            font-size: 2rem;
            color: #ff4444;
            margin-bottom: 10px;
        }
        
        .stats-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            margin-bottom: 20px;
        }
        
        .stat-card {
            background: #111;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #333;
            text-align: center;
        }
        
        .stat-number {
            font-size: 2rem;
            font-weight: bold;
            color: #00aa00;
            margin-bottom: 5px;
        }
        
        .stat-label {
            color: #999;
            font-size: 0.9rem;
        }
        
        .webhook-section {
            background: #111;
            padding: 20px;
            border-radius: 10px;
            border: 2px solid #333;
            margin-bottom: 20px;
        }
        
        .webhook-title {
            font-size: 1.5rem;
            color: #ffa500;
            margin-bottom: 15px;
        }
        
        .webhook-info {
            background: #000;
            padding: 15px;
            border-radius: 6px;
            border: 1px solid #333;
            font-family: monospace;
            font-size: 0.9rem;
            line-height: 1.6;
        }
        
        .back-btn {
            background: #666;
            border: 2px solid #888;
            color: white;
            padding: 10px 20px;
            border-radius: 6px;
            cursor: pointer;
            text-decoration: none;
            display: inline-block;
            margin-bottom: 20px;
        }
        
        .back-btn:hover {
            background: #888;
        }
        
        .test-links {
            display: flex;
            gap: 10px;
            margin-top: 15px;
        }
        
        .test-link {
            background: #00aa00;
            color: white;
            padding: 8px 15px;
            border-radius: 4px;
            text-decoration: none;
            font-size: 0.9rem;
        }
        
        .test-link:hover {
            background: #00cc00;
        }
    </style>
</head>
<body>
    <div class="admin-container">
        <a href="/" class="back-btn">← Voltar ao Sistema</a>
        
        <div class="admin-header">
            <h1 class="admin-title">🎛️ PAINEL ADMINISTRATIVO</h1>
            <p>Gerenciamento de compradores e webhook</p>
        </div>
        
        <div class="stats-grid">
            <div class="stat-card">
                <div class="stat-number">{{ authorized_count }}</div>
                <div class="stat-label">Compradores Autorizados</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ authenticated_users|length }}</div>
                <div class="stat-label">Usuários Online</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ messages|length }}</div>
                <div class="stat-label">Mensagens Enviadas</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ webhook_count }}</div>
                <div class="stat-label">Webhooks Recebidos</div>
            </div>
            <div class="stat-card">
                <div class="stat-number">{{ hotmart_buyers }}</div>
                <div class="stat-label">Compradores da Hotmart</div>
            </div>
        </div>
        
        <div class="webhook-section">
            <h2 class="webhook-title">📡 Configuração do Webhook</h2>
            
            <div class="webhook-info">
                <strong>🔗 URL do Webhook:</strong><br>
                https://quiet-routinely-insect.ngrok-free.app/webhook/hotmart<br><br>
                
                <strong>📋 Eventos para configurar na Hotmart:</strong><br>
                • PURCHASE_APPROVED<br>
                • PURCHASE_COMPLETE<br>
                • PURCHASE_BILLET_PRINTED<br><br>
                
                <strong>📊 Status:</strong> Ativo e monitorando<br>
                <strong>🔧 Método:</strong> POST<br>
                <strong>📦 Formato:</strong> JSON ou Form Data
            </div>
            
            <div class="test-links">
                <a href="/test-webhook" class="test-link" target="_blank">
                    🧪 Testar Webhook
                </a>
                <a href="/api/status" class="test-link" target="_blank">
                    📊 Status JSON
                </a>
                <a href="/ping" class="test-link" target="_blank">
                    🏓 Ping
                </a>
            </div>
        </div>
    </div>
    
    <script>
        // Atualizar estatísticas a cada 10 segundos
        setInterval(() => {
            location.reload();
        }, 10000);
    </script>
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
    print("🚀 MOEDOR AO VIVO - Debug de Webhook Hotmart")
    print("=" * 60)
    print("🔧 MODO DEBUG ATIVO:")
    print("   - Logs detalhados de webhook")
    print("   - Página de teste: /test-webhook")
    print("   - Status da API: /api/status")
    print("   - Teste de conectividade: /ping")
    print()
    print("🌐 URLs IMPORTANTES:")
    print("   🔐 Login: http://localhost:5001/login")
    print("   🧪 Teste Webhook: http://localhost:5001/test-webhook")
    print("   📊 Status: http://localhost:5001/api/status")
    print("   🏓 Ping: http://localhost:5001/ping")
    print()
    print("📡 WEBHOOK HOTMART:")
    print("   URL: https://quiet-routinely-insect.ngrok-free.app/webhook/hotmart")
    print("   Método: POST")
    print("   Eventos: PURCHASE_APPROVED, PURCHASE_COMPLETE")
    print()
    print("✅ COMPRADORES INICIAIS:")
    for email in sorted(authorized_buyers):
        print(f"   📧 {email}")
    print()
    print("⏹️ Pressione Ctrl+C para parar")
    print("=" * 60)
    
    socketio.run(app, host='0.0.0.0', port=5001, debug=False)

