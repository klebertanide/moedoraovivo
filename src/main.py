import os
import sys
# DON'T CHANGE THIS !!!
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from flask import Flask, send_from_directory, request, session
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
from dotenv import load_dotenv
import logging
from datetime import datetime

# Carregar variáveis de ambiente
load_dotenv()

# Importar modelos e rotas
from src.models.database import db
from src.routes.auth import auth_bp
from src.routes.messages import messages_bp
from src.routes.admin import admin_bp
from src.routes.donations import donations_bp
from src.routes.cameras import cameras_bp
from src.routes.overlays import overlays_bp
from src.routes.polls import polls_bp

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Criar aplicação Flask
app = Flask(__name__, static_folder=os.path.join(os.path.dirname(__file__), 'static'))

# Configurações
app.config['SECRET_KEY'] = os.getenv('SECRET_KEY', 'moedor-ao-vivo-secret-key-2024')
app.config['SQLALCHEMY_DATABASE_URI'] = f"sqlite:///{os.path.join(os.path.dirname(__file__), 'database', 'app.db')}"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Configurar CORS
CORS(app, origins="*")

# Configurar SocketIO
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='eventlet')

# Registrar blueprints
app.register_blueprint(auth_bp, url_prefix='/api/auth')
app.register_blueprint(messages_bp, url_prefix='/api/messages')
app.register_blueprint(admin_bp, url_prefix='/api/admin')
app.register_blueprint(donations_bp, url_prefix='/api/donations')
app.register_blueprint(cameras_bp, url_prefix='/api/cameras')
app.register_blueprint(overlays_bp, url_prefix='/api/overlays')
app.register_blueprint(polls_bp, url_prefix='/api/polls')

# Inicializar banco de dados
db.init_app(app)
with app.app_context():
    db.create_all()
    logger.info("Banco de dados inicializado")

# Variáveis globais para controle da live
connected_users = {}
current_live_session = None
message_queue = []
overlay_queue = []

# Eventos WebSocket
@socketio.on('connect')
def handle_connect():
    """Usuário conectou"""
    user_id = session.get('user_id')
    if user_id:
        connected_users[request.sid] = user_id
        join_room('live_room')
        emit('connected', {'status': 'success', 'message': 'Conectado à live!'})
        
        # Enviar estatísticas atuais
        emit('stats_update', {
            'online_users': len(connected_users),
            'total_messages': len(message_queue)
        }, room='live_room')
        
        logger.info(f"Usuário {user_id} conectado - SID: {request.sid}")
    else:
        emit('error', {'message': 'Usuário não autenticado'})

@socketio.on('disconnect')
def handle_disconnect():
    """Usuário desconectou"""
    user_id = connected_users.pop(request.sid, None)
    if user_id:
        leave_room('live_room')
        
        # Atualizar estatísticas
        emit('stats_update', {
            'online_users': len(connected_users)
        }, room='live_room')
        
        logger.info(f"Usuário {user_id} desconectado - SID: {request.sid}")

@socketio.on('send_message')
def handle_message(data):
    """Receber mensagem do usuário"""
    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'message': 'Usuário não autenticado'})
        return
    
    fake_name = data.get('fake_name', '').strip()
    content = data.get('content', '').strip()
    
    # Validações
    if not fake_name or len(fake_name) > 50:
        emit('error', {'message': 'Nome inválido (máximo 50 caracteres)'})
        return
    
    if not content or len(content) > 250:
        emit('error', {'message': 'Mensagem inválida (máximo 250 caracteres)'})
        return
    
    # TODO: Implementar rate limiting
    
    # Salvar mensagem no banco
    from src.models.database import Message
    message = Message(
        user_id=user_id,
        fake_name=fake_name,
        content=content
    )
    
    try:
        db.session.add(message)
        db.session.commit()
        
        # Adicionar à fila de mensagens
        message_data = {
            'id': message.id,
            'fake_name': fake_name,
            'content': content,
            'likes': 0,
            'timestamp': datetime.utcnow().isoformat()
        }
        message_queue.append(message_data)
        
        # Notificar todos os usuários
        emit('new_message', message_data, room='live_room')
        
        # Notificar overlay (se configurado)
        emit('overlay_message', message_data, room='overlay_room')
        
        logger.info(f"Nova mensagem de {fake_name}: {content}")
        
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao salvar mensagem: {e}")
        emit('error', {'message': 'Erro ao enviar mensagem'})

@socketio.on('like_message')
def handle_like_message(data):
    """Curtir mensagem"""
    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'message': 'Usuário não autenticado'})
        return
    
    message_id = data.get('message_id')
    if not message_id:
        emit('error', {'message': 'ID da mensagem inválido'})
        return
    
    # TODO: Implementar sistema de likes no banco
    # Por enquanto, apenas emitir atualização
    emit('message_liked', {
        'message_id': message_id,
        'likes': 1  # Placeholder
    }, room='live_room')

@socketio.on('join_overlay')
def handle_join_overlay():
    """OBS conectou para receber overlays"""
    join_room('overlay_room')
    emit('overlay_connected', {'status': 'success'})
    logger.info("OBS conectado para overlays")

@socketio.on('vote_poll')
def handle_vote_poll(data):
    """Votar em enquete"""
    user_id = session.get('user_id')
    if not user_id:
        emit('error', {'message': 'Usuário não autenticado'})
        return
    
    poll_id = data.get('poll_id')
    option = data.get('option')  # 'A' ou 'B'
    
    if not poll_id or option not in ['A', 'B']:
        emit('error', {'message': 'Dados de votação inválidos'})
        return
    
    # TODO: Implementar votação no banco
    # Por enquanto, apenas emitir atualização
    emit('poll_vote_update', {
        'poll_id': poll_id,
        'option': option
    }, room='live_room')

# Rotas principais
@app.route('/', defaults={'path': ''})
@app.route('/<path:path>')
def serve(path):
    """Servir arquivos estáticos"""
    static_folder_path = app.static_folder
    if static_folder_path is None:
        return "Static folder not configured", 404

    if path != "" and os.path.exists(os.path.join(static_folder_path, path)):
        return send_from_directory(static_folder_path, path)
    else:
        index_path = os.path.join(static_folder_path, 'index.html')
        if os.path.exists(index_path):
            return send_from_directory(static_folder_path, 'index.html')
        else:
            return "index.html not found", 404

@app.route('/health')
def health_check():
    """Health check endpoint"""
    return {
        'status': 'ok',
        'timestamp': datetime.utcnow().isoformat(),
        'connected_users': len(connected_users),
        'message_queue_size': len(message_queue)
    }

# Funções utilitárias para outros módulos
def broadcast_to_overlay(event, data):
    """Enviar dados para overlay do OBS"""
    socketio.emit(event, data, room='overlay_room')

def broadcast_to_users(event, data):
    """Enviar dados para todos os usuários"""
    socketio.emit(event, data, room='live_room')

def get_connected_users_count():
    """Obter número de usuários conectados"""
    return len(connected_users)

if __name__ == '__main__':
    logger.info("Iniciando MOEDOR AO VIVO...")
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)

