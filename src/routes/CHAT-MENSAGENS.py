from flask import Blueprint, request, jsonify, session
from src.models.database import db, Message, MessageLike, User
from datetime import datetime, timedelta
import logging
import json

logger = logging.getLogger(__name__)

messages_bp = Blueprint('messages', __name__)

# Rate limiting em memória (em produção, usar Redis)
user_message_timestamps = {}
user_like_timestamps = {}

def check_rate_limit(user_id, action='message', limit_per_minute=1):
    """Verificar rate limiting para ações do usuário"""
    now = datetime.utcnow()
    
    if action == 'message':
        timestamps = user_message_timestamps.get(user_id, [])
    else:  # likes
        timestamps = user_like_timestamps.get(user_id, [])
    
    # Remover timestamps antigos (mais de 1 minuto)
    recent_timestamps = [ts for ts in timestamps if now - ts < timedelta(minutes=1)]
    
    # Verificar se excedeu o limite
    if len(recent_timestamps) >= limit_per_minute:
        return False, recent_timestamps
    
    # Adicionar timestamp atual
    recent_timestamps.append(now)
    
    # Atualizar cache
    if action == 'message':
        user_message_timestamps[user_id] = recent_timestamps
    else:
        user_like_timestamps[user_id] = recent_timestamps
    
    return True, recent_timestamps

