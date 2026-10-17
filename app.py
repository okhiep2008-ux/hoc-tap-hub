import os
import json
import re
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from pypdf import PdfReader
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'hoc_tap_hub_secret_key_pro_v2'

DB_NAME = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # Bảng history lưu thêm cột detail_json để xem lại bài cũ
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
            detail_json TEXT,
            date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    if 'username' in session:
        username = session['username']
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT id, score, total, date FROM history WHERE username = ? ORDER BY date DESC LIMIT 10", (username,))
        history = cursor.fetchall()
        conn.close()
        return render_template('dashboard.html', username=username, history=history)
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        if username:
            session['username'] = username
            return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if not GEMINI_API_KEY:
        return jsonify({'error': 'Chưa cấu hình GEMINI_API_KEY trên Render!'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'Không tìm thấy file'}), 400
    
    file = request.files['file']
    num_questions = request.form.get('num_questions', 10)
    difficulty = request.form.get('difficulty', 'Vận dụng cao')
    time_limit = request.form.get('time_limit', 10)

    if file and file.filename.endswith('.pdf'):
        try:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                extracted = page.extract_text()
                if extracted:
                    text += extracted + "\n"
            
            if not text.strip():
                return jsonify({'error': 'File PDF dạng ảnh (scanned) không đọc được chữ. Hãy dùng PDF văn bản!'}), 400

            text = text[:15000]

            prompt = f"""
            Bạn là một chuyên gia ra đề thi cấp độ đại học/chuyên sâu.
            Dựa vào nội dung tài liệu học tập dưới đây, hãy tạo ra {num_questions} câu hỏi trắc nghiệm với mức độ tư duy: "{difficulty}".

            YÊU CẦU ĐẶC BIỆT:
            1. Nếu tài liệu chứa CÔNG THỨC, LÍ THUYẾT BÀI TẬP hoặc ĐỊNH LÝ, hãy tạo các bài tập TÍNH TOÁN VẬN DỤNG, cho dữ kiện số cụ thể để người học tự áp dụng công thức tính ra kết quả.
            2. Tránh các câu hỏi nhận biết ghi nhớ đơn thuần. Hãy tập trung vào phân tích, suy luận, áp dụng công thức, so sánh hoặc xử lý tình huống.
            3. Với mỗi câu hỏi, BẮT BUỘC cung cấp LỜI GIẢI CHI TIẾT (explanation) giải thích rõ từng bước tính toán hoặc lý do tại sao đáp án đó đúng/sai.

            BẮT BUỘC trả về duy nhất một chuỗi JSON thuần túy theo định dạng:
            {{
              "quiz": [
                {{
                  "id": 1,
                  "question": "Nội dung câu hỏi hoặc bài tập tính toán?",
                  "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
                  "answer": 0,
                  "explanation": "Lời giải chi tiết: Áp dụng công thức X = Y * Z... Do đó tính ra đáp án A."
                }}
              ]
            }}
            Trong đó "answer" là số thứ tự đáp án đúng (từ 0 đến 3).

            Nội dung tài liệu:
            {text}
            """

            model = genai.GenerativeModel('gemini-3.8-flash')
            response = model.generate_content(prompt)
            res_text = response.text.strip()

            json_match = re.search(r'\{.*\}', res_text, re.DOTALL)
            if json_match:
                clean_json = json_match.group(0)
                quiz_data = json.loads(clean_json)
            else:
                quiz_data = json.loads(res_text)

            session['quiz_data'] = quiz_data['quiz']
            session['time_limit'] = int(time_limit)

            return jsonify({'success': True})

        except Exception as e:
            return jsonify({'error': f'Lỗi xử lý AI: {str(e)}'}), 500

    return jsonify({'error': 'Chỉ chấp nhận file PDF!'}), 400

@app.route('/quiz')
def quiz_page():
    if 'quiz_data' not in session:
        return redirect(url_for('home'))
    return render_template('quiz.html', quiz=session['quiz_data'], time_limit=session.get('time_limit', 10), is_review=False)

@app.route('/submit-quiz', methods=['POST'])
def submit_quiz():
    user_answers = request.json.get('answers', {})
    quiz_data = session.get('quiz_data', [])
    username = session.get('username', 'Học viên')
    
    score = 0
    total = len(quiz_data)
    details = []

    for idx, q in enumerate(quiz_data):
        user_ans = int(user_answers.get(str(idx), -1))
        correct_ans = q['answer']
        is_correct = (user_ans == correct_ans)
        if is_correct:
            score += 1
        details.append({
            'question': q['question'],
            'options': q['options'],
            'user_ans': user_ans,
            'correct_ans': correct_ans,
            'is_correct': is_correct,
            'explanation': q.get('explanation', 'Không có lời giải chi tiết.')
        })

    # Lưu kết quả + chi tiết đáp án vào Database
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (username, score, total, detail_json) VALUES (?, ?, ?, ?)",
                       (username, score, total, json.dumps(details, ensure_ascii=False)))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Lỗi lưu DB:", str(e))

    return jsonify({
        'score': score,
        'total': total,
        'details': details
    })

# Xem lại bài thi cũ
@app.route('/review/<int:history_id>')
def review_quiz(history_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT score, total, detail_json, date FROM history WHERE id = ?", (history_id,))
    record = cursor.fetchone()
    conn.close()

    if not record:
        return redirect(url_for('home'))

    score, total, detail_json, date = record
    details = json.loads(detail_json) if detail_json else []

    return render_template('review.html', score=score, total=total, details=details, date=date)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)