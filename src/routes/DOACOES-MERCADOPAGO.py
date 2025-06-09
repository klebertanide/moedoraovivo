from flask import Blueprint, request, jsonify, session
from src.models.database import db, Donation, User, LiveSession
import mercadopago
import logging
import hashlib
import hmac
import json
import os
from datetime import datetime

logger = logging.getLogger(__name__)

donations_bp = Blueprint('donations', __name__)

# Configurações do Mercado Pago
MP_ACCESS_TOKEN = os.getenv('MERCADOPAGO_ACCESS_TOKEN', 'your_access_token')
MP_PUBLIC_KEY = os.getenv('MERCADOPAGO_PUBLIC_KEY', 'your_public_key')
MP_WEBHOOK_SECRET = os.getenv('MERCADOPAGO_WEBHOOK_SECRET', 'your_webhook_secret')

# Inicializar SDK do Mercado Pago
sdk = mercadopago.SDK(MP_ACCESS_TOKEN)

def verify_mercadopago_signature(request_data, signature_header):
    """Verificar assinatura do webhook Mercado Pago"""
    try:
        if not signature_header:
            return False
        
        # Extrair timestamp e signature do header
        # Formato: ts=1704908010,v1=618c85345248dd820d5fd456117c2ab2ef8eda45a0282ff693eac24131a5e839
        parts = signature_header.split(',')
        ts = None
        signature = None
        
        for part in parts:
            if part.startswith('ts='):
                ts = part[3:]
            elif part.startswith('v1='):
                signature = part[3:]
        
        if not ts or not signature:
            return False
        
        # Criar string para verificação
        data_string = f"id={request_data.get('data', {}).get('id')};request-id={request.headers.get('x-request-id', '')};ts={ts};"
        
        # Calcular HMAC
        expected_signature = hmac.new(
            MP_WEBHOOK_SECRET.encode('utf-8'),
            data_string.encode('utf-8'),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(signature, expected_signature)
        
    except Exception as e:
        logger.error(f"Erro ao verificar assinatura Mercado Pago: {e}")
        return False

@donations_bp.route('/create', methods=['POST'])
def create_donation():
    """Criar doação livre"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Usuário não autenticado'}), 401
    
    try:
        data = request.get_json()
        amount = float(data.get('amount', 0))
        description = data.get('description', 'Doação para MOEDOR AO VIVO')
        
        if amount <= 0:
            return jsonify({'error': 'Valor deve ser maior que zero'}), 400
        
        if amount > 1000:  # Limite de R$ 1000
            return jsonify({'error': 'Valor máximo é R$ 1000,00'}), 400
        
        # Buscar dados do usuário
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        
        # Criar preferência no Mercado Pago
        preference_data = {
            "items": [
                {
                    "title": description,
                    "quantity": 1,
                    "unit_price": amount,
                    "currency_id": "BRL"
                }
            ],
            "payer": {
                "name": user.name,
                "email": user.email
            },
            "back_urls": {
                "success": f"{request.host_url}donation/success",
                "failure": f"{request.host_url}donation/failure",
                "pending": f"{request.host_url}donation/pending"
            },
            "auto_return": "approved",
            "notification_url": f"{request.host_url}api/donations/webhook/mercadopago",
            "external_reference": f"donation_{user_id}_{int(datetime.utcnow().timestamp())}",
            "metadata": {
                "user_id": user_id,
                "donation_type": "free"
            }
        }
        
        preference_response = sdk.preference().create(preference_data)
        
        if preference_response["status"] != 201:
            logger.error(f"Erro ao criar preferência MP: {preference_response}")
            return jsonify({'error': 'Erro ao processar pagamento'}), 500
        
        preference = preference_response["response"]
        
        # Salvar doação no banco
        donation = Donation(
            user_id=user_id,
            amount=amount,
            payment_id=preference["id"],
            status='pending',
            donation_type='free'
        )
        db.session.add(donation)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'payment_url': preference["init_point"],
            'payment_id': preference["id"],
            'amount': amount
        })
        
    except ValueError:
        return jsonify({'error': 'Valor inválido'}), 400
    except Exception as e:
        logger.error(f"Erro ao criar doação: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

@donations_bp.route('/embarrassing', methods=['POST'])
def create_embarrassing_donation():
    """Criar doação para vergonha alheia (R$ 20,00)"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Usuário não autenticado'}), 401
    
    try:
        # Verificar se já atingiu o limite de 3 vergonhas por live
        current_session = LiveSession.query.filter_by(is_active=True).first()
        if current_session and current_session.embarrassing_count >= 3:
            return jsonify({
                'error': 'Limite de vergonhas atingido para esta live (máximo 3)'
            }), 400
        
        # Buscar dados do usuário
        user = User.query.get(user_id)
        if not user:
            return jsonify({'error': 'Usuário não encontrado'}), 404
        
        amount = 20.00  # Valor fixo para vergonha alheia
        
        # Criar preferência no Mercado Pago
        preference_data = {
            "items": [
                {
                    "title": "ENVERGONHAR UM DOS INTEGRANTES - MOEDOR AO VIVO",
                    "description": "Os apresentadores ouvirão verdades realmente constrangedoras",
                    "quantity": 1,
                    "unit_price": amount,
                    "currency_id": "BRL"
                }
            ],
            "payer": {
                "name": user.name,
                "email": user.email
            },
            "back_urls": {
                "success": f"{request.host_url}donation/success",
                "failure": f"{request.host_url}donation/failure",
                "pending": f"{request.host_url}donation/pending"
            },
            "auto_return": "approved",
            "notification_url": f"{request.host_url}api/donations/webhook/mercadopago",
            "external_reference": f"embarrassing_{user_id}_{int(datetime.utcnow().timestamp())}",
            "metadata": {
                "user_id": user_id,
                "donation_type": "embarrassing"
            }
        }
        
        preference_response = sdk.preference().create(preference_data)
        
        if preference_response["status"] != 201:
            logger.error(f"Erro ao criar preferência MP: {preference_response}")
            return jsonify({'error': 'Erro ao processar pagamento'}), 500
        
        preference = preference_response["response"]
        
        # Salvar doação no banco
        donation = Donation(
            user_id=user_id,
            amount=amount,
            payment_id=preference["id"],
            status='pending',
            donation_type='embarrassing'
        )
        db.session.add(donation)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'payment_url': preference["init_point"],
            'payment_id': preference["id"],
            'amount': amount,
            'type': 'embarrassing'
        })
        
    except Exception as e:
        logger.error(f"Erro ao criar doação de vergonha: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

@donations_bp.route('/webhook/mercadopago', methods=['POST'])
def mercadopago_webhook():
    """Webhook para receber notificações do Mercado Pago"""
    try:
        # Verificar Content-Type
        if request.content_type != 'application/json':
            logger.warning(f"Content-Type inválido: {request.content_type}")
            return jsonify({'error': 'Invalid content type'}), 400
        
        data = request.get_json()
        if not data:
            logger.warning("Dados JSON inválidos recebidos")
            return jsonify({'error': 'Invalid JSON data'}), 400
        
        # Verificar assinatura (em produção)
        if os.getenv('FLASK_ENV') == 'production':
            signature = request.headers.get('x-signature')
            if not verify_mercadopago_signature(data, signature):
                logger.warning("Assinatura Mercado Pago inválida")
                return jsonify({'error': 'Invalid signature'}), 401
        
        # Processar notificação
        topic = data.get('type')
        resource_id = data.get('data', {}).get('id')
        
        logger.info(f"Webhook MP recebido - Topic: {topic}, ID: {resource_id}")
        
        if topic == 'payment':
            handle_payment_notification(resource_id)
        else:
            logger.info(f"Tópico não processado: {topic}")
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Erro no webhook Mercado Pago: {e}")
        return jsonify({'error': 'Internal server error'}), 500

def handle_payment_notification(payment_id):
    """Processar notificação de pagamento"""
    try:
        # Buscar informações do pagamento no Mercado Pago
        payment_response = sdk.payment().get(payment_id)
        
        if payment_response["status"] != 200:
            logger.error(f"Erro ao buscar pagamento {payment_id}: {payment_response}")
            return
        
        payment_data = payment_response["response"]
        external_reference = payment_data.get("external_reference")
        status = payment_data.get("status")
        
        if not external_reference:
            logger.warning(f"Pagamento sem external_reference: {payment_id}")
            return
        
        # Buscar doação no banco
        donation = Donation.query.filter_by(payment_id=payment_id).first()
        if not donation:
            logger.warning(f"Doação não encontrada para payment_id: {payment_id}")
            return
        
        # Atualizar status da doação
        old_status = donation.status
        donation.status = status
        donation.processed_at = datetime.utcnow()
        
        if status == 'approved' and old_status != 'approved':
            # Pagamento aprovado
            logger.info(f"Pagamento aprovado: {payment_id} - Valor: R$ {donation.amount}")
            
            # Notificar sistema
            from src.main import broadcast_to_overlay, broadcast_to_users
            
            if donation.donation_type == 'embarrassing':
                # Processar vergonha alheia
                handle_embarrassing_approved(donation)
            else:
                # Doação livre - mostrar aviãozinho
                broadcast_to_overlay('donation_approved', {
                    'amount': donation.amount,
                    'user_name': donation.user.name,
                    'type': 'free',
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            # Atualizar estatísticas
            broadcast_to_users('stats_update', {
                'new_donation': True,
                'amount': donation.amount,
                'type': donation.donation_type
            })
        
        elif status in ['cancelled', 'rejected']:
            logger.info(f"Pagamento cancelado/rejeitado: {payment_id}")
        
        db.session.commit()
        
    except Exception as e:
        logger.error(f"Erro ao processar notificação de pagamento: {e}")
        db.session.rollback()

def handle_embarrassing_approved(donation):
    """Processar vergonha alheia aprovada"""
    try:
        # Incrementar contador da live
        current_session = LiveSession.query.filter_by(is_active=True).first()
        if current_session:
            current_session.embarrassing_count += 1
            db.session.commit()
        
        # Adicionar à fila de vergonhas
        from src.main import broadcast_to_overlay
        
        broadcast_to_overlay('embarrassing_approved', {
            'user_name': donation.user.name,
            'amount': donation.amount,
            'timestamp': datetime.utcnow().isoformat()
        })
        
        logger.info(f"Vergonha alheia aprovada para {donation.user.name}")
        
    except Exception as e:
        logger.error(f"Erro ao processar vergonha aprovada: {e}")

@donations_bp.route('/stats', methods=['GET'])
def get_donation_stats():
    """Obter estatísticas de doações"""
    try:
        # Estatísticas gerais
        total_donations = Donation.query.filter_by(status='approved').count()
        total_amount = db.session.query(db.func.sum(Donation.amount)).filter_by(status='approved').scalar() or 0
        
        # Doações por tipo
        free_donations = Donation.query.filter_by(status='approved', donation_type='free').count()
        embarrassing_donations = Donation.query.filter_by(status='approved', donation_type='embarrassing').count()
        
        # Estatísticas da live atual
        current_session = LiveSession.query.filter_by(is_active=True).first()
        session_stats = {
            'embarrassing_count': 0,
            'total_donations': 0,
            'session_amount': 0
        }
        
        if current_session:
            session_stats['embarrassing_count'] = current_session.embarrassing_count
            session_stats['total_donations'] = current_session.total_donations
            session_stats['session_amount'] = current_session.total_donations
        
        return jsonify({
            'total_donations': total_donations,
            'total_amount': float(total_amount),
            'free_donations': free_donations,
            'embarrassing_donations': embarrassing_donations,
            'current_session': session_stats,
            'embarrassing_limit': 3,
            'embarrassing_remaining': max(0, 3 - session_stats['embarrassing_count'])
        })
        
    except Exception as e:
        logger.error(f"Erro ao buscar estatísticas de doações: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@donations_bp.route('/history', methods=['GET'])
def get_donation_history():
    """Obter histórico de doações do usuário"""
    user_id = session.get('user_id')
    if not user_id:
        return jsonify({'error': 'Usuário não autenticado'}), 401
    
    try:
        donations = Donation.query.filter_by(user_id=user_id).order_by(
            Donation.created_at.desc()
        ).limit(20).all()
        
        history = []
        for donation in donations:
            history.append({
                'id': donation.id,
                'amount': donation.amount,
                'status': donation.status,
                'type': donation.donation_type,
                'created_at': donation.created_at.isoformat(),
                'processed_at': donation.processed_at.isoformat() if donation.processed_at else None
            })
        
        return jsonify({'history': history})
        
    except Exception as e:
        logger.error(f"Erro ao buscar histórico de doações: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@donations_bp.route('/test-webhook', methods=['POST'])
def test_webhook():
    """Endpoint para testar webhook (apenas desenvolvimento)"""
    if os.getenv('FLASK_ENV') != 'development':
        return jsonify({'error': 'Endpoint disponível apenas em desenvolvimento'}), 403
    
    try:
        # Simular notificação de pagamento aprovado
        test_data = {
            'type': 'payment',
            'data': {
                'id': 'test_payment_123'
            }
        }
        
        # Criar doação de teste
        user = User.query.first()
        if user:
            test_donation = Donation(
                user_id=user.id,
                amount=20.00,
                payment_id='test_payment_123',
                status='pending',
                donation_type='embarrassing'
            )
            db.session.add(test_donation)
            db.session.commit()
            
            # Simular aprovação
            test_donation.status = 'approved'
            test_donation.processed_at = datetime.utcnow()
            db.session.commit()
            
            handle_embarrassing_approved(test_donation)
        
        return jsonify({
            'status': 'success',
            'message': 'Webhook de teste processado com sucesso'
        })
        
    except Exception as e:
        logger.error(f"Erro no webhook de teste: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

