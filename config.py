import os

class Config:
    SECRET_KEY = 'secret-key-12345'
    
    # Используем нового пользователя
    SQLALCHEMY_DATABASE_URI = 'postgresql://quiz_user:quiz123@localhost:5432/myquiz_db'
    
    SQLALCHEMY_TRACK_MODIFICATIONS = False