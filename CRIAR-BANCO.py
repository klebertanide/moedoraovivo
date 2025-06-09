#!/usr/bin/env python3
"""
Script para criar dados de teste para o MOEDOR AO VIVO
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from src.main import app
from src.models.database import db, User, EmbarrassingTruth, WelcomeMessage, Camera

def create_test_data():
    """Criar dados de teste"""
    with app.app_context():
        # Limpar dados existentes
        db.drop_all()
        db.create_all()
        
        # Criar usuário de teste
        test_user = User(
            hotmart_id='test_123',
            name='Usuário Teste',
            email='teste@moedor.com'
        )
        db.session.add(test_user)
        
        # Criar verdades constrangedoras de exemplo
        truths = [
            EmbarrassingTruth(
                content="Você já chorou assistindo um comercial de margarina.",
                target_member="Apresentador 1"
            ),
            EmbarrassingTruth(
                content="Você já fingiu que estava dormindo para não ter que levantar e ir ao banheiro.",
                target_member="Apresentador 2"
            ),
            EmbarrassingTruth(
                content="Você já conversou sozinho no espelho e perdeu a discussão.",
                target_member="Apresentador 3"
            ),
            EmbarrassingTruth(
                content="Você já tentou impressionar alguém mentindo sobre algo completamente idiota.",
                target_member="Apresentador 1"
            ),
            EmbarrassingTruth(
                content="Você já teve medo de um desenho animado quando era criança.",
                target_member="Apresentador 2"
            )
        ]
        
        for truth in truths:
            db.session.add(truth)
        
        # Criar mensagens de boas-vindas de exemplo
        welcome_messages = [
            WelcomeMessage(template="Bem-vindo, {name}, seu arrombado!"),
            WelcomeMessage(template="Olha quem chegou, {name}! Prepare-se para o caos!"),
            WelcomeMessage(template="Eita, {name}! Mais um corajoso entrou no moedor!"),
            WelcomeMessage(template="Salve, {name}! Agora a coisa vai ficar interessante!"),
            WelcomeMessage(template="Opa, {name}! Bem-vindo ao inferno do humor!")
        ]
        
        for msg in welcome_messages:
            db.session.add(msg)
        
        # Criar câmeras de exemplo
        cameras = [
            Camera(
                name="Estúdio Principal",
                rtsp_url="rtsp://example.com/camera1",
                position_x=0,
                position_y=0,
                width=640,
                height=480
            ),
            Camera(
                name="Bancada",
                rtsp_url="rtsp://example.com/camera2",
                position_x=650,
                position_y=0,
                width=640,
                height=480
            ),
            Camera(
                name="Plateia",
                rtsp_url="rtsp://example.com/camera3",
                position_x=0,
                position_y=490,
                width=640,
                height=480
            ),
            Camera(
                name="Câmera Geral",
                rtsp_url="rtsp://example.com/camera4",
                position_x=650,
                position_y=490,
                width=640,
                height=480
            )
        ]
        
        for camera in cameras:
            db.session.add(camera)
        
        # Salvar tudo
        db.session.commit()
        
        print("✅ Dados de teste criados com sucesso!")
        print(f"📧 Email de teste: {test_user.email}")
        print(f"🎭 {len(truths)} verdades constrangedoras criadas")
        print(f"👋 {len(welcome_messages)} mensagens de boas-vindas criadas")
        print(f"📹 {len(cameras)} câmeras configuradas")

if __name__ == '__main__':
    create_test_data()