@messages_bp.route('/', methods=['GET'])
def get_messages():
    """Listar mensagens recentes"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        
        # Limitar per_page
        per_page = min(per_page, 50)
        
        # Buscar mensagens ordenadas por likes e data
        messages = Message.query.order_by(
            Message.likes_count.desc(),
            Message.created_at.desc()
        ).paginate(
            page=page,
            per_page=per_page,
            error_out=False
        )
        
        messages_data = []
        for message in messages.items:
            messages_data.append({
                'id': message.id,
                'fake_name': message.fake_name,
                'content': message.content,
                'likes_count': message.likes_count,
                'created_at': message.created_at.isoformat(),
                'displayed_at': message.displayed_at.isoformat() if message.displayed_at else None,
                'is_displayed': message.is_displayed
            })
        
        return jsonify({
            'messages': messages_data,
            'pagination': {
                'page': page,
                'per_page': per_page,
                'total': messages.total,
                'pages': messages.pages,
                'has_next': messages.has_next,
                'has_prev': messages.has_prev
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar mensagens: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@messages_bp.route('/<int:message_id>/like', methods=['POST'])
def like_message(message_id):
    """Curtir/descurtir mensagem"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Usuário não autenticado'}), 401
    
    try:
        # Verificar rate limiting
        allowed, timestamps = check_rate_limit(user_id, 'like', limit_per_minute=10)
        if not allowed:
            return jsonify({
                'error': 'Muitos likes em pouco tempo. Aguarde um momento.',
                'retry_after': 60
            }), 429
        
        # Verificar se mensagem existe
        message = Message.query.get(message_id)
        if not message:
            return jsonify({'error': 'Mensagem não encontrada'}), 404
        
        # Verificar se usuário já curtiu
        existing_like = MessageLike.query.filter_by(
            message_id=message_id,
            user_id=user_id
        ).first()
        
        if existing_like:
            # Remover like (descurtir)
            db.session.delete(existing_like)
            message.likes_count = max(0, message.likes_count - 1)
            action = 'unliked'
        else:
            # Adicionar like
            new_like = MessageLike(
                message_id=message_id,
                user_id=user_id
            )
            db.session.add(new_like)
            message.likes_count += 1
            action = 'liked'
        
        db.session.commit()
        
        # Notificar via WebSocket
        from src.main import broadcast_to_users
        broadcast_to_users('message_liked', {
            'message_id': message_id,
            'likes_count': message.likes_count,
            'action': action
        })
        
        return jsonify({
            'status': 'success',
            'action': action,
            'likes_count': message.likes_count
        })
        
    except Exception as e:
        logger.error(f"Erro ao curtir mensagem: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

@messages_bp.route('/top', methods=['GET'])
def get_top_message():
    """Obter mensagem com mais likes (para exibir no OBS)"""
    try:
        # Buscar mensagem com mais likes que ainda não foi exibida
        top_message = Message.query.filter_by(is_displayed=False).order_by(
            Message.likes_count.desc(),
            Message.created_at.desc()
        ).first()
        
        if not top_message:
            return jsonify({'message': None})
        
        return jsonify({
            'message': {
                'id': top_message.id,
                'fake_name': top_message.fake_name,
                'content': top_message.content,
                'likes_count': top_message.likes_count,
                'created_at': top_message.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar mensagem top: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@messages_bp.route('/<int:message_id>/mark-displayed', methods=['POST'])
def mark_message_displayed(message_id):
    """Marcar mensagem como exibida (para admin/OBS)"""
    try:
        message = Message.query.get(message_id)
        if not message:
            return jsonify({'error': 'Mensagem não encontrada'}), 404
        
        message.is_displayed = True
        message.displayed_at = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Erro ao marcar mensagem como exibida: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

@messages_bp.route('/stats', methods=['GET'])
def get_message_stats():
    """Obter estatísticas de mensagens"""
    try:
        total_messages = Message.query.count()
        displayed_messages = Message.query.filter_by(is_displayed=True).count()
        pending_messages = total_messages - displayed_messages
        
        # Mensagens por hora (últimas 24h)
        last_24h = datetime.utcnow() - timedelta(hours=24)
        recent_messages = Message.query.filter(
            Message.created_at >= last_24h
        ).count()
        
        # Top 5 mensagens por likes
        top_messages = Message.query.order_by(
            Message.likes_count.desc()
        ).limit(5).all()
        
        top_messages_data = []
        for msg in top_messages:
            top_messages_data.append({
                'id': msg.id,
                'fake_name': msg.fake_name,
                'content': msg.content[:100] + '...' if len(msg.content) > 100 else msg.content,
                'likes_count': msg.likes_count
            })
        
        return jsonify({
            'total_messages': total_messages,
            'displayed_messages': displayed_messages,
            'pending_messages': pending_messages,
            'recent_messages_24h': recent_messages,
            'top_messages': top_messages_data
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@messages_bp.route('/validate', methods=['POST'])
def validate_message():
    """Validar mensagem antes do envio"""
    try:
        data = request.get_json()
        fake_name = data.get('fake_name', '').strip()
        content = data.get('content', '').strip()
        
        errors = []
        
        # Validar nome falso
        if not fake_name:
            errors.append('Nome é obrigatório')
        elif len(fake_name) > 50:
            errors.append('Nome deve ter no máximo 50 caracteres')
        elif len(fake_name) < 2:
            errors.append('Nome deve ter pelo menos 2 caracteres')
        
        # Validar conteúdo
        if not content:
            errors.append('Mensagem é obrigatória')
        elif len(content) > 250:
            errors.append('Mensagem deve ter no máximo 250 caracteres')
        elif len(content) < 3:
            errors.append('Mensagem deve ter pelo menos 3 caracteres')
        
        # Verificar palavras proibidas (básico)
        forbidden_words = ['spam', 'hack', 'bot']
        content_lower = content.lower()
        for word in forbidden_words:
            if word in content_lower:
                errors.append(f'Palavra não permitida: {word}')
        
        if errors:
            return jsonify({
                'valid': False,
                'errors': errors
            }), 400
        
        return jsonify({
            'valid': True,
            'message': 'Mensagem válida'
        })
        
    except Exception as e:
        logger.error(f"Erro ao validar mensagem: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@messages_bp.route('/queue', methods=['GET'])
def get_message_queue():
    """Obter fila de mensagens para exibição no OBS"""
    try:
        # Buscar mensagens não exibidas ordenadas por likes
        queue_messages = Message.query.filter_by(is_displayed=False).order_by(
            Message.likes_count.desc(),
            Message.created_at.asc()
        ).limit(10).all()
        
        queue_data = []
        for msg in queue_messages:
            queue_data.append({
                'id': msg.id,
                'fake_name': msg.fake_name,
                'content': msg.content,
                'likes_count': msg.likes_count,
                'created_at': msg.created_at.isoformat(),
                'priority': msg.likes_count  # Prioridade baseada em likes
            })
        
        return jsonify({
            'queue': queue_data,
            'total_in_queue': len(queue_data)
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar fila de mensagens: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@messages_bp.route('/cleanup', methods=['POST'])
def cleanup_old_messages():
    """Limpar mensagens antigas (para admin)"""
    try:
        # Remover mensagens com mais de 7 dias e 0 likes
        cutoff_date = datetime.utcnow() - timedelta(days=7)
        
        old_messages = Message.query.filter(
            Message.created_at < cutoff_date,
            Message.likes_count == 0
        ).all()
        
        count = len(old_messages)
        
        for msg in old_messages:
            # Remover likes associados
            MessageLike.query.filter_by(message_id=msg.id).delete()
            db.session.delete(msg)
        
        db.session.commit()
        
        logger.info(f"Limpeza realizada: {count} mensagens removidas")
        
        return jsonify({
            'status': 'success',
            'messages_removed': count
        })
        
    except Exception as e:
        logger.error(f"Erro na limpeza de mensagens: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

