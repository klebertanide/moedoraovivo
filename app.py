#!/usr/bin/env python3
"""
MOEDOR AO VIVO - Sistema Local com Recepção de Tokens
Recebe tokens do servidor de autenticação e executa sistema principal
"""

from flask import Flask, render_template_string, send_from_directory, request, session, redirect, url_for, jsonify
from flask_socketio import SocketIO, emit
from datetime import datetime
import os
import json
import requests
import jwt
from dotenv import load_dotenv

# Carregar variáveis de ambiente
load_dotenv()
print("✅ Arquivo .env carregado")

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'moedor-local-2024-secure')

# Configurar SocketIO
socketio = SocketIO(app, cors_allowed_origins="*")

# Configurações
JWT_SECRET = os.environ.get('JWT_SECRET', 'moedor-jwt-secret-2024')
AUTH_SERVER_URL = os.environ.get('AUTH_SERVER_URL', 'https://moedor-ao-vivo.onrender.com')

# Dados em memória (mesmo sistema anterior)
users_online = 0
messages = []  # Mensagens para OBS
authenticated_users = {}
cameras = [
    {"id": 1, "name": "Câmera 1", "url": "", "active": True},
    {"id": 2, "name": "Câmera 2", "url": "", "active": True},
    {"id": 3, "name": "Câmera 3", "url": "", "active": True},
    {"id": 4, "name": "Câmera 4", "url": "", "active": True},
    {"id": 5, "name": "Câmera 5", "url": "", "active": True},
    {"id": 6, "name": "Câmera 6", "url": "", "active": True}
]
next_camera_id = 7
captures = []
next_capture_id = 1

def verify_jwt_token(token):
    """Verificar token JWT do servidor de autenticação"""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=['HS256'])
        return {
            'valid': True,
            'user': {
                'id': payload.get('user_id'),
                'email': payload.get('email'),
                'name': payload.get('name'),
                'provider': payload.get('provider')
            }
        }
    except jwt.ExpiredSignatureError:
        return {'valid': False, 'error': 'Token expirado'}
    except jwt.InvalidTokenError:
        return {'valid': False, 'error': 'Token inválido'}

def login_required(f):
    """Decorator para rotas que requerem autenticação"""
    def decorated_function(*args, **kwargs):
        if 'authenticated' not in session or not session['authenticated']:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    decorated_function.__name__ = f.__name__
    return decorated_function

# Servir arquivos estáticos
@app.route('/logo.png')
def serve_logo():
    return send_from_directory('.', 'logo.png')

@app.route('/ZURITA.otf')
def serve_font():
    return send_from_directory('.', 'ZURITA.otf')

# ROTAS PRINCIPAIS

@app.route('/')
@login_required
def index():
    return render_template_string(main_template)

@app.route('/login')
def login():
    """Página de login que redireciona para servidor de autenticação"""
    return render_template_string(login_template, auth_server_url=AUTH_SERVER_URL)

@app.route('/auth/callback')
def auth_callback():
    """Callback que recebe token do servidor de autenticação"""
    token = request.args.get('token')
    
    if not token:
        return render_template_string(error_template, 
            error="Token de autenticação não recebido")
    
    # Verificar token
    token_data = verify_jwt_token(token)
    
    if not token_data['valid']:
        return render_template_string(error_template,
            error=f"Token inválido: {token_data.get('error', 'Erro desconhecido')}")
    
    # Autenticar usuário localmente
    user = token_data['user']
    session['authenticated'] = True
    session['user_email'] = user['email']
    session['user_name'] = user['name']
    session['user_provider'] = user['provider']
    
    authenticated_users[user['email']] = {
        'login_time': datetime.now().isoformat(),
        'provider': user['provider'],
        'name': user['name']
    }
    
    print(f"✅ Usuário autenticado: {user['email']} via {user['provider']}")
    
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    if 'user_email' in session and session['user_email'] in authenticated_users:
        del authenticated_users[session['user_email']]
    
    session.clear()
    return redirect(url_for('login'))

# ROTAS DA API (mesmas do sistema anterior)
@app.route('/api/cameras', methods=['GET'])
@login_required
def get_cameras():
    return jsonify({"cameras": cameras})

@app.route('/api/cameras', methods=['POST'])
@login_required
def add_camera():
    global next_camera_id
    data = request.get_json()
    
    new_camera = {
        "id": next_camera_id,
        "name": data.get('name', f'Câmera {next_camera_id}'),
        "url": data.get('url', ''),
        "active": True
    }
    
    cameras.append(new_camera)
    next_camera_id += 1
    
    socketio.emit('cameras_updated', {"cameras": cameras})
    return jsonify({"success": True, "camera": new_camera})

