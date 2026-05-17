from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from config import Config
from models import db, User, Quiz, Question, GameResult
from datetime import datetime, timezone
import random
import string
import time

app = Flask(__name__)
app.config.from_object(Config)

db.init_app(app)

with app.app_context():
    db.create_all()

# Хранилище активных игр
game_sessions = {}
# Хранилище командных игр
team_games = {}

def generate_quiz_code():
    while True:
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        if not Quiz.query.filter_by(quiz_code=code).first():
            return code

def check_quizmaster_access(code):
    if 'user_id' not in session:
        return None, {'success': False, 'error': 'Не авторизован'}, 401
    
    if code not in game_sessions:
        return None, {'success': False, 'error': 'Игра не найдена'}, 404
    
    quiz = db.session.get(Quiz, game_sessions[code]['quiz_id'])
    if not quiz or quiz.owner_id != session['user_id']:
        return None, {'success': False, 'error': 'Нет доступа'}, 403
    
    return quiz, None, None


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


# ========== API АВТОРИЗАЦИИ ==========
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


# ========== РЕДАКТОР ВИКТОРИН ==========
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
    
    try:
        data = request.get_json()
        if not data:
            return jsonify({'success': False, 'error': 'Нет данных'}), 400
        
        quiz_id = data.get('quiz_id')
        
        settings = {
            'description': data.get('description', ''),
            'startDate': data.get('startDate', ''),
            'startTime': data.get('startTime', ''),
            'autoStart': data.get('autoStart', False),
            'timePerQuestion': data.get('timePerQuestion', 25),
            'timeShowAnswer': data.get('timeShowAnswer', 10),
            'accessType': data.get('accessType', 'public'),
            'accessPassword': data.get('accessPassword', ''),
            'gameMode': data.get('gameMode', 'multiplayer'),
            'allowReplay': data.get('allowReplay', False),
            'allowReplaySolo': data.get('allowReplaySolo', False),
            'customScoring': data.get('customScoring', False),
            'customPointsPerQuestion': data.get('customPointsPerQuestion', False),
            'pointsPerQuestion': data.get('pointsPerQuestion', 100),
            'randomQuestions': data.get('randomQuestions', False),
            'randomOptions': data.get('randomOptions', False)
        }
        
        if quiz_id:
            quiz = Quiz.query.filter_by(id=quiz_id, owner_id=session['user_id']).first()
            if not quiz:
                return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
            quiz.title = data.get('title')
            quiz.description = data.get('description', '')
            quiz.cover_data = data.get('coverImage')
            quiz.settings = settings
            quiz.updated_at = datetime.now(timezone.utc)
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
    
    except Exception as e:
        print(f"Ошибка при сохранении: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/quiz/<int:quiz_id>', methods=['GET'])
def get_quiz(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    quiz = db.session.get(Quiz, quiz_id)
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
            'is_closed': quiz.settings.get('is_closed', False) if quiz.settings else False,
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

@app.route('/api/public/quiz/<int:quiz_id>/questions', methods=['GET'])
def get_public_questions(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
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


# ========== ПАНЕЛЬ ВЕДУЩЕГО (МУЛЬТИПЛЕЕР) ==========

@app.route('/quizmaster/<code>')
def quizmaster_panel(code):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return "Викторина не найдена", 404
    
    if quiz.owner_id != session['user_id']:
        return "У вас нет доступа", 403
    
    if code not in game_sessions:
        settings = quiz.settings or {}
        time_per_question = int(settings.get('timePerQuestion', 25))
        time_show_answer = int(settings.get('timeShowAnswer', 10))
        allow_replay = settings.get('allowReplay', False)
        
        game_sessions[code] = {
            'quiz_id': quiz.id,
            'players': [],
            'current_index': 0,
            'status': 'waiting',
            'show_answer': False,
            'answer_end_time': None,
            'players_answers': {},
            'time_per_question': time_per_question,
            'time_show_answer': time_show_answer,
            'game_end_time': None,
            'questions_shuffled': False,
            'shuffled_questions': None,
            'allow_replay': allow_replay,
            'manual_start_required': False
        }
    
    return render_template('quizmaster.html', quiz=quiz, code=code)

@app.route('/api/quizmaster/<code>/join', methods=['POST'])
def api_quizmaster_join(code):
    data = request.get_json()
    nickname = data.get('nickname')
    password = data.get('password', '')
    
    if code not in game_sessions:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    
    session_data = game_sessions[code]
    quiz = Quiz.query.get(session_data['quiz_id'])
    settings = quiz.settings or {}
    
    if settings.get('accessType') == 'password':
        expected_password = settings.get('accessPassword', '')
        if password != expected_password:
            return jsonify({'success': False, 'error': 'Неверный пароль'}), 400
    
    if session_data['status'] != 'waiting':
        return jsonify({'success': False, 'error': 'Игра уже началась'}), 400
    
    existing = [p for p in session_data['players'] if p['nickname'] == nickname]
    if existing:
        return jsonify({'success': False, 'error': 'Никнейм уже занят'}), 400
    
    if len(session_data['players']) >= 35:
        return jsonify({'success': False, 'error': 'Достигнут лимит бесплатного тарифа (35 игроков).'}), 400
    
    session_data['players'].append({'nickname': nickname, 'score': 0})
    
    return jsonify({'success': True, 'players': session_data['players']})

@app.route('/api/quizmaster/<code>/players', methods=['GET'])
def api_quizmaster_players(code):
    if code not in game_sessions:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    return jsonify({'success': True, 'players': game_sessions[code]['players']})

@app.route('/api/quizmaster/<code>/start', methods=['POST'])
def api_quizmaster_start(code):
    quiz, error, status = check_quizmaster_access(code)
    if error:
        return jsonify(error), status
    
    session_data = game_sessions[code]
    
    if len(session_data['players']) == 0:
        return jsonify({'success': False, 'error': 'Нет игроков'}), 400
    
    if session_data['status'] != 'waiting':
        return jsonify({'success': False, 'error': 'Игра уже началась'}), 400
    
    session_data['status'] = 'active'
    session_data['current_index'] = 0
    session_data['show_answer'] = False
    session_data['players_answers'] = {}
    
    now = time.time()
    session_data['answer_end_time'] = now + session_data['time_per_question']
    
    return jsonify({'success': True})

@app.route('/api/quizmaster/<code>/pause', methods=['POST'])
def api_quizmaster_pause(code):
    quiz, error, status = check_quizmaster_access(code)
    if error:
        return jsonify(error), status
    
    session_data = game_sessions[code]
    
    if session_data['status'] != 'active':
        return jsonify({'success': False, 'error': 'Игра не активна'}), 400
    
    session_data['status'] = 'paused'
    return jsonify({'success': True})

@app.route('/api/quizmaster/<code>/resume', methods=['POST'])
def api_quizmaster_resume(code):
    quiz, error, status = check_quizmaster_access(code)
    if error:
        return jsonify(error), status
    
    session_data = game_sessions[code]
    
    if session_data['status'] != 'paused':
        return jsonify({'success': False, 'error': 'Игра не на паузе'}), 400
    
    session_data['status'] = 'active'
    
    now = time.time()
    if session_data['answer_end_time']:
        time_left = session_data['answer_end_time'] - session_data['answer_start_time'] if 'answer_start_time' in session_data else session_data['time_per_question']
        session_data['answer_end_time'] = now + max(0, time_left)
    session_data['answer_start_time'] = now
    
    return jsonify({'success': True})

@app.route('/api/quizmaster/<code>/stop', methods=['POST'])
def api_quizmaster_stop(code):
    quiz, error, status = check_quizmaster_access(code)
    if error:
        return jsonify(error), status
    
    session_data = game_sessions[code]
    quiz_obj = Quiz.query.get(session_data['quiz_id'])
    questions_list = Question.query.filter_by(quiz_id=quiz_obj.id).all()
    total_questions = len(questions_list)
    
    print(f"=== СОХРАНЕНИЕ МУЛЬТИПЛЕЕРА ===")
    print(f"Код игры: {code}")
    print(f"Игроков в сессии: {len(session_data['players'])}")
    
    saved_count = 0
    for player in session_data['players']:
        print(f"  - Обработка: {player['nickname']}, счёт: {player['score']}")
        
        try:
            new_result = GameResult(
                quiz_id=session_data['quiz_id'],
                quiz_code=quiz_obj.quiz_code,
                player_name=player['nickname'],
                score=player['score'],
                correct_answers=0,
                total_questions=total_questions,
                mode='multiplayer',
                finished_at=datetime.now(timezone.utc)
            )
            db.session.add(new_result)
            saved_count += 1
            print(f"    ✅ Добавлен в сессию БД")
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
    
    try:
        db.session.commit()
        print(f"=== СОХРАНЕНО В БД: {saved_count} ИГРОКОВ ===")
    except Exception as e:
        print(f"❌ ОШИБКА COMMIT: {e}")
        db.session.rollback()
    
    game_sessions[code]['status'] = 'finished'
    
    return jsonify({'success': True})

@app.route('/api/quizmaster/<code>/status', methods=['GET'])
def api_quizmaster_status(code):
    if code not in game_sessions:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

    session = game_sessions[code]
    quiz = Quiz.query.get(session['quiz_id'])
    all_questions = Question.query.filter_by(quiz_id=quiz.id).order_by(Question.order).all()
    now = time.time()

    settings = quiz.settings or {}
    time_per_question = int(settings.get('timePerQuestion', 25))
    time_show_answer = int(settings.get('timeShowAnswer', 10))
    points_per_question = int(settings.get('pointsPerQuestion', 100))
    random_questions = settings.get('randomQuestions', False)
    random_options = settings.get('randomOptions', False)
    winner_count = int(settings.get('prizeWinnersCount', 3))
    show_leaderboard = not settings.get('hideFromPlayers', False)
    auto_start = settings.get('autoStart', False)
    allow_replay = settings.get('allowReplay', False)
    manual_start_required = session.get('manual_start_required', False)

    if session.get('shuffled_questions') is None:
        if random_questions:
            import random
            shuffled = all_questions.copy()
            random.shuffle(shuffled)
            session['shuffled_questions'] = shuffled
        else:
            session['shuffled_questions'] = all_questions

    questions = session['shuffled_questions']

    start_datetime_str = None
    start_date = settings.get('startDate', '')
    start_time_str = settings.get('startTime', '')
    if start_date and start_time_str:
        start_datetime_str = f"{start_date} {start_time_str}"

    if session['status'] == 'waiting' and auto_start and not manual_start_required:
        if start_date and start_time_str:
            try:
                start_ts = datetime.strptime(f"{start_date} {start_time_str}", "%Y-%m-%d %H:%M").timestamp()
                if now >= start_ts:
                    session['status'] = 'active'
                    session['current_index'] = 0
                    session['show_answer'] = False
                    session['players_answers'] = {}
                    session['answer_end_time'] = None
                    session['manual_start_required'] = False
            except:
                pass

    if session['status'] == 'active':
        if session.get('answer_end_time') is None and not session.get('show_answer'):
            session['answer_end_time'] = now + time_per_question
            session['players_answers'] = {}

        if not session.get('show_answer') and session.get('answer_end_time') and now >= session['answer_end_time']:
            if session['current_index'] < len(questions):
                current_q = questions[session['current_index']]
                for player in session['players']:
                    nickname = player['nickname']
                    if nickname in session['players_answers']:
                        answer = session['players_answers'][nickname]
                        if current_q.type == 'choice' and current_q.correct_answer:
                            if answer in current_q.correct_answer:
                                player['score'] += points_per_question
            session['show_answer'] = True
            session['answer_end_time'] = now + time_show_answer

        elif session.get('show_answer') and session.get('answer_end_time') and now >= session['answer_end_time']:
            session['current_index'] += 1
            session['show_answer'] = False
            session['answer_end_time'] = None
            session['players_answers'] = {}

            if session['current_index'] >= len(questions):
                session['status'] = 'finished'
                session['game_end_time'] = now
                
                # ===== СОХРАНЯЕМ РЕЗУЛЬТАТЫ В БД =====
                print(f"=== ИГРА ОКОНЧЕНА, СОХРАНЯЕМ РЕЗУЛЬТАТЫ ===")
                total_questions = len(questions)
                
                for player in session['players']:
                    existing = GameResult.query.filter_by(
                        quiz_id=session['quiz_id'],
                        quiz_code=code,
                        player_name=player['nickname'],
                        mode='multiplayer'
                    ).first()
                    
                    if not existing:
                        result = GameResult(
                            quiz_id=session['quiz_id'],
                            quiz_code=code,
                            player_name=player['nickname'],
                            score=player['score'],
                            correct_answers=0,
                            total_questions=total_questions,
                            mode='multiplayer',
                            finished_at=datetime.now(timezone.utc)
                        )
                        db.session.add(result)
                        print(f"  ✅ Сохранён: {player['nickname']} - {player['score']} баллов")
                    else:
                        print(f"  ⚠️ Уже есть: {player['nickname']}")
                
                db.session.commit()
                print(f"=== СОХРАНЕНО {len(session['players'])} ИГРОКОВ В БД ===")

    current_question = None
    if session['status'] == 'active' and session['current_index'] < len(questions):
        q = questions[session['current_index']]
        opts = q.options
        if random_options and opts:
            import random
            opts = random.sample(opts, len(opts))
        current_question = {
            'id': q.id,
            'text': q.text,
            'type': q.type,
            'options': opts,
            'correct_answer': q.correct_answer if session.get('show_answer') else None
        }

    time_left = None
    if session['status'] == 'active' and session.get('answer_end_time'):
        time_left = max(0, int(session['answer_end_time'] - now))

    sorted_players = sorted(session['players'], key=lambda x: x['score'], reverse=True)
    winners = sorted_players[:winner_count] if winner_count > 0 else []

    show_final_results = False
    if session['status'] == 'finished' and session.get('game_end_time'):
        if now - session['game_end_time'] < 6:
            show_final_results = True

    need_password = settings.get('accessType') == 'password'

    return jsonify({
        'success': True,
        'status': session['status'],
        'current_question': current_question,
        'question_index': session['current_index'],
        'total_questions': len(questions),
        'show_answer': session.get('show_answer', False),
        'players': session['players'],
        'sorted_players': sorted_players,
        'time_left': time_left,
        'time_per_question': time_per_question,
        'time_show_answer': time_show_answer,
        'show_leaderboard_to_players': show_leaderboard,
        'winners': [{'nickname': p['nickname'], 'score': p['score']} for p in winners],
        'start_datetime': start_datetime_str,
        'show_final_results': show_final_results,
        'points_per_question': points_per_question,
        'need_password': need_password,
        'auto_start': auto_start,
        'allow_replay': allow_replay
    })

@app.route('/api/quizmaster/<code>/answer', methods=['POST'])
def api_quizmaster_answer(code):
    data = request.get_json()
    nickname = data.get('nickname')
    answer = data.get('answer')

    if code not in game_sessions:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404

    session = game_sessions[code]

    if session['status'] != 'active':
        return jsonify({'success': False, 'error': 'Игра не активна'}), 400

    if session.get('show_answer'):
        return jsonify({'success': False, 'error': 'Время ответа истекло'}), 400

    if nickname not in session.get('players_answers', {}):
        session.setdefault('players_answers', {})[nickname] = answer

    return jsonify({
        'success': True,
        'message': 'Ответ сохранён'
    })

@app.route('/api/quizmaster/<code>/replay', methods=['POST'])
def api_quizmaster_replay(code):
    quiz, error, status = check_quizmaster_access(code)
    if error:
        return jsonify(error), status
    
    old_session = game_sessions[code]
    quiz_obj = Quiz.query.get(old_session['quiz_id'])
    settings = quiz_obj.settings or {}
    time_per_question = int(settings.get('timePerQuestion', 25))
    time_show_answer = int(settings.get('timeShowAnswer', 10))
    allow_replay = settings.get('allowReplay', False)
    
    new_session = {
        'quiz_id': old_session['quiz_id'],
        'players': [],
        'current_index': 0,
        'status': 'waiting',
        'show_answer': False,
        'answer_end_time': None,
        'players_answers': {},
        'time_per_question': time_per_question,
        'time_show_answer': time_show_answer,
        'game_end_time': None,
        'questions_shuffled': False,
        'shuffled_questions': None,
        'allow_replay': allow_replay,
        'manual_start_required': True
    }
    
    game_sessions[code] = new_session
    
    return jsonify({'success': True})




# ========== ИГРОВЫЕ СТРАНИЦЫ ==========
@app.route('/play/<code>')
def play_game(code):
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return "Викторина не найдена", 404
    return render_template('game.html', quiz=quiz, code=code)

@app.route('/prices')
def prices():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
    return render_template('prices.html', user=user)

@app.route('/play')
def play_page():
    user = None
    if 'user_id' in session:
        user = User.query.get(session['user_id'])
        quizzes = Quiz.query.filter_by(owner_id=user.id).all()
    else:
        quizzes = Quiz.query.all()
    return render_template('play.html', user=user, quizzes=quizzes)

@app.route('/api/quizmaster/<code>/history', methods=['GET'])
def quizmaster_get_history(code):
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    
    if 'user_id' not in session or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    results = GameResult.query.filter_by(quiz_id=quiz.id)\
        .order_by(GameResult.finished_at.desc()).limit(50).all()
    
    return jsonify({
        'success': True,
        'history': [{
            'quiz_code': r.quiz_code,
            'player_name': r.player_name,
            'score': r.score,
            'mode': r.mode,
            'finished_at': r.finished_at.strftime('%d.%m.%Y %H:%M')
        } for r in results]
    })

@app.route('/api/public/quiz/<int:quiz_id>/status', methods=['GET'])
def public_quiz_status(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    
    settings = quiz.settings or {}
    is_closed = settings.get('is_closed', False)
    allow_replay_solo = settings.get('allowReplaySolo', False)
    time_show_answer = int(settings.get('timeShowAnswer', 10))
    random_questions = settings.get('randomQuestions', False)
    random_options = settings.get('randomOptions', False)
    points_per_question = int(settings.get('pointsPerQuestion', 100))
    
    return jsonify({
        'success': True,
        'is_closed': is_closed,
        'allowReplaySolo': allow_replay_solo,
        'timeShowAnswer': time_show_answer,
        'randomQuestions': random_questions,
        'randomOptions': random_options,
        'pointsPerQuestion': points_per_question
    })


# ========== СОЛО РЕЖИМ ==========

# Хранилище статусов соло игр (в памяти)
solo_games_status = {}  # quiz_id: {'is_closed': bool}
solo_active_games = {}  # quiz_id: {'active': bool, 'paused': bool, 'current_q': int, 'questions': list, 'show_answer': bool, 'start_time': float}

@app.route('/api/solo/<int:quiz_id>/save', methods=['POST'])
def solo_save_result(quiz_id):
    data = request.get_json()
    player_name = data.get('player_name')
    score = data.get('score', 0)
    total_questions = data.get('total_questions', 0)
    correct_answers = data.get('correct_answers', 0)
    
    if not player_name:
        return jsonify({'success': False, 'error': 'Имя игрока не указано'}), 400
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    
    settings = quiz.settings or {}
    allow_replay_solo = settings.get('allowReplaySolo', False)
    
    if allow_replay_solo:
        old_result = GameResult.query.filter_by(
            quiz_id=quiz_id, 
            player_name=player_name,
            mode='solo'
        ).first()
        if old_result:
            db.session.delete(old_result)
    
    result = GameResult(
        quiz_id=quiz_id,
        quiz_code=quiz.quiz_code,
        player_name=player_name,
        score=score,
        correct_answers=correct_answers,
        total_questions=total_questions,
        mode='solo',
        finished_at=datetime.now(timezone.utc)
    )
    db.session.add(result)
    db.session.commit()
    
    return jsonify({'success': True, 'result_id': result.id})

@app.route('/api/solo/<int:quiz_id>/leaderboard', methods=['GET'])
def solo_get_leaderboard(quiz_id):
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    
    results = GameResult.query.filter_by(quiz_id=quiz_id, mode='solo')\
        .order_by(GameResult.score.desc())\
        .limit(20).all()
    
    return jsonify({
        'success': True,
        'leaderboard': [{
            'player_name': r.player_name,
            'score': r.score,
            'correct_answers': r.correct_answers,
            'total_questions': r.total_questions,
            'finished_at': r.finished_at.strftime('%d.%m.%Y %H:%M')
        } for r in results]
    })

@app.route('/api/solo/<int:quiz_id>/reset', methods=['POST'])
def solo_reset_result(quiz_id):
    data = request.get_json()
    player_name = data.get('player_name')
    
    if not player_name:
        return jsonify({'success': False, 'error': 'Имя игрока не указано'}), 400
    
    result = GameResult.query.filter_by(
        quiz_id=quiz_id, 
        player_name=player_name,
        mode='solo'
    ).first()
    
    if result:
        db.session.delete(result)
        db.session.commit()
    
    return jsonify({'success': True})

@app.route('/quizmaster/solo/<int:quiz_id>')
def quizmaster_solo_panel(quiz_id):
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return "Нет доступа", 403
    
    return render_template('quizmaster_solo.html', quiz=quiz)

# Управление доступом (открыть/закрыть)
@app.route('/api/solo/<int:quiz_id>/close', methods=['POST'])
def solo_close_access(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    solo_games_status[quiz_id] = {'is_closed': True}
    print(f"🔒 Викторина {quiz_id} ЗАКРЫТА")
    
    return jsonify({'success': True})

@app.route('/api/solo/<int:quiz_id>/open', methods=['POST'])
def solo_open_access(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    solo_games_status[quiz_id] = {'is_closed': False}
    print(f"🔓 Викторина {quiz_id} ОТКРЫТА")
    
    return jsonify({'success': True})

@app.route('/api/solo/<int:quiz_id>/status', methods=['GET'])
def solo_game_status(quiz_id):
    """Проверить доступна ли викторина для игры"""
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    
    is_closed = solo_games_status.get(quiz_id, {}).get('is_closed', False)
    
    return jsonify({
        'success': True,
        'is_closed': is_closed,
        'title': quiz.title
    })

# Управление активной игрой (Старт, Пауза, и т.д.)
@app.route('/api/solo/<int:quiz_id>/start-game', methods=['POST'])
def solo_start_game(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    questions = Question.query.filter_by(quiz_id=quiz_id).all()
    if not questions:
        return jsonify({'success': False, 'error': 'Нет вопросов в викторине'}), 400
    
    solo_active_games[quiz_id] = {
        'active': True,
        'paused': False,
        'current_q': 0,
        'questions': [{'id': q.id, 'text': q.text, 'options': q.options, 'correct_answer': q.correct_answer} for q in questions],
        'show_answer': False,
        'start_time': time.time()
    }
    
    return jsonify({'success': True})

@app.route('/api/solo/<int:quiz_id>/pause-game', methods=['POST'])
def solo_pause_game(quiz_id):
    if quiz_id in solo_active_games:
        solo_active_games[quiz_id]['paused'] = True
    return jsonify({'success': True})

@app.route('/api/solo/<int:quiz_id>/resume-game', methods=['POST'])
def solo_resume_game(quiz_id):
    if quiz_id in solo_active_games:
        solo_active_games[quiz_id]['paused'] = False
        solo_active_games[quiz_id]['start_time'] = time.time()
    return jsonify({'success': True})

@app.route('/api/solo/<int:quiz_id>/show-answer', methods=['POST'])
def solo_show_answer(quiz_id):
    if quiz_id in solo_active_games:
        solo_active_games[quiz_id]['show_answer'] = True
    return jsonify({'success': True})

@app.route('/api/solo/<int:quiz_id>/skip-question', methods=['POST'])
def solo_skip_question(quiz_id):
    if quiz_id in solo_active_games:
        solo_active_games[quiz_id]['current_q'] += 1
        solo_active_games[quiz_id]['show_answer'] = False
        solo_active_games[quiz_id]['start_time'] = time.time()
        
        # Проверяем конец игры
        if solo_active_games[quiz_id]['current_q'] >= len(solo_active_games[quiz_id]['questions']):
            solo_active_games[quiz_id]['active'] = False
    return jsonify({'success': True})

@app.route('/api/solo/<int:quiz_id>/current-question', methods=['GET'])
def solo_current_question(quiz_id):
    if quiz_id not in solo_active_games or not solo_active_games[quiz_id]['active']:
        return jsonify({'success': True, 'has_active_game': False})
    
    game = solo_active_games[quiz_id]
    
    if game['paused']:
        return jsonify({
            'success': True,
            'has_active_game': True,
            'is_paused': True,
            'current_question': None
        })
    
    if game['current_q'] >= len(game['questions']):
        game['active'] = False
        return jsonify({
            'success': True,
            'has_active_game': False,
            'is_finished': True
        })
    
    q = game['questions'][game['current_q']]
    time_left = max(0, 25 - int(time.time() - game['start_time']))
    
    return jsonify({
        'success': True,
        'has_active_game': True,
        'is_active': True,
        'current_question': {
            'text': q['text'],
            'options': q['options'],
            'correct_answer': q['correct_answer']
        },
        'time_left': time_left,
        'show_answer': game['show_answer'],
        'question_index': game['current_q'] + 1,
        'total_questions': len(game['questions'])
    })

# Общие API
@app.route('/api/quiz/by-code/<code>', methods=['GET'])
def get_quiz_by_code(code):
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
    return jsonify({'success': True, 'quiz_id': quiz.id, 'quiz_code': quiz.quiz_code})

@app.route('/solo/code/<code>')
def solo_game_by_code(code):
    """Одиночная игра по коду викторины"""
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return "Викторина не найдена", 404
    return render_template('solo_game.html', quiz=quiz)

# ========== КОМАНДНЫЙ РЕЖИМ (ПРАВИЛЬНАЯ ЛОГИКА) ==========

# Хранилище командных игр
team_games = {}  # game_code: {quiz_id, teams: {team_code: {name, members, score}}, status, current_q, questions}

@app.route('/api/team/join', methods=['POST'])
def team_join_simple():
    """Игрок присоединяется к команде"""
    data = request.get_json()
    game_code = data.get('game_code')
    team_name = data.get('team_name')
    player_name = data.get('player_name')
    
    if not game_code or not team_name or not player_name:
        return jsonify({'success': False, 'error': 'Заполните все поля'}), 400
    
    # Создаём игру если её нет
    if game_code not in team_games:
        quiz = Quiz.query.filter_by(quiz_code=game_code).first()
        if not quiz:
            return jsonify({'success': False, 'error': 'Викторина не найдена'}), 404
        questions = Question.query.filter_by(quiz_id=quiz.id).all()
        team_games[game_code] = {
            'quiz_id': quiz.id,
            'teams': {},
            'status': 'waiting',
            'current_q': 0,
            'questions': [{'id': q.id, 'text': q.text, 'options': q.options, 'correct_answer': q.correct_answer} for q in questions]
        }
    
    game = team_games[game_code]
    
    # Добавляем игрока в команду
    if team_name not in game['teams']:
        game['teams'][team_name] = {'members': [], 'score': 0}
    
    # Проверяем не входил ли уже
    for member in game['teams'][team_name]['members']:
        if member['name'] == player_name:
            return jsonify({'success': True, 'team_name': team_name})
    
    game['teams'][team_name]['members'].append({'name': player_name})
    
    return jsonify({'success': True, 'team_name': team_name})

@app.route('/api/team/status', methods=['GET'])
def team_status_simple():
    """Получить статус игры"""
    game_code = request.args.get('game_code')
    team_name = request.args.get('team_name')
    
    if game_code not in team_games:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    
    game = team_games[game_code]
    
    current_q = None
    if game['status'] == 'active' and game['current_q'] < len(game['questions']):
        q = game['questions'][game['current_q']]
        current_q = {
            'text': q['text'],
            'options': q['options']
        }
    
    team_score = game['teams'].get(team_name, {}).get('score', 0) if team_name else 0
    
    return jsonify({
        'success': True,
        'status': game['status'],
        'current_question': current_q,
        'question_index': game['current_q'],
        'total_questions': len(game['questions']),
        'team_score': team_score
    })

@app.route('/api/team/answer', methods=['POST'])
def team_answer_simple():
    """Ответ команды"""
    data = request.get_json()
    game_code = data.get('game_code')
    team_name = data.get('team_name')
    answer = data.get('answer')
    
    if game_code not in team_games:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    
    game = team_games[game_code]
    
    if game['status'] != 'active':
        return jsonify({'success': False, 'error': 'Игра не активна'}), 400
    
    # Проверяем ответ
    q = game['questions'][game['current_q']]
    is_correct = q['correct_answer'] and answer in q['correct_answer']
    
    if is_correct:
        game['teams'][team_name]['score'] += 100
    
    # Переход к следующему вопросу
    game['current_q'] += 1
    
    if game['current_q'] >= len(game['questions']):
        game['status'] = 'finished'
    
    return jsonify({
        'success': True,
        'correct': is_correct,
        'team_score': game['teams'][team_name]['score'],
        'game_finished': game['status'] == 'finished'
    })

@app.route('/api/team/leaderboard', methods=['GET'])
def team_leaderboard_simple():
    """Таблица команд"""
    game_code = request.args.get('game_code')
    
    if game_code not in team_games:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    
    game = team_games[game_code]
    
    teams_list = [{'name': name, 'score': team['score'], 'members_count': len(team['members'])} 
                  for name, team in game['teams'].items()]
    teams_list.sort(key=lambda x: x['score'], reverse=True)
    
    return jsonify({'success': True, 'teams': teams_list})

@app.route('/api/team/start', methods=['POST'])
def team_start_simple():
    """Начать игру (ведущий)"""
    data = request.get_json()
    game_code = data.get('game_code')
    
    if game_code not in team_games:
        return jsonify({'success': False, 'error': 'Игра не найдена'}), 404
    
    team_games[game_code]['status'] = 'active'
    team_games[game_code]['current_q'] = 0
    
    return jsonify({'success': True})


@app.route('/team/leader/<int:quiz_id>')
def team_leader(quiz_id):
    """Панель ведущего"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    quiz = Quiz.query.get(quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return "Нет доступа", 403
    return render_template('team_leader.html', quiz=quiz)

@app.route('/team/play/<code>')
def team_play(code):
    """Страница для игроков"""
    quiz = Quiz.query.filter_by(quiz_code=code).first()
    if not quiz:
        return "Викторина не найдена", 404
    return render_template('team_play.html', quiz=quiz, code=code)



@app.route('/api/team/pause', methods=['POST'])
def team_pause():
    """Поставить игру на паузу"""
    data = request.get_json()
    game_code = data.get('game_code')
    
    if game_code in team_games and team_games[game_code]['status'] == 'active':
        team_games[game_code]['status'] = 'paused'
    
    return jsonify({'success': True})

@app.route('/api/team/resume', methods=['POST'])
def team_resume():
    """Возобновить игру"""
    data = request.get_json()
    game_code = data.get('game_code')
    
    if game_code in team_games and team_games[game_code]['status'] == 'paused':
        team_games[game_code]['status'] = 'active'
    
    return jsonify({'success': True})

@app.route('/api/team/stop', methods=['POST'])
def team_stop():
    """Завершить игру"""
    data = request.get_json()
    game_code = data.get('game_code')
    
    if game_code in team_games:
        team_games[game_code]['status'] = 'finished'
    
    return jsonify({'success': True})


@app.route('/quiz/stats/<int:quiz_id>')
def quiz_stats(quiz_id):
    """Страница аналитики викторины"""
    if 'user_id' not in session:
        return redirect(url_for('login_page'))
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return "Нет доступа", 403
    
    # Получаем все результаты для этой викторины
    results = GameResult.query.filter_by(quiz_id=quiz_id).order_by(GameResult.score.desc()).all()
    
    # Базовая статистика
    total_players = len(results)
    avg_score = sum(r.score for r in results) / total_players if total_players > 0 else 0
    max_score = max((r.score for r in results), default=0)
    
    # Топ игроков
    top_players = results[:10]
    
    return render_template('quiz_stats.html', 
                          quiz=quiz, 
                          results=results,
                          total_players=total_players,
                          avg_score=round(avg_score, 1),
                          max_score=max_score,
                          top_players=top_players)


@app.route('/api/quiz/<int:quiz_id>/question-stats', methods=['GET'])
def get_question_stats_old(quiz_id):
    """Статистика по каждому вопросу викторины"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    # Получаем все вопросы
    questions = Question.query.filter_by(quiz_id=quiz_id).order_by(Question.order).all()
    
    # Получаем все результаты игроков (нужны для статистики ответов)
    results = GameResult.query.filter_by(quiz_id=quiz_id, mode='solo').all()
    
    # Здесь нужна будет дополнительная таблица для хранения ответов игроков
    # Пока сделаем базовую статистику
    
    question_stats = []
    for q in questions:
        # Считаем сколько раз отвечали на этот вопрос (из сохранённых ответов)
        # Для простоты пока считаем из GameResult (но там только общее кол-во)
        stats = {
            'question_id': q.id,
            'question_text': q.text[:100],
            'correct_answer': q.correct_answer[0] if q.correct_answer else '?',
            'total_attempts': len(results),
            'difficulty': 'medium'  # можно рассчитать позже
        }
        question_stats.append(stats)
    
    return jsonify({
        'success': True,
        'questions': question_stats,
        'total_players': len(results)
    })

@app.route('/api/quiz/<int:quiz_id>/multiplayer-stats', methods=['GET'])
def get_multiplayer_stats(quiz_id):
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    # Получаем ВСЕ мультиплеерные результаты
    results = GameResult.query.filter_by(quiz_id=quiz_id, mode='multiplayer').all()
    
    # Если нет результатов - вернуть пустые данные
    if not results:
        return jsonify({
            'success': True,
            'total_games': 0,
            'total_sessions': 0,
            'avg_players_per_session': 0,
            'avg_score': 0,
            'max_score': 0,
            'top_sessions': []
        })
    
    # Группируем по коду сессии
    sessions = {}
    for r in results:
        if r.quiz_code not in sessions:
            sessions[r.quiz_code] = {'players': [], 'total_score': 0, 'date': r.finished_at}
        sessions[r.quiz_code]['players'].append(r)
        sessions[r.quiz_code]['total_score'] += r.score
    
    total_sessions = len(sessions)
    avg_players_per_session = sum(len(s['players']) for s in sessions.values()) / total_sessions if total_sessions > 0 else 0
    
    top_sessions = sorted(sessions.items(), key=lambda x: len(x[1]['players']), reverse=True)[:5]
    
    return jsonify({
        'success': True,
        'total_games': len(results),
        'total_sessions': total_sessions,
        'avg_players_per_session': round(avg_players_per_session, 1),
        'avg_score': round(sum(r.score for r in results) / len(results), 1) if results else 0,
        'max_score': max((r.score for r in results), default=0),
        'top_sessions': [{'code': code, 'players_count': len(s['players']), 'total_score': s['total_score'], 'date': s['date'].strftime('%d.%m.%Y %H:%M') if s['date'] else '-'} for code, s in top_sessions]
    })


# ========== ОБЩАЯ АНАЛИТИКА ДЛЯ ВСЕХ РЕЖИМОВ ==========

@app.route('/api/quiz/<int:quiz_id>/all-results', methods=['GET'])
def get_all_results(quiz_id):
    """Получить все результаты викторины для указанного режима"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    mode = request.args.get('mode', 'all')
    
    if mode == 'all':
        results = GameResult.query.filter_by(quiz_id=quiz_id).order_by(GameResult.score.desc()).all()
    else:
        results = GameResult.query.filter_by(quiz_id=quiz_id, mode=mode).order_by(GameResult.score.desc()).all()
    
    return jsonify({
        'success': True,
        'results': [{
            'player_name': r.player_name,
            'score': r.score,
            'correct_answers': r.correct_answers,
            'total_questions': r.total_questions,
            'mode': r.mode,
            'finished_at': r.finished_at.strftime('%d.%m.%Y %H:%M') if r.finished_at else '-'
        } for r in results]
    })

@app.route('/api/quiz/<int:quiz_id>/session-stats', methods=['GET'])
def get_session_stats(quiz_id):
    """Статистика по игровым сессиям (для мультиплеера)"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    # Получаем все мультиплеерные результаты
    results = GameResult.query.filter_by(quiz_id=quiz_id, mode='multiplayer').all()
    
    # Группируем по коду сессии
    sessions = {}
    for r in results:
        if r.quiz_code not in sessions:
            sessions[r.quiz_code] = {'players': [], 'total_score': 0, 'date': r.finished_at}
        sessions[r.quiz_code]['players'].append(r)
        sessions[r.quiz_code]['total_score'] += r.score
    
    total_sessions = len(sessions)
    avg_players = sum(len(s['players']) for s in sessions.values()) / total_sessions if total_sessions > 0 else 0
    total_games = len(results)
    
    # Список сессий
    sessions_list = [{'code': code, 'players_count': len(s['players']), 'total_score': s['total_score'], 'date': s['date'].strftime('%d.%m.%Y %H:%M') if s['date'] else '-'} for code, s in sessions.items()]
    sessions_list.sort(key=lambda x: x['date'], reverse=True)
    
    return jsonify({
        'success': True,
        'total_sessions': total_sessions,
        'avg_players_per_session': round(avg_players, 1),
        'total_games': total_games,
        'sessions': sessions_list
    })

@app.route('/api/quiz/<int:quiz_id>/question-stats', methods=['GET'])
def get_question_stats(quiz_id):
    """Статистика по каждому вопросу викторины"""
    if 'user_id' not in session:
        return jsonify({'success': False, 'error': 'Не авторизован'}), 401
    
    quiz = db.session.get(Quiz, quiz_id)
    if not quiz or quiz.owner_id != session['user_id']:
        return jsonify({'success': False, 'error': 'Нет доступа'}), 403
    
    questions = Question.query.filter_by(quiz_id=quiz_id).order_by(Question.order).all()
    results = GameResult.query.filter_by(quiz_id=quiz_id).all()
    
    question_stats = []
    for q in questions:
        stats = {
            'question_id': q.id,
            'question_text': q.text[:100] if q.text else '?',
            'correct_answer': q.correct_answer[0] if q.correct_answer else '?',
            'total_attempts': len(results),
            'difficulty': 'medium'
        }
        question_stats.append(stats)
    
    return jsonify({
        'success': True,
        'questions': question_stats,
        'total_players': len(results)
    })


if __name__ == '__main__':
    app.run(debug=True)