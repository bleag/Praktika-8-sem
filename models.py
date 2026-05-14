from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    nickname = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime)

class Quiz(db.Model):
    __tablename__ = 'quizzes'
    id = db.Column(db.Integer, primary_key=True)
    quiz_code = db.Column(db.String(6), unique=True, nullable=False)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(150), nullable=False)
    description = db.Column(db.String(800), nullable=True)
    cover_data = db.Column(db.Text, nullable=True)
    settings = db.Column(db.JSON, default=dict)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    owner = db.relationship('User', backref='quizzes')


class Question(db.Model):
    __tablename__ = 'questions'
    id = db.Column(db.Integer, primary_key=True)
    quiz_id = db.Column(db.Integer, db.ForeignKey('quizzes.id'), nullable=False)
    round_id = db.Column(db.Integer, nullable=True)  # для группировки в раунды
    type = db.Column(db.String(30), nullable=False)  # choice, open, wordcloud и т.д.
    text = db.Column(db.Text, nullable=False)  # текст вопроса
    options = db.Column(db.JSON, nullable=True)  # варианты ответов (для choice)
    correct_answer = db.Column(db.JSON, nullable=True)  # правильный ответ
    media_url = db.Column(db.String(500), nullable=True)  # картинка/видео
    order = db.Column(db.Integer, default=0)  # порядок показа
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    quiz = db.relationship('Quiz', backref='questions')