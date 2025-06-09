from flask import Blueprint, request, jsonify, session, Response
from src.models.database import db, Camera, User
import cv2
import threading
import time
import logging
import os
from datetime import datetime
import base64
import numpy as np

logger = logging.getLogger(__name__)

cameras_bp = Blueprint('cameras', __name__)

# Dicionário para armazenar streams ativos
active_streams = {}
stream_threads = {}

class RTSPStreamManager:
    """Gerenciador de streams RTSP"""
    
    def __init__(self):
        self.streams = {}
        self.running = {}
    
    def start_stream(self, camera_id, rtsp_url):
        """Iniciar stream de uma câmera"""
        try:
            if camera_id in self.streams:
                self.stop_stream(camera_id)
            
            # Criar captura de vídeo
            cap = cv2.VideoCapture(rtsp_url)
            
            if not cap.isOpened():
                logger.error(f"Não foi possível conectar à câmera {camera_id}: {rtsp_url}")
                return False
            
            self.streams[camera_id] = cap
            self.running[camera_id] = True
            
            # Iniciar thread para processar frames
            thread = threading.Thread(
                target=self._process_stream,
                args=(camera_id,),
                daemon=True
            )
            thread.start()
            
            logger.info(f"Stream iniciado para câmera {camera_id}")
            return True
            
        except Exception as e:
            logger.error(f"Erro ao iniciar stream da câmera {camera_id}: {e}")
            return False
    
    def stop_stream(self, camera_id):
        """Parar stream de uma câmera"""
        try:
            self.running[camera_id] = False
            
            if camera_id in self.streams:
                self.streams[camera_id].release()
                del self.streams[camera_id]
            
            logger.info(f"Stream parado para câmera {camera_id}")
            
        except Exception as e:
            logger.error(f"Erro ao parar stream da câmera {camera_id}: {e}")
    
    def _process_stream(self, camera_id):
        """Processar frames do stream em thread separada"""
        cap = self.streams.get(camera_id)
        if not cap:
            return
        
        while self.running.get(camera_id, False):
            try:
                ret, frame = cap.read()
                if not ret:
                    logger.warning(f"Falha ao ler frame da câmera {camera_id}")
                    time.sleep(1)
                    continue
                
                # Redimensionar frame para economizar banda
                frame = cv2.resize(frame, (640, 480))
                
                # Armazenar frame atual
                active_streams[camera_id] = frame
                
                # Aguardar um pouco antes do próximo frame
                time.sleep(1/30)  # ~30 FPS
                
            except Exception as e:
                logger.error(f"Erro ao processar frame da câmera {camera_id}: {e}")
                time.sleep(1)
    
    def get_frame(self, camera_id):
        """Obter frame atual de uma câmera"""
        return active_streams.get(camera_id)
    
    def stop_all_streams(self):
        """Parar todos os streams"""
        for camera_id in list(self.streams.keys()):
            self.stop_stream(camera_id)

# Instância global do gerenciador
stream_manager = RTSPStreamManager()

