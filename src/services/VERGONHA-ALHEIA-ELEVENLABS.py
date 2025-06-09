import os
import requests
import random
import logging
from datetime import datetime
from threading import Thread
import queue
import time

logger = logging.getLogger(__name__)

class ElevenLabsService:
    """Serviço para integração com ElevenLabs TTS"""
    
    def __init__(self):
        self.api_key = os.getenv('ELEVENLABS_API_KEY', 'your_api_key_here')
        self.voice_id = os.getenv('ELEVENLABS_VOICE_ID', 'CY9SQTU8fYN5MZMw15Ma')
        self.base_url = 'https://api.elevenlabs.io/v1'
        self.audio_queue = queue.Queue()
        self.is_processing = False
        
    def generate_speech(self, text, output_path=None):
        """Gerar áudio a partir de texto"""
        try:
            url = f"{self.base_url}/text-to-speech/{self.voice_id}"
            
            headers = {
                'Accept': 'audio/mpeg',
                'Content-Type': 'application/json',
                'xi-api-key': self.api_key
            }
            
            data = {
                'text': text,
                'model_id': 'eleven_multilingual_v2',
                'voice_settings': {
                    'stability': 0.5,
                    'similarity_boost': 0.5,
                    'style': 0.5,
                    'use_speaker_boost': True
                },
                'output_format': 'mp3_44100_128'
            }
            
            response = requests.post(url, json=data, headers=headers, timeout=30)
            
            if response.status_code == 200:
                if output_path:
                    with open(output_path, 'wb') as f:
                        f.write(response.content)
                    logger.info(f"Áudio gerado e salvo em: {output_path}")
                    return output_path
                else:
                    return response.content
            else:
                logger.error(f"Erro na API ElevenLabs: {response.status_code} - {response.text}")
                return None
                
        except Exception as e:
            logger.error(f"Erro ao gerar speech: {e}")
            return None
    
    def add_to_queue(self, text, callback=None):
        """Adicionar texto à fila de processamento"""
        self.audio_queue.put({
            'text': text,
            'callback': callback,
            'timestamp': datetime.utcnow()
        })
        
        if not self.is_processing:
            self.start_processing()
    
    def start_processing(self):
        """Iniciar processamento da fila em thread separada"""
        if self.is_processing:
            return
        
        self.is_processing = True
        thread = Thread(target=self._process_queue)
        thread.daemon = True
        thread.start()
    
    def _process_queue(self):
        """Processar fila de áudios"""
        while not self.audio_queue.empty():
            try:
                item = self.audio_queue.get(timeout=1)
                text = item['text']
                callback = item['callback']
                
                logger.info(f"Processando TTS: {text[:50]}...")
                
                # Gerar áudio
                timestamp = int(datetime.utcnow().timestamp())
                output_path = f"/tmp/tts_{timestamp}.mp3"
                
                audio_path = self.generate_speech(text, output_path)
                
                if audio_path and callback:
                    callback(audio_path, text)
                
                # Aguardar um pouco entre processamentos
                time.sleep(1)
                
            except queue.Empty:
                break
            except Exception as e:
                logger.error(f"Erro ao processar item da fila TTS: {e}")
        
        self.is_processing = False

