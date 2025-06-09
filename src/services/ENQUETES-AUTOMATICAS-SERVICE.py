import random
import logging
from datetime import datetime, timedelta
from threading import Timer
import json
import re

logger = logging.getLogger(__name__)

class PollGenerationService:
    """Serviço para geração automática de enquetes"""
    
    def __init__(self):
        self.active_polls = {}
        self.poll_templates = {
            'momento_polemico': [
                "O que vocês acharam dessa declaração?",
                "Concordam com essa opinião?",
                "Essa foi uma boa resposta?",
                "Quem está certo nessa discussão?",
                "Qual a opinião de vocês sobre isso?"
            ],
            'discussao': [
                "Quem vocês apoiam nessa discussão?",
                "Qual lado tem razão?",
                "O que vocês fariam nessa situação?",
                "Concordam com essa atitude?",
                "Quem está sendo mais sensato?"
            ],
            'confusao': [
                "Entenderam alguma coisa?",
                "Alguém consegue explicar isso?",
                "Que confusão foi essa?",
                "Vocês estão perdidos também?",
                "Conseguiram acompanhar?"
            ],
            'vergonha': [
                "Que vergonha alheia foi essa?",
                "Vocês sentiram o constrangimento?",
                "Alguém mais ficou com vergonha?",
                "Que situação embaraçosa!",
                "Deu para sentir o climão?"
            ]
        }
        
        self.option_templates = {
            'concordancia': ['Concordo totalmente', 'Concordo parcialmente', 'Discordo', 'Não tenho opinião'],
            'qualidade': ['Muito bom', 'Bom', 'Regular', 'Ruim', 'Péssimo'],
            'apoio': ['Apoio 100%', 'Apoio', 'Neutro', 'Não apoio', 'Sou contra'],
            'entendimento': ['Entendi tudo', 'Entendi mais ou menos', 'Não entendi nada', 'Estou confuso'],
            'vergonha': ['Muita vergonha', 'Vergonha moderada', 'Pouca vergonha', 'Sem vergonha'],
            'pessoas': ['Pessoa A', 'Pessoa B', 'Ambos', 'Nenhum dos dois'],
            'sim_nao': ['Sim', 'Não', 'Talvez', 'Não sei']
        }
    
    def generate_poll_from_content(self, content, context='momento_polemico', timestamp=None):
        """Gerar enquete baseada no conteúdo transcrito"""
        try:
            # Selecionar template de pergunta
            question_templates = self.poll_templates.get(context, self.poll_templates['momento_polemico'])
            question = random.choice(question_templates)
            
            # Determinar tipo de opções baseado no contexto e conteúdo
            option_type = self._determine_option_type(content, context)
            options = self.option_templates[option_type]
            
            # Personalizar pergunta se possível
            personalized_question = self._personalize_question(question, content)
            
            # Criar enquete
            poll_data = self._create_poll(
                question=personalized_question,
                options=options,
                context=context,
                source_content=content,
                timestamp=timestamp
            )
            
            if poll_data:
                # Iniciar timer de 10 minutos
                self._start_poll_timer(poll_data['id'])
                
                logger.info(f"Enquete gerada: {personalized_question}")
                return poll_data
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao gerar enquete: {e}")
            return None
    
    def _determine_option_type(self, content, context):
        """Determinar tipo de opções baseado no conteúdo"""
        content_lower = content.lower()
        
        # Detectar nomes de pessoas para enquetes de apoio
        if re.search(r'\b(joão|maria|pedro|ana|carlos|lucia)\b', content_lower):
            return 'pessoas'
        
        # Detectar perguntas sim/não
        if any(word in content_lower for word in ['sim', 'não', 'verdade', 'mentira']):
            return 'sim_nao'
        
        # Baseado no contexto
        context_mapping = {
            'momento_polemico': 'concordancia',
            'discussao': 'apoio',
            'confusao': 'entendimento',
            'vergonha': 'vergonha'
        }
        
        return context_mapping.get(context, 'concordancia')
    
    def _personalize_question(self, question, content):
        """Personalizar pergunta baseada no conteúdo"""
        try:
            # Extrair palavras-chave do conteúdo
            keywords = self._extract_keywords(content)
            
            # Substituir placeholders genéricos
            if 'essa declaração' in question and keywords:
                question = question.replace('essa declaração', f'"{keywords[0]}"')
            
            if 'essa opinião' in question and keywords:
                question = question.replace('essa opinião', f'a opinião sobre {keywords[0]}')
            
            return question
            
        except Exception as e:
            logger.error(f"Erro ao personalizar pergunta: {e}")
            return question
    
    def _extract_keywords(self, content):
        """Extrair palavras-chave do conteúdo"""
        try:
            # Palavras irrelevantes
            stop_words = {'o', 'a', 'os', 'as', 'um', 'uma', 'de', 'do', 'da', 'em', 'no', 'na', 'para', 'por', 'com', 'sem', 'que', 'é', 'são', 'foi', 'foram', 'ser', 'estar', 'ter', 'haver', 'isso', 'isto', 'aquilo', 'ele', 'ela', 'eles', 'elas', 'eu', 'tu', 'você', 'nós', 'vocês'}
            
            # Dividir em palavras e filtrar
            words = re.findall(r'\b\w+\b', content.lower())
            keywords = [word for word in words if len(word) > 3 and word not in stop_words]
            
            # Retornar as 3 palavras mais relevantes
            return keywords[:3]
            
        except Exception as e:
            logger.error(f"Erro ao extrair palavras-chave: {e}")
            return []
    
    def _create_poll(self, question, options, context, source_content, timestamp):
        """Criar enquete no banco de dados"""
        try:
            from src.models.database import db, Poll, PollOption
            
            # Criar enquete
            poll = Poll(
                question=question,
                context=context,
                source_content=source_content[:500],  # Limitar tamanho
                source_timestamp=timestamp,
                expires_at=datetime.utcnow() + timedelta(minutes=10)
            )
            
            db.session.add(poll)
            db.session.flush()  # Para obter o ID
            
            # Criar opções
            poll_options = []
            for i, option_text in enumerate(options):
                option = PollOption(
                    poll_id=poll.id,
                    text=option_text,
                    position=i
                )
                db.session.add(option)
                poll_options.append(option)
            
            db.session.commit()
            
            # Adicionar à lista de enquetes ativas
            self.active_polls[poll.id] = {
                'poll': poll,
                'options': poll_options,
                'votes': {opt.id: 0 for opt in poll_options},
                'total_votes': 0
            }
            
            return {
                'id': poll.id,
                'question': poll.question,
                'options': [{'id': opt.id, 'text': opt.text} for opt in poll_options],
                'expires_at': poll.expires_at.isoformat(),
                'context': poll.context
            }
            
        except Exception as e:
            logger.error(f"Erro ao criar enquete: {e}")
            if 'db' in locals():
                db.session.rollback()
            return None
    
    def _start_poll_timer(self, poll_id):
        """Iniciar timer para encerrar enquete"""
        try:
            timer = Timer(600, self._close_poll, args=[poll_id])  # 10 minutos
            timer.start()
            
            logger.info(f"Timer de 10 minutos iniciado para enquete {poll_id}")
            
        except Exception as e:
            logger.error(f"Erro ao iniciar timer da enquete: {e}")
    
    def _close_poll(self, poll_id):
        """Encerrar enquete automaticamente"""
        try:
            if poll_id not in self.active_polls:
                return
            
            poll_data = self.active_polls[poll_id]
            poll = poll_data['poll']
            
            # Marcar como encerrada no banco
            poll.is_active = False
            poll.closed_at = datetime.utcnow()
            
            from src.models.database import db
            db.session.commit()
            
            # Calcular resultados
            results = self._calculate_results(poll_id)
            
            # Notificar usuários
            from src.main import broadcast_to_users
            
            broadcast_to_users('poll_closed', {
                'poll_id': poll_id,
                'question': poll.question,
                'results': results,
                'total_votes': poll_data['total_votes'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Remover da lista ativa
            del self.active_polls[poll_id]
            
            logger.info(f"Enquete {poll_id} encerrada automaticamente")
            
        except Exception as e:
            logger.error(f"Erro ao encerrar enquete {poll_id}: {e}")
    
    def vote_on_poll(self, poll_id, option_id, user_id):
        """Registrar voto em enquete"""
        try:
            if poll_id not in self.active_polls:
                return {'error': 'Enquete não encontrada ou já encerrada'}
            
            from src.models.database import db, PollVote
            
            # Verificar se usuário já votou
            existing_vote = PollVote.query.filter_by(
                poll_id=poll_id,
                user_id=user_id
            ).first()
            
            if existing_vote:
                return {'error': 'Você já votou nesta enquete'}
            
            # Verificar se opção existe
            poll_data = self.active_polls[poll_id]
            valid_option_ids = [opt.id for opt in poll_data['options']]
            
            if option_id not in valid_option_ids:
                return {'error': 'Opção inválida'}
            
            # Registrar voto
            vote = PollVote(
                poll_id=poll_id,
                option_id=option_id,
                user_id=user_id
            )
            
            db.session.add(vote)
            db.session.commit()
            
            # Atualizar contadores em memória
            poll_data['votes'][option_id] += 1
            poll_data['total_votes'] += 1
            
            # Notificar atualização em tempo real
            from src.main import broadcast_to_users
            
            broadcast_to_users('poll_vote_update', {
                'poll_id': poll_id,
                'option_id': option_id,
                'votes': poll_data['votes'][option_id],
                'total_votes': poll_data['total_votes'],
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Voto registrado: Poll {poll_id}, Option {option_id}, User {user_id}")
            
            return {'status': 'success', 'message': 'Voto registrado com sucesso'}
            
        except Exception as e:
            logger.error(f"Erro ao registrar voto: {e}")
            if 'db' in locals():
                db.session.rollback()
            return {'error': 'Erro interno do servidor'}
    
    def _calculate_results(self, poll_id):
        """Calcular resultados da enquete"""
        try:
            if poll_id not in self.active_polls:
                return []
            
            poll_data = self.active_polls[poll_id]
            total_votes = poll_data['total_votes']
            
            results = []
            for option in poll_data['options']:
                votes = poll_data['votes'][option.id]
                percentage = (votes / total_votes * 100) if total_votes > 0 else 0
                
                results.append({
                    'option_id': option.id,
                    'text': option.text,
                    'votes': votes,
                    'percentage': round(percentage, 1)
                })
            
            # Ordenar por número de votos
            results.sort(key=lambda x: x['votes'], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Erro ao calcular resultados: {e}")
            return []
    
    def get_active_polls(self):
        """Obter enquetes ativas"""
        try:
            active_list = []
            
            for poll_id, poll_data in self.active_polls.items():
                poll = poll_data['poll']
                
                active_list.append({
                    'id': poll.id,
                    'question': poll.question,
                    'options': [{'id': opt.id, 'text': opt.text} for opt in poll_data['options']],
                    'total_votes': poll_data['total_votes'],
                    'expires_at': poll.expires_at.isoformat(),
                    'context': poll.context,
                    'time_remaining': max(0, int((poll.expires_at - datetime.utcnow()).total_seconds()))
                })
            
            return active_list
            
        except Exception as e:
            logger.error(f"Erro ao obter enquetes ativas: {e}")
            return []
    
    def get_poll_results(self, poll_id):
        """Obter resultados de uma enquete específica"""
        try:
            if poll_id in self.active_polls:
                return self._calculate_results(poll_id)
            
            # Buscar enquete encerrada no banco
            from src.models.database import Poll, PollOption, PollVote
            
            poll = Poll.query.get(poll_id)
            if not poll:
                return None
            
            results = []
            for option in poll.options:
                votes_count = PollVote.query.filter_by(option_id=option.id).count()
                total_votes = PollVote.query.filter_by(poll_id=poll_id).count()
                
                percentage = (votes_count / total_votes * 100) if total_votes > 0 else 0
                
                results.append({
                    'option_id': option.id,
                    'text': option.text,
                    'votes': votes_count,
                    'percentage': round(percentage, 1)
                })
            
            results.sort(key=lambda x: x['votes'], reverse=True)
            
            return results
            
        except Exception as e:
            logger.error(f"Erro ao obter resultados da enquete: {e}")
            return None
    
    def create_manual_poll(self, question, options, duration_minutes=10):
        """Criar enquete manual"""
        try:
            poll_data = self._create_poll(
                question=question,
                options=options,
                context='manual',
                source_content='Enquete criada manualmente',
                timestamp=None
            )
            
            if poll_data:
                # Iniciar timer personalizado
                timer = Timer(duration_minutes * 60, self._close_poll, args=[poll_data['id']])
                timer.start()
                
                logger.info(f"Enquete manual criada: {question}")
                return poll_data
            
            return None
            
        except Exception as e:
            logger.error(f"Erro ao criar enquete manual: {e}")
            return None
    
    def get_poll_stats(self):
        """Obter estatísticas das enquetes"""
        try:
            from src.models.database import Poll, PollVote
            
            total_polls = Poll.query.count()
            active_polls_count = len(self.active_polls)
            total_votes = PollVote.query.count()
            
            # Enquetes mais votadas
            popular_polls = Poll.query.join(PollVote).group_by(Poll.id).order_by(
                Poll.id.desc()
            ).limit(5).all()
            
            return {
                'total_polls': total_polls,
                'active_polls': active_polls_count,
                'total_votes': total_votes,
                'popular_polls': [
                    {
                        'id': poll.id,
                        'question': poll.question[:100] + '...' if len(poll.question) > 100 else poll.question,
                        'created_at': poll.created_at.isoformat()
                    }
                    for poll in popular_polls
                ]
            }
            
        except Exception as e:
            logger.error(f"Erro ao obter estatísticas: {e}")
            return {
                'total_polls': 0,
                'active_polls': 0,
                'total_votes': 0,
                'popular_polls': []
            }

# Instância global do serviço
poll_service = PollGenerationService()

def generate_poll_from_content(content, context='momento_polemico', timestamp=None):
    """Função helper para gerar enquete"""
    return poll_service.generate_poll_from_content(content, context, timestamp)

def vote_on_poll(poll_id, option_id, user_id):
    """Função helper para votar"""
    return poll_service.vote_on_poll(poll_id, option_id, user_id)

def get_active_polls():
    """Função helper para obter enquetes ativas"""
    return poll_service.get_active_polls()

def get_poll_results(poll_id):
    """Função helper para obter resultados"""
    return poll_service.get_poll_results(poll_id)

def create_manual_poll(question, options, duration_minutes=10):
    """Função helper para criar enquete manual"""
    return poll_service.create_manual_poll(question, options, duration_minutes)

def get_poll_stats():
    """Função helper para obter estatísticas"""
    return poll_service.get_poll_stats()

