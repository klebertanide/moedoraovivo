import whisper
import yt_dlp
import os
import threading
import time
import logging
from datetime import datetime, timedelta
import tempfile
import subprocess
from threading import Timer
import re
from collections import Counter
import json

logger = logging.getLogger(__name__)

class WhisperTranscriptionService:
    """Serviço para transcrição automática com Whisper"""
    
    def __init__(self):
        self.model = None
        self.youtube_url = None
        self.is_running = False
        self.transcription_interval = 15 * 60  # 15 minutos
        self.timer = None
        self.last_transcription = None
        self.controversial_keywords = [
            'polêmico', 'controverso', 'escândalo', 'problema', 'briga', 'discussão',
            'vergonha', 'constrangedor', 'embaraçoso', 'ridículo', 'absurdo',
            'inacreditável', 'chocante', 'surreal', 'bizarro', 'estranho',
            'drama', 'confusão', 'barraco', 'treta', 'climão'
        ]
        
    def load_model(self, model_size='base'):
        """Carregar modelo Whisper"""
        try:
            logger.info(f"Carregando modelo Whisper: {model_size}")
            self.model = whisper.load_model(model_size)
            logger.info("Modelo Whisper carregado com sucesso")
            return True
        except Exception as e:
            logger.error(f"Erro ao carregar modelo Whisper: {e}")
            return False
    
    def set_youtube_url(self, url):
        """Definir URL do YouTube para monitoramento"""
        self.youtube_url = url
        logger.info(f"URL do YouTube definida: {url}")
    
    def start_monitoring(self):
        """Iniciar monitoramento automático"""
        if not self.model:
            logger.error("Modelo Whisper não carregado")
            return False
        
        if not self.youtube_url:
            logger.error("URL do YouTube não definida")
            return False
        
        if self.is_running:
            logger.warning("Monitoramento já está em execução")
            return False
        
        self.is_running = True
        self._schedule_next_transcription()
        logger.info("Monitoramento Whisper iniciado")
        return True
    
    def stop_monitoring(self):
        """Parar monitoramento automático"""
        self.is_running = False
        if self.timer:
            self.timer.cancel()
        logger.info("Monitoramento Whisper parado")
    
    def _schedule_next_transcription(self):
        """Agendar próxima transcrição"""
        if not self.is_running:
            return
        
        self.timer = Timer(self.transcription_interval, self._perform_transcription)
        self.timer.start()
        
        next_time = datetime.now() + timedelta(seconds=self.transcription_interval)
        logger.info(f"Próxima transcrição agendada para: {next_time.strftime('%H:%M:%S')}")
    
    def _perform_transcription(self):
        """Executar transcrição em thread separada"""
        if not self.is_running:
            return
        
        thread = threading.Thread(target=self._transcribe_live_audio, daemon=True)
        thread.start()
        
        # Agendar próxima transcrição
        self._schedule_next_transcription()
    
    def _transcribe_live_audio(self):
        """Transcrever áudio da live"""
        try:
            logger.info("Iniciando transcrição da live...")
            
            # Capturar áudio dos últimos 5 minutos
            audio_file = self._capture_youtube_audio(duration=300)  # 5 minutos
            
            if not audio_file:
                logger.error("Falha ao capturar áudio")
                return
            
            # Transcrever com Whisper
            result = self.model.transcribe(audio_file, language='pt')
            
            # Processar resultado
            transcription_data = self._process_transcription(result)
            
            # Salvar transcrição
            self._save_transcription(transcription_data)
            
            # Analisar conteúdo polêmico
            controversial_moments = self._analyze_controversial_content(transcription_data)
            
            if controversial_moments:
                self._trigger_poll_generation(controversial_moments)
            
            # Limpar arquivo temporário
            try:
                os.remove(audio_file)
            except:
                pass
            
            logger.info("Transcrição concluída com sucesso")
            
        except Exception as e:
            logger.error(f"Erro na transcrição: {e}")
    
    def _capture_youtube_audio(self, duration=300):
        """Capturar áudio do YouTube"""
        try:
            # Configurar yt-dlp para capturar stream de áudio
            ydl_opts = {
                'format': 'bestaudio/best',
                'outtmpl': tempfile.mktemp(suffix='.%(ext)s'),
                'extractaudio': True,
                'audioformat': 'wav',
                'audioquality': '192K',
                'quiet': True,
                'no_warnings': True
            }
            
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                # Extrair informações do stream
                info = ydl.extract_info(self.youtube_url, download=False)
                
                if not info.get('is_live'):
                    logger.warning("Stream não está ao vivo")
                    return None
                
                # Obter URL do stream de áudio
                audio_url = None
                for format_info in info['formats']:
                    if format_info.get('acodec') != 'none':
                        audio_url = format_info['url']
                        break
                
                if not audio_url:
                    logger.error("URL de áudio não encontrada")
                    return None
                
                # Capturar segmento de áudio com ffmpeg
                output_file = tempfile.mktemp(suffix='.wav')
                
                cmd = [
                    'ffmpeg',
                    '-i', audio_url,
                    '-t', str(duration),
                    '-acodec', 'pcm_s16le',
                    '-ar', '16000',
                    '-ac', '1',
                    '-y',
                    output_file
                ]
                
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=duration + 30)
                
                if result.returncode == 0 and os.path.exists(output_file):
                    logger.info(f"Áudio capturado: {output_file}")
                    return output_file
                else:
                    logger.error(f"Erro no ffmpeg: {result.stderr}")
                    return None
                
        except Exception as e:
            logger.error(f"Erro ao capturar áudio: {e}")
            return None
    
    def _process_transcription(self, result):
        """Processar resultado da transcrição"""
        try:
            segments = []
            
            for segment in result['segments']:
                segments.append({
                    'start': segment['start'],
                    'end': segment['end'],
                    'text': segment['text'].strip(),
                    'confidence': segment.get('avg_logprob', 0)
                })
            
            return {
                'timestamp': datetime.utcnow().isoformat(),
                'language': result.get('language', 'pt'),
                'full_text': result['text'].strip(),
                'segments': segments,
                'duration': segments[-1]['end'] if segments else 0
            }
            
        except Exception as e:
            logger.error(f"Erro ao processar transcrição: {e}")
            return None
    
    def _save_transcription(self, transcription_data):
        """Salvar transcrição no banco de dados"""
        try:
            from src.models.database import db, Transcription
            
            transcription = Transcription(
                content=transcription_data['full_text'],
                segments=json.dumps(transcription_data['segments']),
                language=transcription_data['language'],
                duration=transcription_data['duration']
            )
            
            db.session.add(transcription)
            db.session.commit()
            
            self.last_transcription = transcription
            logger.info(f"Transcrição salva no banco: ID {transcription.id}")
            
        except Exception as e:
            logger.error(f"Erro ao salvar transcrição: {e}")
            if 'db' in locals():
                db.session.rollback()
    
    def _analyze_controversial_content(self, transcription_data):
        """Analisar conteúdo polêmico na transcrição"""
        try:
            text = transcription_data['full_text'].lower()
            segments = transcription_data['segments']
            
            controversial_moments = []
            
            # Buscar palavras-chave polêmicas
            for keyword in self.controversial_keywords:
                if keyword in text:
                    # Encontrar segmentos que contêm a palavra-chave
                    for segment in segments:
                        if keyword in segment['text'].lower():
                            controversial_moments.append({
                                'keyword': keyword,
                                'text': segment['text'],
                                'start_time': segment['start'],
                                'end_time': segment['end'],
                                'confidence': segment['confidence']
                            })
            
            # Detectar padrões de discussão/briga
            discussion_patterns = [
                r'não concordo',
                r'você está errado',
                r'isso é absurdo',
                r'não faz sentido',
                r'que ridículo',
                r'não acredito'
            ]
            
            for pattern in discussion_patterns:
                matches = re.finditer(pattern, text, re.IGNORECASE)
                for match in matches:
                    # Encontrar segmento correspondente
                    for segment in segments:
                        if pattern.replace(r'', '') in segment['text'].lower():
                            controversial_moments.append({
                                'keyword': 'discussão',
                                'text': segment['text'],
                                'start_time': segment['start'],
                                'end_time': segment['end'],
                                'confidence': segment['confidence'],
                                'pattern': pattern
                            })
            
            # Remover duplicatas e ordenar por tempo
            unique_moments = []
            seen_times = set()
            
            for moment in controversial_moments:
                time_key = f"{moment['start_time']:.1f}"
                if time_key not in seen_times:
                    seen_times.add(time_key)
                    unique_moments.append(moment)
            
            unique_moments.sort(key=lambda x: x['start_time'])
            
            logger.info(f"Encontrados {len(unique_moments)} momentos polêmicos")
            return unique_moments
            
        except Exception as e:
            logger.error(f"Erro ao analisar conteúdo polêmico: {e}")
            return []
    
    def _trigger_poll_generation(self, controversial_moments):
        """Disparar geração de enquete baseada em momentos polêmicos"""
        try:
            if not controversial_moments:
                return
            
            # Selecionar momento mais polêmico (maior confiança)
            best_moment = max(controversial_moments, key=lambda x: x['confidence'])
            
            # Gerar enquete
            from src.services.poll_service import generate_poll_from_content
            
            poll_data = generate_poll_from_content(
                content=best_moment['text'],
                context='momento_polemico',
                timestamp=best_moment['start_time']
            )
            
            if poll_data:
                logger.info(f"Enquete gerada a partir de momento polêmico: {best_moment['text'][:50]}...")
                
                # Notificar sistema
                from src.main import broadcast_to_users
                
                broadcast_to_users('poll_generated', {
                    'poll_id': poll_data['id'],
                    'question': poll_data['question'],
                    'trigger': 'whisper_analysis',
                    'timestamp': datetime.utcnow().isoformat()
                })
            
        except Exception as e:
            logger.error(f"Erro ao gerar enquete: {e}")
    
    def get_recent_transcriptions(self, limit=5):
        """Obter transcrições recentes"""
        try:
            from src.models.database import Transcription
            
            transcriptions = Transcription.query.order_by(
                Transcription.created_at.desc()
            ).limit(limit).all()
            
            result = []
            for t in transcriptions:
                result.append({
                    'id': t.id,
                    'content': t.content[:200] + '...' if len(t.content) > 200 else t.content,
                    'language': t.language,
                    'duration': t.duration,
                    'created_at': t.created_at.isoformat()
                })
            
            return result
            
        except Exception as e:
            logger.error(f"Erro ao buscar transcrições: {e}")
            return []
    
    def manual_transcription(self, audio_file_path):
        """Realizar transcrição manual de arquivo de áudio"""
        try:
            if not self.model:
                logger.error("Modelo Whisper não carregado")
                return None
            
            if not os.path.exists(audio_file_path):
                logger.error(f"Arquivo não encontrado: {audio_file_path}")
                return None
            
            logger.info(f"Iniciando transcrição manual: {audio_file_path}")
            
            result = self.model.transcribe(audio_file_path, language='pt')
            transcription_data = self._process_transcription(result)
            
            if transcription_data:
                self._save_transcription(transcription_data)
                logger.info("Transcrição manual concluída")
                return transcription_data
            
            return None
            
        except Exception as e:
            logger.error(f"Erro na transcrição manual: {e}")
            return None
    
    def get_status(self):
        """Obter status do serviço"""
        return {
            'model_loaded': self.model is not None,
            'is_running': self.is_running,
            'youtube_url': self.youtube_url,
            'interval_minutes': self.transcription_interval // 60,
            'last_transcription': self.last_transcription.created_at.isoformat() if self.last_transcription else None,
            'next_transcription': (datetime.now() + timedelta(seconds=self.transcription_interval)).isoformat() if self.is_running else None
        }

