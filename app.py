from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Quiz, Question
import datetime
import random
import string



app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()

def generate_quiz_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Quiz.query.filter_by(quiz_code=code).first():
            return code

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
    quizzes = Quiz.query.filter_by(owner_id=user.id).order_by(Quiz.updated_at.desc()).all()
    return render_template('profile.html', user=user, quizzes=quizzes)

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
    return render_template('quiz_editor_simple.html', user=user, quiz=None)


@app.route('/quiz/edit/<int:quiz_id>')
def edit_quiz(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    user = User.query.get(session['user_id'])
    quiz = Quiz.query.filter_by(id=quiz_id, owner_id=user.id).first_or_404()
    return render_template('quiz_editor_simple.html', user=user, quiz=quiz)

@app.route('/api/quiz/save', methods=['POST'])
def save_quiz_settings():
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    data = request.get_json()
    quiz_id = data.get('quiz_id')
    
    settings = {
        'description': data.get('description', ''),
        'startDate': data.get('startDate', ''),
        'startTime': data.get('startTime', ''),
        'autoStart': data.get('autoStart', False),
        'showCountdown': data.get('showCountdown', False),
        'countdownDuration': data.get('countdownDuration', 6),
        'timePerQuestion': data.get('timePerQuestion', 25),
        'timeShowAnswer': data.get('timeShowAnswer', 10),
        'accessType': data.get('accessType', 'public'),
        'accessPassword': data.get('accessPassword', ''),
        'gameMode': data.get('gameMode', 'multiplayer'),
        'hasPrizes': data.get('hasPrizes', False),
        'prizeWinnersCount': data.get('prizeWinnersCount', 1),
        'givePrizesToAll': data.get('givePrizesToAll', False),
        'customScoring': data.get('customScoring', False),
        'scoringSystem': data.get('scoringSystem'),
        'sameRewardValue': data.get('sameRewardValue', 100),
        'extraPointsForWinner': data.get('extraPointsForWinner', False),
        'winnerCount': data.get('winnerCount', 1),
        'hideLeaderboard': data.get('hideLeaderboard', False),
        'hideFromOrganizer': data.get('hideFromOrganizer', False),
        'hideFromPlayers': data.get('hideFromPlayers', False),
        'randomQuestions': data.get('randomQuestions', False),
        'randomOptions': data.get('randomOptions', False),
        'partOfCampaign': data.get('partOfCampaign', False),
        'promoOnWaiting': data.get('promoOnWaiting', False),
        'promoModalOnWaiting': data.get('promoModalOnWaiting', False),
        'promoOnLeaderboard': data.get('promoOnLeaderboard', False),
        'promoModalOnLeaderboard': data.get('promoModalOnLeaderboard', False)
    }
    
    if quiz_id:
        quiz = Quiz.query.filter_by(id=quiz_id, owner_id=session['user_id']).first()
        if not quiz:
            return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
        quiz.title = data.get('title')
        quiz.description = data.get('description', '')
        quiz.cover_data = data.get('coverImage')
        quiz.settings = settings
        quiz.updated_at = datetime.datetime.utcnow()
    else:
        quiz_code = generate_quiz_code()
        quiz = Quiz(
            quiz_code=quiz_code,
            owner_id=session['user_id'],
            title=data.get('title'),
            description=data.get('description', ''),
            cover_data=data.get('coverImage'),
            settings=settings
        )
        db.session.add(quiz)
    
    db.session.commit()
    return jsonify({'success': True, 'quiz_id': quiz.id, 'quiz_code': quiz.quiz_code})


@app.route('/api/quiz/<int:quiz_id>', methods=['GET'])
def get_quiz(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    quiz = Quiz.query.filter_by(id=quiz_id, owner_id=session['user_id']).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    return jsonify({
        'success': True,
        'quiz': {
            'id': quiz.id,
            'quiz_code': quiz.quiz_code,
            'title': quiz.title,
            'description': quiz.description,
            'coverImage': quiz.cover_data,
            **quiz.settings
        }
    })

@app.route('/api/quiz/<int:quiz_id>', methods=['DELETE'])
def delete_quiz(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    quiz = Quiz.query.filter_by(id=quiz_id, owner_id=session['user_id']).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    db.session.delete(quiz)
    db.session.commit()
    return jsonify({'success': True})


# Получить все вопросы викторины
@app.route('/api/quiz/<int:quiz_id>/questions', methods=['GET'])
def get_questions(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = Quiz.query.filter_by(id=quiz_id, owner_id=session['user_id']).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    
    questions = Question.query.filter_by(quiz_id=quiz_id).order_by(Question.order).all()
    return jsonify({
        'success': True,
        'questions': [{
            'id': q.id,
            'type': q.type,
            'text': q.text,
            'options': q.options,
            'correct_answer': q.correct_answer,
            'media_url': q.media_url,
            'order': q.order
        } for q in questions]
    })

# Сохранить вопрос
@app.route('/api/quiz/<int:quiz_id>/question', methods=['POST'])
def save_question(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = Quiz.query.filter_by(id=quiz_id, owner_id=session['user_id']).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    
    data = request.get_json()
    question_id = data.get('id')
    
    if question_id:
        question = Question.query.filter_by(id=question_id, quiz_id=quiz_id).first()
        if not question:
            return jsonify({'success': False, 'error': 'Вопрос не найден'}), 404
    else:
        question = Question(quiz_id=quiz_id)
        db.session.add(question)
    
    question.type = data.get('type')
    question.text = data.get('text')
    question.options = data.get('options')
    question.correct_answer = data.get('correct_answer')
    question.media_url = data.get('media_url')
    question.order = data.get('order', 0)
    
    db.session.commit()
    return jsonify({'success': True, 'question_id': question.id})

# Удалить вопрос
@app.route('/api/question/<int:question_id>', methods=['DELETE'])
def delete_question(question_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'success': False, 'error': 'Вопрос не найден'}), 404
    
    quiz = Quiz.query.filter_by(id=question.quiz_id, owner_id=session['user_id']).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    db.session.delete(question)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/question/<int:question_id>', methods=['GET'])
def get_question(question_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    question = Question.query.get(question_id)
    if not question:
        return jsonify({'success': False, 'error': 'Вопрос не найден'}), 404
    
    quiz = Quiz.query.filter_by(id=question.quiz_id, owner_id=session['user_id']).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    return jsonify({
        'success': True,
        'question': {
            'id': question.id,
            'type': question.type,
            'text': question.text,
            'options': question.options,
            'correct_answer': question.correct_answer,
            'media_url': question.media_url,
            'order': question.order
        }
    })

@app.route('/play/<code>')
def play_game(code):
    # Проверяем существует ли викторина
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return "Викторина не найдена", 404
    return render_template('game.html', quiz=quiz, code=code)
@app.route('/play/<code>/game')
def play_game_session(code):
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return "Викторина не найдена", 404
    return render_template('game_play.html', quiz=quiz)


@app.route('/solo/<int:quiz_id>')
def solo_game(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return "Викторина не найдена", 404
    return render_template('solo_game.html', quiz=quiz)


@app.route('/team/<int:quiz_id>')
def team_game(quiz_id):
    quiz = Quiz.query.get(quiz_id)
    if not quiz:
        return "Викторина не найдена", 404
    return render_template('team_game.html', quiz=quiz)


# Хранилище для команд
teams = {}  # team_code: {id, name, code, quiz_id, members, score}

@app.route('/api/team/create', methods=['POST'])
def create_team():
    data = request.get_json()
    quiz_id = data.get('quiz_id')
    team_name = data.get('team_name')
    
    import random
    import string
    team_code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
    
    team = {
        'id': len(teams) + 1,
        'name': team_name,
        'code': team_code,
        'quiz_id': quiz_id,
        'members': [],
        'score': 0
    }
    teams[team_code] = team
    
    return jsonify({'success': True, 'team': team})

@app.route('/api/team/join', methods=['POST'])
def join_team():
    data = request.get_json()
    team_code = data.get('team_code')
    player_name = data.get('player_name')
    
    if team_code not in teams:
        return jsonify({'success': False, 'error': 'Команда не найдена'})
    
    teams[team_code]['members'].append({'name': player_name})
    return jsonify({'success': True, 'team': teams[team_code]})

@app.route('/api/team/<team_code>/members', methods=['GET'])
def get_team_members(team_code):
    if team_code not in teams:
        return jsonify({'success': False, 'error': 'Команда не найдена'})
    return jsonify({'success': True, 'members': teams[team_code]['members']})

@app.route('/api/team/start', methods=['POST'])
def start_team_game():
    data = request.get_json()
    team_code = data.get('team_code')
    return jsonify({'success': True})

@app.route('/api/team/score', methods=['POST'])
def save_team_score():
    data = request.get_json()
    team_code = data.get('team_code')
    score = data.get('score')
    
    if team_code in teams:
        teams[team_code]['score'] = score
    return jsonify({'success': True})

@app.route('/api/team/<team_code>/leaderboard', methods=['GET'])
def get_team_leaderboard(team_code):
    if team_code not in teams:
        return jsonify({'success': False})
    
    quiz_id = teams[team_code]['quiz_id']
    # Все команды для этой викторины
    quiz_teams = [t for t in teams.values() if t['quiz_id'] == quiz_id]
    quiz_teams.sort(key=lambda x: x['score'], reverse=True)
    
    return jsonify({'success': True, 'teams': quiz_teams})

@app.route('/prices')
def prices():
    user = None
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
    return render_template('prices.html', user=user)

@app.route('/play')
def play_page():
    user = None
    if 'user_id' in session:
        user = db.session.get(User, session['user_id'])
        quizzes = Quiz.query.filter_by(owner_id=user.id).all()
    else:
        # Для гостей - все викторины
        quizzes = Quiz.query.all()
    return render_template('play.html', user=user, quizzes=quizzes)

if __name__ == '__main__':
    app.run(debug=True)