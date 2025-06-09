from flask import Blueprint, request, jsonify, session
from src.models.database import db, User, LiveSession
import requests
import logging
import hashlib
import hmac
import json
from datetime import datetime
import os

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__)

# Configurações do Hotmart
HOTMART_HOTTOK = os.getenv('HOTMART_WEBHOOK_SECRET', 'your_hottok_here')
HOTMART_CLIENT_ID = os.getenv('HOTMART_CLIENT_ID', 'your_client_id')
HOTMART_CLIENT_SECRET = os.getenv('HOTMART_CLIENT_SECRET', 'your_client_secret')

def verify_hotmart_signature(request_data, signature):
    """Verificar assinatura do webhook Hotmart usando hottok"""
    try:
        # O hottok é enviado no header X-HOTMART-HOTTOK
        hottok = request.headers.get('X-HOTMART-HOTTOK')
        
        if not hottok or hottok != HOTMART_HOTTOK:
            logger.warning(f"Hottok inválido recebido: {hottok}")
            return False
            
        return True
        
    except Exception as e:
        logger.error(f"Erro ao verificar assinatura Hotmart: {e}")
        return False

@auth_bp.route('/webhook/hotmart', methods=['POST'])
def hotmart_webhook():
    """Webhook para receber notificações do Hotmart"""
    try:
        # Verificar Content-Type
        if request.content_type != 'application/json':
            logger.warning(f"Content-Type inválido: {request.content_type}")
            return jsonify({'error': 'Invalid content type'}), 400
        
        # Obter dados do webhook
        data = request.get_json()
        if not data:
            logger.warning("Dados JSON inválidos recebidos")
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        # Verificar assinatura/hottok
        if not verify_hotmart_signature(data, request.headers.get('X-HOTMART-HOTTOK')):
            logger.warning("Assinatura Hotmart inválida")
            return jsonify({'error': 'Invalid signature'}), 401
        
        # Processar evento
        event_type = data.get('event')
        logger.info(f"Evento Hotmart recebido: {event_type}")
        
        if event_type == 'PURCHASE_APPROVED':
            handle_purchase_approved(data)
        elif event_type == 'PURCHASE_CANCELED':
            handle_purchase_canceled(data)
        elif event_type == 'PURCHASE_DELAYED':
            handle_purchase_delayed(data)
        else:
            logger.info(f"Evento não processado: {event_type}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Erro no webhook Hotmart: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def handle_purchase_approved(data):
    """Processar compra aprovada - novo assinante"""
    try:
        # Extrair dados do comprador
        buyer = data.get('buyer', {})
        subscription = data.get('subscription', {})
        purchase = data.get('purchase', {})
        
        email = buyer.get('email')
        name = buyer.get('name', 'Usuário')
        hotmart_id = subscription.get('subscriber', {}).get('code') or purchase.get('transaction')
        
        if not email or not hotmart_id:
            logger.warning("Dados insuficientes no webhook de compra aprovada")
            return
        
        # Verificar se usuário já existe
        existing_user = User.query.filter_by(email=email).first()
        
        if existing_user:
            # Atualizar usuário existente
            existing_user.is_active = True
            existing_user.last_login = datetime.utcnow()
            existing_user.hotmart_id = hotmart_id
            logger.info(f"Usuário reativado: {email}")
        else:
            # Criar novo usuário
            new_user = User(
                hotmart_id=hotmart_id,
                name=name,
                email=email,
                is_active=True
            )
            db.session.add(new_user)
            logger.info(f"Novo usuário criado: {email}")
        
        db.session.commit()
        
        # Notificar sistema sobre novo assinante
        from src.main import broadcast_to_overlay, broadcast_to_users
        
        # Enviar para overlay (boas-vindas com berinjelas)
        broadcast_to_overlay('new_subscriber', {
            'name': name,
            'email': email,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        # Atualizar estatísticas para usuários
        broadcast_to_users('stats_update', {
            'new_subscriber': True,
            'subscriber_name': name
        })
        
    except Exception as e:
        logger.error(f"Erro ao processar compra aprovada: {e}")
        db.session.rollback()

def handle_purchase_canceled(data):
    """Processar cancelamento de compra"""
    try:
        buyer = data.get('buyer', {})
        email = buyer.get('email')
        
        if email:
            user = User.query.filter_by(email=email).first()
            if user:
                user.is_active = False
                db.session.commit()
                logger.info(f"Usuário desativado por cancelamento: {email}")
        
    except Exception as e:
        logger.error(f"Erro ao processar cancelamento: {e}")
        db.session.rollback()

def handle_purchase_delayed(data):
    """Processar pagamento atrasado"""
    try:
        buyer = data.get('buyer', {})
        email = buyer.get('email')
        
        if email:
            user = User.query.filter_by(email=email).first()
            if user:
                # Por enquanto, apenas log. Futuramente pode implementar notificações
                logger.info(f"Pagamento atrasado para usuário: {email}")
        
    except Exception as e:
        logger.error(f"Erro ao processar pagamento atrasado: {e}")

@auth_bp.route('/login', methods=['POST'])
def login():
    """Login do usuário"""
    try:
        data = request.get_json()
        email = data.get('email', '').strip().lower()
        
        if not email:
            return jsonify({'error': 'Email é obrigatório'}), 400
        
        # Buscar usuário no banco
        user = User.query.filter_by(email=email).first()
        
        if not user:
            return jsonify({'error': 'Usuário não encontrado. Você precisa ser assinante do Hotmart.'}), 401
        
        if not user.is_active:
            return jsonify({'error': 'Sua assinatura está inativa. Verifique seu pagamento no Hotmart.'}), 401
        
        # Atualizar último login
        user.last_login = datetime.utcnow()
        db.session.commit()
        
        # Criar sessão
        session['user_id'] = user.id
        session['user_name'] = user.name
        session['user_email'] = user.email
        
        logger.info(f"Login realizado: {email}")
        
        return jsonify({
            'status': 'success',
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'created_at': user.created_at.isoformat()
            }
        })
        
    except Exception as e:
        logger.error(f"Erro no login: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@auth_bp.route('/logout', methods=['POST'])
def logout():
    """Logout do usuário"""
    user_email = session.get('user_email')
    session.clear()
    
    if user_email:
        logger.info(f"Logout realizado: {user_email}")
    
    return jsonify({'status': 'success'})

@auth_bp.route('/status')
def auth_status():
    """Verificar status de autenticação"""
    user_id = session.get('user_id')
    
    if not user_id:
        return jsonify({'authenticated': False})
    
    try:
        user = User.query.get(user_id)
        
        if not user or not user.is_active:
            session.clear()
            return jsonify({'authenticated': False})
        
        return jsonify({
            'authenticated': True,
            'user': {
                'id': user.id,
                'name': user.name,
                'email': user.email,
                'created_at': user.created_at.isoformat(),
                'last_login': user.last_login.isoformat() if user.last_login else None
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao verificar status de autenticação: {e}")
        session.clear()
        return jsonify({'authenticated': False})

@auth_bp.route('/validate-subscription', methods=['POST'])
def validate_subscription():
    """Validar assinatura diretamente com API Hotmart (opcional)"""
    try:
        data = request.get_json()
        email = data.get('email')
        
        if not email:
            return jsonify({'error': 'Email é obrigatório'}), 400
        
        # TODO: Implementar validação via API Hotmart se necessário
        # Por enquanto, usar apenas dados do webhook
        
        user = User.query.filter_by(email=email).first()
        
        if user and user.is_active:
            return jsonify({
                'valid': True,
                'user': {
                    'name': user.name,
                    'email': user.email
                }
            })
        else:
            return jsonify({'valid': False})
        
    except Exception as e:
        logger.error(f"Erro ao validar assinatura: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@auth_bp.route('/webhook/test', methods=['POST'])
def test_webhook():
    """Endpoint para testar webhook (apenas desenvolvimento)"""
    if os.getenv('FLASK_ENV') != 'development':
        return jsonify({'error': 'Endpoint disponível apenas em desenvolvimento'}), 403
    
    try:
        # Simular evento de compra aprovada
        test_data = {
            'event': 'PURCHASE_APPROVED',
            'buyer': {
                'email': 'teste@moedor.com',
                'name': 'Usuário Teste'
            },
            'subscription': {
                'subscriber': {
                    'code': 'test_subscriber_123'
                }
            },
            'purchase': {
                'transaction': 'test_transaction_123'
            }
        }
        
        handle_purchase_approved(test_data)
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook de teste processado com sucesso'
        })
        
    except Exception as e:
        logger.error(f"Erro no webhook de teste: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