class EmbarrassingTruthService:
    """Serviço para gerenciar verdades constrangedoras"""
    
    def __init__(self):
        self.tts_service = ElevenLabsService()
        self.embarrassing_queue = queue.Queue()
        self.max_per_live = 3
        self.current_count = 0
    
    def get_random_truth(self):
        """Obter verdade constrangedora aleatória"""
        try:
            from src.models.database import EmbarrassingTruth
            
            # Buscar verdades ativas
            truths = EmbarrassingTruth.query.filter_by(is_active=True).all()
            
            if not truths:
                logger.warning("Nenhuma verdade constrangedora encontrada")
                return None
            
            # Selecionar aleatoriamente
            selected_truth = random.choice(truths)
            
            # Incrementar contador de uso
            selected_truth.times_used += 1
            
            from src.models.database import db
            db.session.commit()
            
            return selected_truth
            
        except Exception as e:
            logger.error(f"Erro ao buscar verdade aleatória: {e}")
            return None
    
    def process_embarrassing_request(self, user_name):
        """Processar solicitação de vergonha alheia"""
        try:
            # Verificar limite
            if self.current_count >= self.max_per_live:
                logger.warning("Limite de vergonhas atingido para esta live")
                return False
            
            # Obter verdade aleatória
            truth = self.get_random_truth()
            if not truth:
                logger.error("Não foi possível obter verdade constrangedora")
                return False
            
            # Preparar texto para TTS
            text = f"Atenção! {truth.target_member}! {truth.content}"
            
            # Adicionar à fila de processamento
            self.tts_service.add_to_queue(
                text, 
                callback=lambda audio_path, text: self._on_audio_ready(
                    audio_path, text, user_name, truth
                )
            )
            
            self.current_count += 1
            logger.info(f"Vergonha processada para {user_name} - Count: {self.current_count}")
            
            return True
            
        except Exception as e:
            logger.error(f"Erro ao processar vergonha: {e}")
            return False
    
    def _on_audio_ready(self, audio_path, text, user_name, truth):
        """Callback quando áudio está pronto"""
        try:
            # Notificar overlay para exibir
            from src.main import broadcast_to_overlay
            
            broadcast_to_overlay('embarrassing_ready', {
                'audio_path': audio_path,
                'text': text,
                'user_name': user_name,
                'target_member': truth.target_member,
                'truth_id': truth.id,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            logger.info(f"Áudio de vergonha pronto: {audio_path}")
            
        except Exception as e:
            logger.error(f"Erro no callback de áudio: {e}")
    
    def reset_live_count(self):
        """Resetar contador para nova live"""
        self.current_count = 0
        logger.info("Contador de vergonhas resetado para nova live")
    
    def get_remaining_count(self):
        """Obter quantidade restante de vergonhas"""
        return max(0, self.max_per_live - self.current_count)

class AudioFileManager:
    """Gerenciador de arquivos de áudio"""
    
    @staticmethod
    def cleanup_old_files(directory="/tmp", max_age_hours=24):
        """Limpar arquivos de áudio antigos"""
        try:
            import glob
            from pathlib import Path
            
            pattern = os.path.join(directory, "tts_*.mp3")
            files = glob.glob(pattern)
            
            current_time = time.time()
            max_age_seconds = max_age_hours * 3600
            
            cleaned_count = 0
            for file_path in files:
                file_age = current_time - os.path.getctime(file_path)
                if file_age > max_age_seconds:
                    try:
                        os.remove(file_path)
                        cleaned_count += 1
                    except OSError:
                        pass
            
            if cleaned_count > 0:
                logger.info(f"Limpeza de arquivos: {cleaned_count} arquivos removidos")
                
        except Exception as e:
            logger.error(f"Erro na limpeza de arquivos: {e}")
    
    @staticmethod
    def get_audio_url(file_path, base_url):
        """Obter URL pública para arquivo de áudio"""
        try:
            filename = os.path.basename(file_path)
            return f"{base_url}/static/audio/{filename}"
        except Exception as e:
            logger.error(f"Erro ao gerar URL de áudio: {e}")
            return None

# Instância global dos serviços
embarrassing_service = EmbarrassingTruthService()
audio_manager = AudioFileManager()

def init_embarrassing_service():
    """Inicializar serviço de vergonha alheia"""
    try:
        # Limpar arquivos antigos na inicialização
        audio_manager.cleanup_old_files()
        
        # Resetar contador
        embarrassing_service.reset_live_count()
        
        logger.info("Serviço de vergonha alheia inicializado")
        
    except Exception as e:
        logger.error(f"Erro ao inicializar serviço de vergonha: {e}")

def process_embarrassing_payment(user_name):
    """Processar pagamento de vergonha alheia aprovado"""
    try:
        success = embarrassing_service.process_embarrassing_request(user_name)
        
        if success:
            # Notificar usuários sobre nova vergonha na fila
            from src.main import broadcast_to_users
            
            broadcast_to_users('embarrassing_queued', {
                'user_name': user_name,
                'remaining': embarrassing_service.get_remaining_count(),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            return True
        else:
            return False
            
    except Exception as e:
        logger.error(f"Erro ao processar pagamento de vergonha: {e}")
        return False

def get_embarrassing_stats():
    """Obter estatísticas do sistema de vergonha"""
    try:
        from src.models.database import EmbarrassingTruth
        
        total_truths = EmbarrassingTruth.query.filter_by(is_active=True).count()
        
        return {
            'total_truths': total_truths,
            'current_count': embarrassing_service.current_count,
            'max_per_live': embarrassing_service.max_per_live,
            'remaining': embarrassing_service.get_remaining_count(),
            'queue_size': embarrassing_service.tts_service.audio_queue.qsize()
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas de vergonha: {e}")
        return {
            'total_truths': 0,
            'current_count': 0,
            'max_per_live': 3,
            'remaining': 3,
            'queue_size': 0
        }

def add_embarrassing_truth(content, target_member, created_by=None):
    """Adicionar nova verdade constrangedora"""
    try:
        from src.models.database import db, EmbarrassingTruth
        
        truth = EmbarrassingTruth(
            content=content,
            target_member=target_member,
            created_by=created_by
        )
        
        db.session.add(truth)
        db.session.commit()
        
        logger.info(f"Nova verdade adicionada para {target_member}")
        return truth
        
    except Exception as e:
        logger.error(f"Erro ao adicionar verdade: {e}")
        db.session.rollback()
        return None

def test_tts_service():
    """Testar serviço TTS (apenas desenvolvimento)"""
    if os.getenv('FLASK_ENV') != 'development':
        return False
    
    try:
        tts = ElevenLabsService()
        test_text = "Este é um teste do sistema de vergonha alheia do MOEDOR AO VIVO!"
        
        audio_path = tts.generate_speech(test_text, "/tmp/test_tts.mp3")
        
        if audio_path:
            logger.info(f"Teste TTS bem-sucedido: {audio_path}")
            return True
        else:
            logger.error("Teste TTS falhou")
            return False
            
    except Exception as e:
        logger.error(f"Erro no teste TTS: {e}")
        return False

