document.addEventListener('DOMContentLoaded', function() {
    
    // ========== ВХОД ПО КОДУ ==========
    const joinBtn = document.getElementById('joinBtn');
    const quizCodeInput = document.getElementById('quizCode');
    
    if (joinBtn) {
        joinBtn.addEventListener('click', function() {
            const code = quizCodeInput.value.trim();
            
            if (code.length === 6) {
                window.location.href = '/play/' + code;
            } else {
                alert('Пожалуйста, введите 6-значный код викторины');
            }
        });
    }
    
    if (quizCodeInput) {
        quizCodeInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                joinBtn.click();
            }
        });
    }
    
    // ========== СОЗДАНИЕ ВИКТОРИНЫ ==========
    const createQuizBtn = document.getElementById('createQuizBtn');
    if (createQuizBtn) {
        createQuizBtn.addEventListener('click', function() {
            // Проверяем, авторизован ли пользователь
            const isLoggedIn = document.querySelector('.user-greeting') !== null;
            
            if (isLoggedIn) {
                window.location.href = '/quiz/create';
            } else {
                window.location.href = '/login';
            }
        });
    }
    
    const ctaCreateBtn = document.getElementById('ctaCreateBtn');
    if (ctaCreateBtn) {
        ctaCreateBtn.addEventListener('click', function() {
            const isLoggedIn = document.querySelector('.user-greeting') !== null;
            
            if (isLoggedIn) {
                window.location.href = '/quiz/create';
            } else {
                window.location.href = '/login';
            }
        });
    }
    
});