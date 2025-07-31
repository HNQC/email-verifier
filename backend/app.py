import os
from flask import Flask, request, jsonify
import mysql.connector
import requests
import random
from datetime import datetime, timedelta
from flask_cors import CORS
from config import DB_CONFIG, SENDCLOUD_API_USER, SENDCLOUD_API_KEY, FROM_EMAIL, EMAIL_TEMPLATE

app = Flask(__name__)
CORS(app)  # 启用CORS支持

# 数据库连接
def get_db_connection():
    return mysql.connector.connect(
        host=DB_CONFIG['host'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database']
    )

# 生成6位随机验证码
def generate_verification_code():
    return ''.join(random.choices('0123456789', k=6))

# 发送邮件
def send_email(email, code):
    url = "https://api.sendcloud.net/apiv2/mail/send"
    
    data = {
        "apiUser": SENDCLOUD_API_USER,
        "apiKey": SENDCLOUD_API_KEY,
        "from": FROM_EMAIL,
        "fromName": "HNQC验证系统",
        "to": email,
        "subject": "HNQC验证码",
        "html": EMAIL_TEMPLATE.format(code=code)
    }
    
    response = requests.post(url, data=data)
    return response.status_code == 200

# 验证码发送接口
@app.route('/send-verification', methods=['POST'])
def send_verification():
    data = request.json
    email = data.get('email')
    
    # 验证邮箱格式
    if not email or '@' not in email:
        return jsonify({'success': False, 'message': '无效的邮箱地址'}), 400
    
    # 生成验证码
    code = generate_verification_code()
    created_at = datetime.now()
    expires_at = created_at + timedelta(minutes=10)
    
    # 保存到数据库
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 删除该邮箱之前的验证码
        cursor.execute("DELETE FROM verification_codes WHERE email = %s", (email,))
        
        # 插入新验证码
        cursor.execute(
            "INSERT INTO verification_codes (email, code, created_at, expires_at, used) VALUES (%s, %s, %s, %s, %s)",
            (email, code, created_at, expires_at, 0)
        )
        conn.commit()
        
        # 发送邮件
        if send_email(email, code):
            return jsonify({'success': True, 'message': '验证码已发送'})
        else:
            return jsonify({'success': False, 'message': '邮件发送失败'}), 500
            
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 验证码验证接口
@app.route('/verify-code', methods=['POST'])
def verify_code():
    data = request.json
    code = data.get('code')
    
    if not code or len(code) != 6:
        return jsonify({'valid': False, 'message': '无效的验证码格式'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        
        # 查询验证码
        cursor.execute(
            "SELECT * FROM verification_codes WHERE code = %s AND used = 0 AND expires_at > NOW()",
            (code,)
        )
        result = cursor.fetchone()
        
        if result:
            # 标记为已使用
            cursor.execute(
                "UPDATE verification_codes SET used = 1 WHERE id = %s",
                (result['id'],)
            )
            conn.commit()
            return jsonify({'valid': True, 'email': result['email']})
        else:
            return jsonify({'valid': False, 'message': '验证码无效或已过期'})
            
    except Exception as e:
        return jsonify({'valid': False, 'message': str(e)}), 500
    finally:
        if conn.is_connected():
            cursor.close()
            conn.close()

# 数据库连接测试
@app.route('/test-db', methods=['GET'])
def test_db():
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT 1")
        result = cursor.fetchone()
        cursor.close()
        conn.close()
        return jsonify({'success': True, 'message': f'数据库连接成功: {result[0]}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

# 健康检查端点
@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({'status': 'ok', 'time': datetime.now().isoformat()})

if __name__ == '__main__':
    # 确保数据库表存在
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS verification_codes (
                id INT AUTO_INCREMENT PRIMARY KEY,
                email VARCHAR(255) NOT NULL,
                code VARCHAR(10) NOT NULL,
                created_at DATETIME NOT NULL,
                expires_at DATETIME NOT NULL,
                used TINYINT(1) NOT NULL DEFAULT 0
            )
        """)
        conn.commit()
        cursor.close()
        conn.close()
        print("数据库表已创建/验证")
    except Exception as e:
        print(f"数据库初始化错误: {str(e)}")
    
    # 启动应用
    app.run(host='0.0.0.0', port=5000)
