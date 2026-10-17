import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from pypdf import PdfReader
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'khoa_bi_mat_cua_ban'

# Kiểm tra và cấu hình Gemini API Key
GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)

@app.route('/')
def home():
    if 'username' in session:
        return render_template('dashboard.html', username=session['username'])
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        session['username'] = username
        return redirect(url_for('home'))
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
def upload_file():
    # Kiểm tra xem đã cấu hình khóa API trên Render chưa
    if not GEMINI_API_KEY:
        return jsonify({'error': 'Lỗi: Chưa cấu hình biến môi trường GEMINI_API_KEY trên Render!'}), 500

    if 'file' not in request.files:
        return jsonify({'error': 'Không tìm thấy file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Chưa chọn file'}), 400
    
    if file and file.filename.endswith('.pdf'):
        try:
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            
            text = text[:12000]

            prompt = f"""
            Dựa vào nội dung tài liệu học tập dưới đây, hãy tạo ra 5 câu hỏi trắc nghiệm chất lượng.
            BẮT BUỘC phải trả về kết quả ở dạng một chuỗi JSON thuần túy (không kèm markdown như ```json), theo cấu trúc mẫu chính xác sau:
            {{
              "quiz": [
                {{
                  "id": 1,
                  "question": "Nội dung câu hỏi?",
                  "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
                  "answer": 0
                }}
              ]
            }}
            Trong đó trường "answer" là số thứ tự của đáp án đúng (từ 0 đến 3 ứng với 4 đáp án trong mảng options).

            Nội dung tài liệu:
            {text}
            """

            model = genai.GenerativeModel('gemini-3.8-flash')
            response = model.generate_content(prompt)
            
            res_text = response.text.strip()
            if res_text.startswith("```json"):
                res_text = res_text[7:]
            if res_text.startswith("```"):
                res_text = res_text[3:]
            if res_text.endswith("```"):
                res_text = res_text[:-3]

            quiz_data = json.loads(res_text.strip())
            return jsonify(quiz_data)

        except Exception as e:
            print("🚨 LỖI CHI TIẾT:", str(e))
            return jsonify({'error': f'Lỗi: {str(e)}'}), 500

    return jsonify({'error': 'Chỉ chấp nhận định dạng file PDF!'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
import os
import json
import re
import sqlite3
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from pypdf import PdfReader
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'hoc_tap_hub_secret_key_pro'

# Khởi tạo SQLite Database
DB_NAME = 'database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT NOT NULL,
            score INTEGER NOT NULL,
            total INTEGER NOT NULL,
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
        # Lấy lịch sử làm bài từ database
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("SELECT score, total, date FROM history WHERE username = ? ORDER BY date DESC LIMIT 10", (username,))
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
                return jsonify({'error': 'File PDF dạng ảnh (scanned) không trích xuất được chữ. Vui lòng tải PDF dạng văn bản!'}), 400

            text = text[:12000]

            prompt = f"""
            Dựa vào nội dung tài liệu học tập dưới đây, hãy tạo ra 5 câu hỏi trắc nghiệm khách quan chất lượng cao.
            BẮT BUỘC trả về duy nhất một chuỗi JSON thuần túy theo định dạng mẫu sau:
            {{
              "quiz": [
                {{
                  "id": 1,
                  "question": "Nội dung câu hỏi?",
                  "options": ["Đáp án A", "Đáp án B", "Đáp án C", "Đáp án D"],
                  "answer": 0
                }}
              ]
            }}
            Trường "answer" là chỉ số đáp án đúng (từ 0 đến 3).

            Nội dung tài liệu:
            {text}
            """

            model = genai.GenerativeModel('gemini-3.8-flash')
            response = model.generate_content(prompt)
            res_text = response.text.strip()

            # Bắt lỗi JSON an toàn bằng Regex
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
            print("🚨 LỖI CHI TIẾT:", str(e))
            return jsonify({'error': f'Lỗi: {str(e)}'}), 500
@app.route('/quiz')
def quiz_page():
    if 'quiz_data' not in session:
        return redirect(url_for('home'))
    return render_template('quiz.html', quiz=session['quiz_data'], time_limit=session.get('time_limit', 10))

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
            'is_correct': is_correct
        })

    # Lưu kết quả thi vào Database
    try:
        conn = sqlite3.connect(DB_NAME)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO history (username, score, total) VALUES (?, ?, ?)", (username, score, total))
        conn.commit()
        conn.close()
    except Exception as e:
        print("Lỗi lưu DB:", str(e))

    return jsonify({
        'score': score,
        'total': total,
        'details': details
    })

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)