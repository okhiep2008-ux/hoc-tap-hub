import os
import json
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = "your_secret_key_here"  # Đổi khóa bí mật khi chạy thực tế
UPLOAD_FOLDER = 'uploads'
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# Dữ liệu giả lập lưu trong bộ nhớ (Bạn có thể thay thế bằng SQLAlchemy + SQLite/PostgreSQL)
users_db = {}       # username: password_hash
history_db = []     # Lưu lịch sử làm bài của user
quizzes_db = {}     # quiz_id: nội dung câu hỏi trắc nghiệm

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login'))
    return render_template('dashboard.html', username=session['user'], history=[h for h in history_db if h['user'] == session['user']])

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        password = generate_password_hash(request.form['password'])
        if username in users_db:
            return "Tài khoản đã tồn tại!"
        users_db[username] = password
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        if username in users_db and check_password_hash(users_db[username], password):
            session['user'] = username
            return redirect(url_for('index'))
        return "Sai tên đăng nhập hoặc mật khẩu!"
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    file = request.files.get('file')
    if file:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        
        # [AI Integration Step]: Ở đây bạn gọi Gemini API / OpenAI API đọc file PDF/Word 
        # để tự động tạo ra danh sách câu hỏi trắc nghiệm & bài tập vận dụng kèm lời giải.
        # Dưới đây là cấu trúc mẫu trả về cho Frontend:
        sample_quiz = [
            {
                "id": 1,
                "question": "Đâu là từ đồng nghĩa với 'benevolent'?",
                "options": ["Hostile", "Kind", "Indifferent", "Cruel"],
                "correct": 1,
                "explanation": "'Benevolent' có nghĩa là nhân từ, tốt bụng, đồng nghĩa với 'Kind'."
            },
            {
                "id": 2,
                "question": "[Bài tập vận dụng] Tính giá trị biểu thức khi x = 2: f(x) = x^2 + 3x - 5",
                "options": ["5", "3", "7", "10"],
                "correct": 0,
                "explanation": "Thay x = 2 vào: 2^2 + 3(2) - 5 = 4 + 6 - 5 = 5."
            }
        ]
        
        quiz_id = str(len(quizzes_db) + 1)
        quizzes_db[quiz_id] = sample_quiz
        return jsonify({'quiz_id': quiz_id, 'quiz': sample_quiz})
    
    return jsonify({'error': 'No file uploaded'}), 400

@app.route('/submit_quiz', methods=['POST'])
def submit_quiz():
    if 'user' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    
    data = request.json
    quiz_id = data.get('quiz_id')
    user_answers = data.get('answers') # Dict: {question_id: selected_option_index}
    
    quiz = quizzes_db.get(quiz_id, [])
    score = 0
    detailed_results = []
    
    for q in quiz:
        q_id = str(q['id'])
        user_choice = user_answers.get(q_id)
        is_correct = (user_choice == q['correct'])
        if is_correct:
            score += 1
        detailed_results.append({
            'question': q['question'],
            'options': q['options'],
            'user_choice': user_choice,
            'correct': q['correct'],
            'is_correct': is_correct,
            'explanation': q['explanation']
        })
        
    # Lưu vào lịch sử làm bài
    history_record = {
        'user': session['user'],
        'score': f"{score}/{len(quiz)}",
        'details': detailed_results
    }
    history_db.append(history_record)
    
    return jsonify({'score': score, 'total': len(quiz), 'details': detailed_results})

if __name__ == '__main__':
    app.run(debug=True, port=5000)