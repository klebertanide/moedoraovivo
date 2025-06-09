from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    hotmart_id = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    
    # Relacionamentos
    messages = db.relationship('Message', backref='user', lazy=True)
    donations = db.relationship('Donation', backref='user', lazy=True)
    poll_votes = db.relationship('PollVote', backref='user', lazy=True)
    
    def __repr__(self):
        return f'<User {self.name}>'

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    fake_name = db.Column(db.String(50), nullable=False)
    content = db.Column(db.Text, nullable=False)
    likes_count = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    displayed_at = db.Column(db.DateTime, nullable=True)
    is_displayed = db.Column(db.Boolean, default=False)
    
    def __repr__(self):
        return f'<Message {self.fake_name}: {self.content[:50]}>'

class EmbarrassingTruth(db.Model):
    __tablename__ = 'embarrassing_truths'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    target_member = db.Column(db.String(100), nullable=False)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    times_used = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<EmbarrassingTruth for {self.target_member}>'

class WelcomeMessage(db.Model):
    __tablename__ = 'welcome_messages'
    
    id = db.Column(db.Integer, primary_key=True)
    template = db.Column(db.Text, nullable=False)  # Ex: "Bem-vindo, {name}, seu arrombado"
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_active = db.Column(db.Boolean, default=True)
    times_used = db.Column(db.Integer, default=0)
    
    def __repr__(self):
        return f'<WelcomeMessage: {self.template[:50]}>'

class Poll(db.Model):
    __tablename__ = 'polls'
    
    id = db.Column(db.Integer, primary_key=True)
    question = db.Column(db.Text, nullable=False)
    option_a = db.Column(db.String(200), nullable=False)
    option_b = db.Column(db.String(200), nullable=False)
    votes_a = db.Column(db.Integer, default=0)
    votes_b = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    ends_at = db.Column(db.DateTime, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    is_automatic = db.Column(db.Boolean, default=False)  # Gerada automaticamente pelo Whisper
    
    # Relacionamentos
    votes = db.relationship('PollVote', backref='poll', lazy=True)
    
    def __repr__(self):
        return f'<Poll: {self.question[:50]}>'

class PollVote(db.Model):
    __tablename__ = 'poll_votes'
    
    id = db.Column(db.Integer, primary_key=True)
    poll_id = db.Column(db.Integer, db.ForeignKey('polls.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    option = db.Column(db.String(1), nullable=False)  # 'A' ou 'B'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Constraint para evitar voto duplo
    __table_args__ = (db.UniqueConstraint('poll_id', 'user_id', name='unique_poll_vote'),)

class Donation(db.Model):
    __tablename__ = 'donations'
    
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    payment_id = db.Column(db.String(100), unique=True, nullable=False)
    status = db.Column(db.String(20), default='pending')  # pending, approved, rejected
    donation_type = db.Column(db.String(20), default='free')  # free, embarrassing
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    processed_at = db.Column(db.DateTime, nullable=True)
    
    def __repr__(self):
        return f'<Donation R$ {self.amount} - {self.status}>'

class Transcription(db.Model):
    __tablename__ = 'transcriptions'
    
    id = db.Column(db.Integer, primary_key=True)
    content = db.Column(db.Text, nullable=False)
    start_time = db.Column(db.DateTime, nullable=False)
    end_time = db.Column(db.DateTime, nullable=False)
    polemic_score = db.Column(db.Float, default=0.0)  # Score de polêmica (0-1)
    polemic_keywords = db.Column(db.Text, nullable=True)  # JSON com palavras encontradas
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Transcription {self.start_time} - Score: {self.polemic_score}>'

class Camera(db.Model):
    __tablename__ = 'cameras'
    
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    rtsp_url = db.Column(db.String(500), nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    position_x = db.Column(db.Integer, default=0)
    position_y = db.Column(db.Integer, default=0)
    width = db.Column(db.Integer, default=320)
    height = db.Column(db.Integer, default=240)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    def __repr__(self):
        return f'<Camera {self.name}>'

class LiveSession(db.Model):
    __tablename__ = 'live_sessions'
    
    id = db.Column(db.Integer, primary_key=True)
    youtube_url = db.Column(db.String(500), nullable=False)
    started_at = db.Column(db.DateTime, default=datetime.utcnow)
    ended_at = db.Column(db.DateTime, nullable=True)
    is_active = db.Column(db.Boolean, default=True)
    embarrassing_count = db.Column(db.Integer, default=0)  # Contador de vergonhas usadas
    total_viewers = db.Column(db.Integer, default=0)
    total_messages = db.Column(db.Integer, default=0)
    total_donations = db.Column(db.Float, default=0.0)
    
    def __repr__(self):
        return f'<LiveSession {self.started_at}>'

class MessageLike(db.Model):
    __tablename__ = 'message_likes'
    
    id = db.Column(db.Integer, primary_key=True)
    message_id = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Constraint para evitar like duplo
    __table_args__ = (db.UniqueConstraint('message_id', 'user_id', name='unique_message_like'),)

class FunnyFace(db.Model):
    __tablename__ = 'funny_faces'
    
    id = db.Column(db.Integer, primary_key=True)
    image_path = db.Column(db.String(500), nullable=False)
    original_frame_path = db.Column(db.String(500), nullable=False)
    camera_id = db.Column(db.Integer, db.ForeignKey('cameras.id'), nullable=True)
    detected_at = db.Column(db.DateTime, default=datetime.utcnow)
    expression_type = db.Column(db.String(50), nullable=True)  # happy, surprised, etc.
    confidence_score = db.Column(db.Float, default=0.0)
    
    def __repr__(self):
        return f'<FunnyFace {self.expression_type} - {self.confidence_score}>'

