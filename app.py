import os
import json
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from pypdf import PdfReader
import google.generativeai as genai

app = Flask(__name__)
app.secret_key = 'khoa_bi_mat_cua_ban' # Thay đổi tùy ý để bảo mật session

# Lấy Gemini API Key từ biến môi trường trên Render
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

# API xử lý đọc file PDF và gọi Gemini tạo trắc nghiệm
@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        return jsonify({'error': 'Không tìm thấy file'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Chưa chọn file'}), 400
    
    if file and file.filename.endswith('.pdf'):
        try:
            # 1. Đọc nội dung chữ từ file PDF
            reader = PdfReader(file)
            text = ""
            for page in reader.pages:
                text += page.extract_text() or ""
            
            # Cắt ngắn bớt nếu tài liệu quá dài (giới hạn token)
            text = text[:12000]

            # 2. Tạo câu lệnh (prompt) yêu cầu Gemini trả về JSON chuẩn
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

            # 3. Gọi Gemini API (Sử dụng model gemini-1.5-flash)
            model = genai.GenerativeModel('gemini-1.5-flash')
            response = model.generate_content(prompt)
            
            # Làm sạch dữ liệu trả về để parse JSON
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
            return jsonify({'error': f'Lỗi xử lý AI:ходила {str(e)}'}), 500

    return jsonify({'error': 'Chỉ chấp nhận định dạng file PDF!'}), 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)