@cameras_bp.route('/', methods=['GET'])
def get_cameras():
    """Listar todas as câmeras"""
    try:
        cameras = Camera.query.filter_by(is_active=True).all()
        
        cameras_data = []
        for camera in cameras:
            cameras_data.append({
                'id': camera.id,
                'name': camera.name,
                'rtsp_url': camera.rtsp_url,
                'position_x': camera.position_x,
                'position_y': camera.position_y,
                'width': camera.width,
                'height': camera.height,
                'is_streaming': camera.id in active_streams,
                'created_at': camera.created_at.isoformat()
            })
        
        return jsonify({'cameras': cameras_data})
        
    except Exception as e:
        logger.error(f"Erro ao buscar câmeras: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/', methods=['POST'])
def add_camera():
    """Adicionar nova câmera (apenas admin)"""
    # TODO: Verificar se usuário é admin
    
    try:
        data = request.get_json()
        
        name = data.get('name', '').strip()
        rtsp_url = data.get('rtsp_url', '').strip()
        position_x = data.get('position_x', 0)
        position_y = data.get('position_y', 0)
        width = data.get('width', 640)
        height = data.get('height', 480)
        
        if not name or not rtsp_url:
            return jsonify({'error': 'Nome e URL RTSP são obrigatórios'}), 400
        
        # Verificar se URL já existe
        existing = Camera.query.filter_by(rtsp_url=rtsp_url).first()
        if existing:
            return jsonify({'error': 'URL RTSP já cadastrada'}), 400
        
        # Criar nova câmera
        camera = Camera(
            name=name,
            rtsp_url=rtsp_url,
            position_x=position_x,
            position_y=position_y,
            width=width,
            height=height
        )
        
        db.session.add(camera)
        db.session.commit()
        
        logger.info(f"Nova câmera adicionada: {name}")
        
        return jsonify({
            'status': 'success',
            'camera': {
                'id': camera.id,
                'name': camera.name,
                'rtsp_url': camera.rtsp_url,
                'position_x': camera.position_x,
                'position_y': camera.position_y,
                'width': camera.width,
                'height': camera.height
            }
        })
        
    except Exception as e:
        logger.error(f"Erro ao adicionar câmera: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/<int:camera_id>', methods=['PUT'])
def update_camera(camera_id):
    """Atualizar câmera (apenas admin)"""
    # TODO: Verificar se usuário é admin
    
    try:
        camera = Camera.query.get(camera_id)
        if not camera:
            return jsonify({'error': 'Câmera não encontrada'}), 404
        
        data = request.get_json()
        
        # Atualizar campos
        if 'name' in data:
            camera.name = data['name'].strip()
        if 'rtsp_url' in data:
            camera.rtsp_url = data['rtsp_url'].strip()
        if 'position_x' in data:
            camera.position_x = data['position_x']
        if 'position_y' in data:
            camera.position_y = data['position_y']
        if 'width' in data:
            camera.width = data['width']
        if 'height' in data:
            camera.height = data['height']
        if 'is_active' in data:
            camera.is_active = data['is_active']
        
        db.session.commit()
        
        # Se câmera foi desativada, parar stream
        if not camera.is_active and camera_id in active_streams:
            stream_manager.stop_stream(camera_id)
        
        logger.info(f"Câmera {camera_id} atualizada")
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Erro ao atualizar câmera: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/<int:camera_id>', methods=['DELETE'])
def delete_camera(camera_id):
    """Remover câmera (apenas admin)"""
    # TODO: Verificar se usuário é admin
    
    try:
        camera = Camera.query.get(camera_id)
        if not camera:
            return jsonify({'error': 'Câmera não encontrada'}), 404
        
        # Parar stream se estiver ativo
        if camera_id in active_streams:
            stream_manager.stop_stream(camera_id)
        
        # Remover do banco
        db.session.delete(camera)
        db.session.commit()
        
        logger.info(f"Câmera {camera_id} removida")
        
        return jsonify({'status': 'success'})
        
    except Exception as e:
        logger.error(f"Erro ao remover câmera: {e}")
        db.session.rollback()
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/<int:camera_id>/start', methods=['POST'])
def start_camera_stream(camera_id):
    """Iniciar stream de uma câmera"""
    try:
        camera = Camera.query.get(camera_id)
        if not camera or not camera.is_active:
            return jsonify({'error': 'Câmera não encontrada ou inativa'}), 404
        
        success = stream_manager.start_stream(camera_id, camera.rtsp_url)
        
        if success:
            return jsonify({'status': 'success', 'message': 'Stream iniciado'})
        else:
            return jsonify({'error': 'Falha ao iniciar stream'}), 500
        
    except Exception as e:
        logger.error(f"Erro ao iniciar stream da câmera {camera_id}: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/<int:camera_id>/stop', methods=['POST'])
def stop_camera_stream(camera_id):
    """Parar stream de uma câmera"""
    try:
        stream_manager.stop_stream(camera_id)
        return jsonify({'status': 'success', 'message': 'Stream parado'})
        
    except Exception as e:
        logger.error(f"Erro ao parar stream da câmera {camera_id}: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/<int:camera_id>/stream')
def camera_stream(camera_id):
    """Stream de vídeo de uma câmera específica"""
    try:
        camera = Camera.query.get(camera_id)
        if not camera or not camera.is_active:
            return jsonify({'error': 'Câmera não encontrada ou inativa'}), 404
        
        def generate_frames():
            while True:
                frame = stream_manager.get_frame(camera_id)
                if frame is not None:
                    # Codificar frame como JPEG
                    ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
                    if ret:
                        frame_bytes = buffer.tobytes()
                        yield (b'--frame\r\n'
                               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                
                time.sleep(1/15)  # ~15 FPS para economizar banda
        
        return Response(
            generate_frames(),
            mimetype='multipart/x-mixed-replace; boundary=frame'
        )
        
    except Exception as e:
        logger.error(f"Erro no stream da câmera {camera_id}: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/<int:camera_id>/snapshot')
def camera_snapshot(camera_id):
    """Obter snapshot atual de uma câmera"""
    try:
        frame = stream_manager.get_frame(camera_id)
        if frame is None:
            return jsonify({'error': 'Frame não disponível'}), 404
        
        # Codificar como base64
        ret, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
        if ret:
            img_base64 = base64.b64encode(buffer).decode('utf-8')
            return jsonify({
                'snapshot': f"data:image/jpeg;base64,{img_base64}",
                'timestamp': datetime.utcnow().isoformat()
            })
        else:
            return jsonify({'error': 'Erro ao codificar imagem'}), 500
        
    except Exception as e:
        logger.error(f"Erro ao obter snapshot da câmera {camera_id}: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/start-all', methods=['POST'])
def start_all_cameras():
    """Iniciar todas as câmeras ativas"""
    try:
        cameras = Camera.query.filter_by(is_active=True).all()
        
        started = 0
        failed = 0
        
        for camera in cameras:
            success = stream_manager.start_stream(camera.id, camera.rtsp_url)
            if success:
                started += 1
            else:
                failed += 1
        
        return jsonify({
            'status': 'success',
            'started': started,
            'failed': failed,
            'total': len(cameras)
        })
        
    except Exception as e:
        logger.error(f"Erro ao iniciar todas as câmeras: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/stop-all', methods=['POST'])
def stop_all_cameras():
    """Parar todas as câmeras"""
    try:
        stream_manager.stop_all_streams()
        return jsonify({'status': 'success', 'message': 'Todos os streams parados'})
        
    except Exception as e:
        logger.error(f"Erro ao parar todas as câmeras: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/status')
def cameras_status():
    """Obter status de todas as câmeras"""
    try:
        cameras = Camera.query.all()
        
        status_data = []
        for camera in cameras:
            status_data.append({
                'id': camera.id,
                'name': camera.name,
                'is_active': camera.is_active,
                'is_streaming': camera.id in active_streams,
                'rtsp_url': camera.rtsp_url[:50] + '...' if len(camera.rtsp_url) > 50 else camera.rtsp_url
            })
        
        return jsonify({
            'cameras': status_data,
            'total_cameras': len(cameras),
            'active_cameras': len([c for c in cameras if c.is_active]),
            'streaming_cameras': len(active_streams)
        })
        
    except Exception as e:
        logger.error(f"Erro ao obter status das câmeras: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

@cameras_bp.route('/test-rtsp', methods=['POST'])
def test_rtsp_connection():
    """Testar conexão RTSP (apenas desenvolvimento)"""
    if os.getenv('FLASK_ENV') != 'development':
        return jsonify({'error': 'Endpoint disponível apenas em desenvolvimento'}), 403
    
    try:
        data = request.get_json()
        rtsp_url = data.get('rtsp_url')
        
        if not rtsp_url:
            return jsonify({'error': 'URL RTSP é obrigatória'}), 400
        
        # Testar conexão
        cap = cv2.VideoCapture(rtsp_url)
        
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            
            if ret:
                return jsonify({
                    'status': 'success',
                    'message': 'Conexão RTSP bem-sucedida',
                    'frame_shape': frame.shape if frame is not None else None
                })
            else:
                return jsonify({
                    'status': 'warning',
                    'message': 'Conexão estabelecida mas falha ao ler frame'
                })
        else:
            return jsonify({
                'status': 'error',
                'message': 'Falha ao conectar com URL RTSP'
            })
        
    except Exception as e:
        logger.error(f"Erro ao testar RTSP: {e}")
        return jsonify({'error': 'Erro interno do servidor'}), 500

def init_camera_system():
    """Inicializar sistema de câmeras"""
    try:
        # Iniciar câmeras ativas automaticamente
        from src.models.database import Camera
        
        active_cameras = Camera.query.filter_by(is_active=True).all()
        
        for camera in active_cameras:
            stream_manager.start_stream(camera.id, camera.rtsp_url)
        
        logger.info(f"Sistema de câmeras inicializado - {len(active_cameras)} câmeras ativas")
        
    except Exception as e:
        logger.error(f"Erro ao inicializar sistema de câmeras: {e}")

def cleanup_camera_system():
    """Limpar sistema de câmeras"""
    try:
        stream_manager.stop_all_streams()
        logger.info("Sistema de câmeras finalizado")
        
    except Exception as e:
        logger.error(f"Erro ao finalizar sistema de câmeras: {e}")