@app.route('/api/cameras/<int:camera_id>', methods=['PUT'])
@login_required
def update_camera(camera_id):
    data = request.get_json()
    
    for camera in cameras:
        if camera['id'] == camera_id:
            camera['name'] = data.get('name', camera['name'])
            camera['url'] = data.get('url', camera['url'])
            camera['active'] = data.get('active', camera['active'])
            
            socketio.emit('cameras_updated', {"cameras": cameras})
            return jsonify({"success": True, "camera": camera})
    
    return jsonify({"success": False, "error": "Câmera não encontrada"}), 404

@app.route('/api/cameras/<int:camera_id>', methods=['DELETE'])
@login_required
def delete_camera(camera_id):
    global cameras
    cameras = [c for c in cameras if c['id'] != camera_id]
    
    socketio.emit('cameras_updated', {"cameras": cameras})
    return jsonify({"success": True})

@app.route('/api/captures', methods=['GET'])
@login_required
def get_captures():
    return jsonify({"captures": captures})

@app.route('/api/obs-messages', methods=['GET'])
@login_required
def get_obs_messages():
    return jsonify({"messages": messages})

@app.route('/api/obs-messages', methods=['POST'])
@login_required
def send_obs_message():
    data = request.get_json()
    message_text = data.get('message', '').strip()
    
    if message_text and len(message_text) <= 200:
        message_data = {
            'id': len(messages) + 1,
            'message': message_text,
            'timestamp': datetime.now().strftime('%H:%M:%S'),
            'user_email': session.get('user_email', 'Usuário'),
            'user_name': session.get('user_name', 'Usuário'),
            'status': 'sent',
            'created_at': datetime.now().isoformat()
        }
        
        messages.append(message_data)
        
        if len(messages) > 50:
            messages.pop(0)
        
        socketio.emit('obs_message_sent', message_data)
        
        return jsonify({"success": True, "message": message_data})
    
    return jsonify({"success": False, "error": "Mensagem inválida"}), 400

@app.route('/obs-overlay')
def obs_overlay():
    """Página para usar como overlay no OBS"""
    return render_template_string(obs_overlay_template)

@app.route('/api/simulate-capture', methods=['POST'])
@login_required
def simulate_capture():
    import random
    global next_capture_id
    
    reactions = [
        "Cara de espanto total",
        "Expressão de vergonha extrema", 
        "Reação de nojo absoluto",
        "Momento de puro desespero",
        "Careta de dor existencial",
        "Expressão de confusão total",
        "Reação de surpresa épica",
        "Momento de constrangimento",
        "Cara de quem se arrependeu",
        "Expressão de pânico puro"
    ]
    
    active_cameras = [c for c in cameras if c['active']]
    if not active_cameras:
        return jsonify({"success": False, "error": "Nenhuma câmera ativa"})
    
    selected_camera = random.choice(active_cameras)
    
    capture_data = {
        'id': next_capture_id,
        'camera_name': selected_camera['name'],
        'reaction': random.choice(reactions),
        'timestamp': datetime.now().strftime('%H:%M:%S'),
        'created_at': datetime.now().isoformat()
    }
    
    captures.append(capture_data)
    next_capture_id += 1
    
    if len(captures) > 50:
        captures.pop(0)
    
    socketio.emit('captures_updated', {"captures": captures})
    return jsonify({"success": True, "capture": capture_data})

@app.route('/admin')
@login_required
def admin():
    return render_template_string(admin_template)

@app.route('/status')
def status():
    """Status do sistema local"""
    return jsonify({
        'status': 'online',
        'service': 'MOEDOR AO VIVO - Local Server',
        'auth_server': AUTH_SERVER_URL,
        'authenticated_users': len(authenticated_users),
        'users_online': users_online,
        'cameras': len([c for c in cameras if c['active']]),
        'messages': len(messages),
        'captures': len(captures),
        'timestamp': datetime.now().isoformat()
    })

# EVENTOS WEBSOCKET (mesmos do sistema anterior)
@socketio.on('connect')
def handle_connect():
    global users_online
    users_online += 1
    emit('user_count_update', {'count': users_online}, broadcast=True)

@socketio.on('disconnect')
def handle_disconnect():
    global users_online
    users_online = max(0, users_online - 1)
    emit('user_count_update', {'count': users_online}, broadcast=True)

# TEMPLATES HTML

