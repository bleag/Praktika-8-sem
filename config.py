import os

class Config:
    SECRET_KEY = 'sovcombank-secret-key-2026'
    SQLALCHEMY_DATABASE_URI  = 'postgresql://orlov_andrey_knowledge_base:123@localhost:5432/myquiz_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False