# Instância global do serviço
whisper_service = WhisperTranscriptionService()

def init_whisper_service(model_size='base', youtube_url=None):
    """Inicializar serviço Whisper"""
    try:
        logger.info("Inicializando serviço Whisper...")
        
        # Carregar modelo
        if not whisper_service.load_model(model_size):
            logger.error("Falha ao carregar modelo Whisper")
            return False
        
        # Definir URL se fornecida
        if youtube_url:
            whisper_service.set_youtube_url(youtube_url)
        
        logger.info("Serviço Whisper inicializado com sucesso")
        return True
        
    except Exception as e:
        logger.error(f"Erro ao inicializar serviço Whisper: {e}")
        return False

def start_live_monitoring(youtube_url):
    """Iniciar monitoramento da live"""
    try:
        whisper_service.set_youtube_url(youtube_url)
        return whisper_service.start_monitoring()
    except Exception as e:
        logger.error(f"Erro ao iniciar monitoramento: {e}")
        return False

def stop_live_monitoring():
    """Parar monitoramento da live"""
    try:
        whisper_service.stop_monitoring()
        return True
    except Exception as e:
        logger.error(f"Erro ao parar monitoramento: {e}")
        return False

def get_transcription_stats():
    """Obter estatísticas de transcrição"""
    try:
        from src.models.database import Transcription
        
        total_transcriptions = Transcription.query.count()
        recent_transcriptions = whisper_service.get_recent_transcriptions(3)
        
        return {
            'total_transcriptions': total_transcriptions,
            'recent_transcriptions': recent_transcriptions,
            'service_status': whisper_service.get_status()
        }
        
    except Exception as e:
        logger.error(f"Erro ao obter estatísticas: {e}")
        return {
            'total_transcriptions': 0,
            'recent_transcriptions': [],
            'service_status': whisper_service.get_status()
        }