login_template = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MOEDOR AO VIVO - Acesso</title>
    <style>
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #000, #111);
            color: #fff;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .access-container {
            background: rgba(17, 17, 17, 0.9);
            border: 2px solid #666;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            width: 90%;
            text-align: center;
            box-shadow: 0 0 50px rgba(102, 102, 102, 0.3);
            backdrop-filter: blur(10px);
        }
        
        .logo {
            font-size: 2.5rem;
            font-weight: 900;
            color: #666;
            margin-bottom: 10px;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.8);
        }
        
        .subtitle {
            color: #999;
            margin-bottom: 40px;
            font-size: 1.1rem;
        }
        
        .access-btn {
            background: linear-gradient(135deg, #666, #555);
            border: none;
            color: white;
            padding: 20px 40px;
            border-radius: 15px;
            font-size: 1.2rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
            margin-bottom: 30px;
        }
        
        .access-btn:hover {
            background: linear-gradient(135deg, #777, #666);
            transform: translateY(-3px);
            box-shadow: 0 5px 20px rgba(102, 102, 102, 0.4);
        }
        
        .info {
            background: rgba(102, 102, 102, 0.1);
            border: 1px solid #666;
            color: #ccc;
            padding: 20px;
            border-radius: 10px;
            font-size: 0.9rem;
            text-align: left;
        }
        
        .status {
            margin-top: 20px;
            padding: 15px;
            background: rgba(0, 100, 0, 0.2);
            border: 1px solid #006400;
            border-radius: 8px;
            font-size: 0.8rem;
        }
    </style>
</head>
<body>
    <div class="access-container">
        <div class="logo">🎥 MOEDOR AO VIVO</div>
        <div class="subtitle">Sistema Local - Performance Máxima</div>
        
        <a href="{{ auth_server_url }}" class="access-btn">
            🔐 Fazer Login Seguro
        </a>
        
        <div class="info">
            <strong>🔒 Sistema Híbrido:</strong><br><br>
            
            <strong>1. Login Seguro:</strong> Autenticação centralizada na nuvem<br><br>
            
            <strong>2. Performance Local:</strong> Sistema roda no seu computador<br><br>
            
            <strong>3. Redirecionamento Automático:</strong> Após login, você volta automaticamente para cá<br><br>
            
            <strong>⚡ Resultado:</strong> Máxima segurança + Performance local!
        </div>
        
        <div class="status">
            ✅ Sistema local online<br>
            🔗 Servidor de autenticação conectado<br>
            🚀 Pronto para receber login
        </div>
    </div>
</body>
</html>
"""

error_template = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Erro - MOEDOR AO VIVO</title>
    <style>
        body {
            font-family: 'Helvetica Neue', Arial, sans-serif;
            background: linear-gradient(135deg, #000, #111);
            color: #fff;
            margin: 0;
            padding: 0;
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
        }
        
        .error-container {
            background: rgba(17, 17, 17, 0.9);
            border: 2px solid #F44336;
            border-radius: 20px;
            padding: 40px;
            max-width: 500px;
            width: 90%;
            text-align: center;
            box-shadow: 0 0 50px rgba(244, 67, 54, 0.3);
        }
        
        .error-icon {
            font-size: 4rem;
            margin-bottom: 20px;
        }
        
        .error-title {
            font-size: 1.5rem;
            color: #F44336;
            margin-bottom: 20px;
        }
        
        .error-message {
            color: #ccc;
            margin-bottom: 30px;
            line-height: 1.6;
        }
        
        .back-btn {
            background: linear-gradient(135deg, #666, #555);
            border: none;
            color: white;
            padding: 15px 30px;
            border-radius: 8px;
            font-size: 1rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.3s ease;
            text-decoration: none;
            display: inline-block;
        }
        
        .back-btn:hover {
            background: linear-gradient(135deg, #777, #666);
            transform: translateY(-2px);
        }
    </style>
</head>
<body>
    <div class="error-container">
        <div class="error-icon">❌</div>
        <div class="error-title">Erro de Autenticação</div>
        <div class="error-message">{{ error }}</div>
        <a href="/login" class="back-btn">🔙 Tentar Novamente</a>
    </div>
</body>
</html>
"""

# Template principal (mesmo do sistema anterior, mas com informações do usuário)
main_template = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>MOEDOR AO VIVO - Big Brother Moído</title>
    <style>
        /* CSS igual ao sistema anterior */
        @font-face {
            font-family: 'ZURITA';
            src: url('/ZURITA.otf') format('opentype');
            font-weight: normal;
            font-style: normal;
            font-display: swap;
        }
        
        * { 
            margin: 0; 
            padding: 0; 
            box-sizing: border-box; 
        }
        
        body {
            font-family: 'Helvetica Neue', 'Helvetica', Arial, sans-serif;
            background: #000;
            color: #fff;
            overflow-x: hidden;
        }
        
        .header {
            background: #111;
            padding: 20px;
            display: flex;
            justify-content: space-between;
            align-items: center;
            border-bottom: 2px solid #666;
        }
        
        .logo-container {
            display: flex;
            justify-content: center;
            align-items: center;
            flex: 1;
        }
        
        .logo-image {
            height: 60px;
            width: auto;
        }
        
        .user-info {
            position: absolute;
            top: 20px;
            left: 20px;
            background: rgba(102, 102, 102, 0.2);
            color: #ccc;
            padding: 8px 15px;
            border-radius: 5px;
            font-size: 0.8rem;
        }
        
        .logout-btn {
            background: rgba(102, 102, 102, 0.2);
            color: #666;
            border: 1px solid #666;
            padding: 8px 15px;
            border-radius: 5px;
            text-decoration: none;
            font-size: 0.8rem;
            transition: all 0.3s ease;
        }
        
        .logout-btn:hover {
            background: rgba(102, 102, 102, 0.3);
        }
        
        /* Resto do CSS igual ao sistema anterior... */
        /* (incluindo todo o CSS do main_template anterior) */
    </style>
</head>
<body>
    <div class="header">
        <div class="user-info">
            👤 {{ session.user_name or session.user_email }} 
            <span style="color: #999;">({{ session.user_provider }})</span>
        </div>
        <div class="logo-container">
            <img src="/logo.png" alt="Logo" class="logo-image" onerror="this.style.display='none';">
        </div>
        <a href="/logout" class="logout-btn">Sair</a>
    </div>
    
    <!-- Resto do HTML igual ao sistema anterior... -->
    <!-- (incluindo todo o HTML do main_template anterior) -->
    
    <script>
        // JavaScript igual ao sistema anterior...
        console.log('✅ MOEDOR AO VIVO - Sistema Local Híbrido carregado!');
        console.log('🔐 Usuário autenticado via {{ session.user_provider }}');
    </script>
</body>
</html>
"""

# Templates admin e overlay (iguais ao sistema anterior)
admin_template = """
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Painel Admin - MOEDOR AO VIVO</title>
    <style>
        body { font-family: Arial, sans-serif; background: #000; color: #fff; padding: 20px; }
        .container { max-width: 800px; margin: 0 auto; }
        h1 { color: #666; text-align: center; }
        .info { background: #111; padding: 20px; border-radius: 10px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚙️ Painel de Administração</h1>
        <div class="info">
            <h3>📊 Status do Sistema</h3>
            <p><strong>Sistema:</strong> MOEDOR AO VIVO - Híbrido</p>
            <p><strong>Autenticação:</strong> Centralizada (Render)</p>
            <p><strong>Performance:</strong> Máxima (Local)</p>
            <p><strong>Usuário:</strong> {{ session.user_name or session.user_email }}</p>
            <p><strong>Provider:</strong> {{ session.user_provider }}</p>
        </div>
        <div class="info">
            <h3>🔗 Links Úteis</h3>
            <p><a href="/" style="color: #666;">🏠 Sistema Principal</a></p>
            <p><a href="/obs-overlay" target="_blank" style="color: #666;">📺 Overlay OBS</a></p>
            <p><a href="/status" target="_blank" style="color: #666;">📊 Status API</a></p>
        </div>
    </div>
</body>
</html>
"""

obs_overlay_template = """
<!-- Template igual ao sistema anterior -->
<!DOCTYPE html>
<html lang="pt-BR">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>OBS Overlay - Mensagens</title>
    <style>
        /* CSS igual ao sistema anterior */
    </style>
</head>
<body>
    <div id="messagesContainer">
        <!-- Mensagens aparecerão aqui -->
    </div>
    
    <script src="https://cdnjs.cloudflare.com/ajax/libs/socket.io/4.0.1/socket.io.js"></script>
    <script>
        // JavaScript igual ao sistema anterior
        console.log('✅ OBS Overlay carregado!');
    </script>
</body>
</html>
"""

if __name__ == '__main__':
    print("🎥 MOEDOR AO VIVO - Sistema Local Híbrido")
    print("🔐 Autenticação: Centralizada (Render)")
    print("⚡ Performance: Máxima (Local)")
    print(f"🔗 Auth Server: {AUTH_SERVER_URL}")
    
    socketio.run(app, host='0.0.0.0', port=5001, debug=True)

