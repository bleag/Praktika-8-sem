from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()

# ========== СТРАНИЦЫ ==========
@app.route('/')
def index():
    user_id = session.get('user_id')
    user = None
    if user_id:
        user = User.query.get(user_id)
    return render_template('index.html', user=user)

@app.route('/login')
def login_page():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return render_template('login.html')

@app.route('/register')
def register_page():
    if 'user_id' in session:
        return redirect(url_for('profile'))
    return render_template('register.html')

@app.route('/profile')
def profile():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    user = User.query.get(session['user_id'])
    return render_template('profile.html', user=user)

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

# ========== API (AJAX) ==========
@app.route('/register', methods=['POST'])
def register():
    data = request.get_json()
    nickname = data.get('nickname')
    password = data.get('password')
    
    if not nickname or not password:
        return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
    
    if len(password) < 6:
        return jsonify({'success': False, 'error': 'Пароль должен быть не менее 6 символов'}), 400
    
    existing_user = User.query.filter_by(nickname=nickname).first()
    if existing_user:
        return jsonify({'success': False, 'error': 'Пользователь с таким ником уже существует'}), 400
    
    password_hash = generate_password_hash(password)
    new_user = User(nickname=nickname, password_hash=password_hash)
    db.session.add(new_user)
    db.session.commit()
    
    session['user_id'] = new_user.id
    session['nickname'] = new_user.nickname
    
    return jsonify({'success': True, 'nickname': new_user.nickname})

@app.route('/login', methods=['POST'])
def login():
    data = request.get_json()
    nickname = data.get('nickname')
    password = data.get('password')
    
    if not nickname or not password:
        return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
    
    user = User.query.filter_by(nickname=nickname).first()
    
    if not user or not check_password_hash(user.password_hash, password):
        return jsonify({'success': False, 'error': 'Неверный ник или пароль'}), 400
    
    session['user_id'] = user.id
    session['nickname'] = user.nickname
    
    return jsonify({'success': True, 'nickname': user.nickname})

# ========== ВРЕМЕННЫЕ ЗАГЛУШКИ ==========
@app.route('/quiz/create')
def create_quiz():
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    user = User.query.get(session['user_id'])
    return render_template('quiz_editor.html', user=user)

@app.route('/api/quiz/save', methods=['POST'])
def save_quiz_settings():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    data = request.get_json()
    print("Сохранены настройки:", data)
    
    # TODO: Сохранять в БД (когда добавим модель Quiz)
    
    return jsonify({'success': True})

@app.route('/play/<code>')
def play_game(code):
    return f'<h1>Игра по коду: {code}</h1><p>Страница игры будет реализована позже</p><a href="/">На главную</a>'

@app.route('/prices')
def prices():
    return '<h1>Цены</h1><p>Страница в разработке</p><a href="/">На главную</a>'

@app.route('/play/demo')
def demo_play():
    return '<h1>Демо-игра</h1><p>Страница в разработке</p><a href="/">На главную</a>'

if __name__ == '__main__':
    app.run(debug=True)