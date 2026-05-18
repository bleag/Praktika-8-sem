from app import app, db
from sqlalchemy import text

with app.app_context():
    db.session.execute(text("DROP TABLE IF EXISTS questions CASCADE"))
    db.session.commit()
    print("✅ Таблица questions удалена")
    
    db.create_all()
    print("✅ Таблицы пересозданы")

print("Готово!")