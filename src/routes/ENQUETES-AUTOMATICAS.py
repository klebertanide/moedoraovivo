from flask import Blueprint, request, jsonify, session
from src.services.poll_service import poll_service
import logging

logger = logging.getLogger(__name__)

polls_bp = Blueprint('polls', __name__)

@polls_bp.route('/', methods=['GET'])
def get_polls():
    """Obter enquetes ativas"""
    try:
        active_polls = poll_service.get_active_polls()
        return jsonify({'polls': active_polls})
        
    except Exception as e:
        logger.error(f"Erro ao buscar enquetes: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@polls_bp.route('/<int:poll_id>/vote', methods=['POST'])
def vote_poll(poll_id):
    """Votar em enquete"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Usuário não autenticado'}), 401
    
    try:
        data = request.get_json()
        option_id = data.get('option_id')
        
        if not option_id:
            return jsonify({'error': 'ID da opção é obrigatório'}), 400
        
        result = poll_service.vote_on_poll(poll_id, option_id, user_id)
        
        if 'error' in result:
            return jsonify(result), 400
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Erro ao votar: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@polls_bp.route('/<int:poll_id>/results', methods=['GET'])
def get_poll_results(poll_id):
    """Obter resultados de enquete"""
    try:
        results = poll_service.get_poll_results(poll_id)
        
        if results is None:
            return jsonify({'error': 'Enquete não encontrada'}), 404
        
        return jsonify({'results': results})
        
    except Exception as e:
        logger.error(f"Erro ao buscar resultados: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@polls_bp.route('/create', methods=['POST'])
def create_poll():
    """Criar enquete manual (apenas admin)"""
    # TODO: Verificar se usuário é admin
    
    try:
        data = request.get_json()
        
        question = data.get('question', '').strip()
        options = data.get('options', [])
        duration = data.get('duration_minutes', 10)
        
        if not question:
            return jsonify({'error': 'Pergunta é obrigatória'}), 400
        
        if len(options) < 2:
            return jsonify({'error': 'Pelo menos 2 opções são necessárias'}), 400
        
        if len(options) > 6:
            return jsonify({'error': 'Máximo 6 opções permitidas'}), 400
        
        # Validar duração
        if duration < 1 or duration > 60:
            return jsonify({'error': 'Duração deve ser entre 1 e 60 minutos'}), 400
        
        poll_data = poll_service.create_manual_poll(question, options, duration)
        
        if poll_data:
            # Notificar usuários sobre nova enquete
            from src.main import broadcast_to_users
            
            broadcast_to_users('new_poll', {
                'poll_id': poll_data['id'],
                'question': poll_data['question'],
                'options': poll_data['options'],
                'duration_minutes': duration,
                'timestamp': poll_data['expires_at']
            })
            
            return jsonify(poll_data)
        else:
            return jsonify({'error': 'Erro ao criar enquete'}), 500
        
    except Exception as e:
        logger.error(f"Erro ao criar enquete: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@polls_bp.route('/stats', methods=['GET'])
def get_stats():
    """Obter estatísticas das enquetes"""
    try:
        stats = poll_service.get_poll_stats()
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

