import random
import time
import mysql.connector
import requests
from flask import Flask, request, jsonify
from datetime import datetime, timedelta

app = Flask(__name__)

# 配置信息
SENDCLOUD_API_USER = 'HNQC2025'
SENDCLOUD_API_KEY = '09ea3daff4c5698556dfa85bc7471892'
FROM_DOMAIN = 'hnqc.dpdns.org'
FROM_EMAIL = 'rbx-hnqc@outlook.com'
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': '63EN4QU5r8euX1Ot0KziH9x2Mpf7ATlY',  # 替换为你的MySQL密码
    'database': 'hnqc_verification'
}

# 创建数据库连接
def create_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# 初始化数据库
def init_database():
    conn = create_db_connection()
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS verification_codes (
            id INT AUTO_INCREMENT PRIMARY KEY,
            email VARCHAR(255) NOT NULL,
            code VARCHAR(10) NOT NULL,
            created_at DATETIME NOT NULL,
            used TINYINT DEFAULT 0
        )
    ''')
    conn.commit()
    cursor.close()
    conn.close()

# 生成验证码
def generate_verification_code():
    return str(random.randint(100000, 999999))

# 发送邮件
def send_verification_email(email, code):
    url = "http://api.sendcloud.net/apiv2/mail/send"
    subject = "您的HNQC验证码"
    html_content = f"""
    <html>
    <head></head>
    <body>
        <div style="background-color:#000; color:#fff; padding:20px; text-align:center;">
            <div style="background-color:#111; padding:30px; border-radius:10px; border:1px solid #333; display:inline-block;">
                <h2 style="color:#00aaff;">HNQC 验证系统</h2>
                <div style="font-size:24px; font-weight:bold; letter-spacing:5px; margin:20px 0; padding:10px; background:#002244; border-radius:5px;">
                    {code}
                </div>
                <p style="color:#aaa;">该验证码10分钟内有效，请勿泄露给他人。</p>
            </div>
        </div>
    </body>
    </html>
    """
    
    params = {
        "apiUser": SENDCLOUD_API_USER,
        "apiKey": SENDCLOUD_API_KEY,
        "from": FROM_EMAIL,
        "fromName": "HNQC系统",
        "to": email,
        "subject": subject,
        "html": html_content
    }
    
    response = requests.post(url, data=params)
    result = response.json()
    return result.get('result', False), result.get('message', '未知错误')

# 邮箱验证码发送接口
@app.route('/send-verification', methods=['POST'])
def send_verification():
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({'success': False, 'error': '邮箱不能为空'}), 400
    
    conn = create_db_connection()
    cursor = conn.cursor()
    
    # 检查10分钟内是否已发送过
    cursor.execute(
        "SELECT * FROM verification_codes WHERE email = %s AND created_at > %s AND used = 0",
        (email, datetime.now() - timedelta(minutes=10))
    )
    existing = cursor.fetchone()
    
    if existing:
        return jsonify({'success': False, 'error': '验证码已发送，请稍后再试'}), 400
    
    # 生成验证码
    code = generate_verification_code()
    created_at = datetime.now()
    
    # 保存到数据库
    cursor.execute(
        "INSERT INTO verification_codes (email, code, created_at) VALUES (%s, %s, %s)",
        (email, code, created_at)
    )
    conn.commit()
    
    # 发送邮件
    success, message = send_verification_email(email, code)
    if success:
        return jsonify({'success': True})
    else:
        # 如果发送失败，删除记录
        cursor.execute("DELETE FROM verification_codes WHERE id = LAST_INSERT_ID()")
        conn.commit()
        return jsonify({'success': False, 'error': f'邮件发送失败: {message}'}), 500

# 启动应用
if __name__ == '__main__':
    init_database()
    app.run(host='0.0.0.0', port=5000)
