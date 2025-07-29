import os
import sqlite3
import smtplib
import random
import time
import logging
import threading
import requests
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, render_template

app = Flask(__name__)

# 配置设置
app.config['DB_FILE'] = '/data/email_verification.db'  # 持久化存储位置
app.config['SMTP_SERVER'] = os.getenv('SMTP_SERVER', 'smtp.qiye.163.com')
app.config['SMTP_PORT'] = int(os.getenv('SMTP_PORT', '465'))
app.config['EMAIL_FROM'] = os.getenv('EMAIL_FROM', 'admin@yourdomain.com')
app.config['SMTP_PASSWORD'] = os.getenv('SMTP_PASSWORD', 'your_password')
app.config['CODE_LENGTH'] = 6
app.config['CODE_EXPIRY'] = 300  # 5分钟
app.config['ZEABUR_URL'] = os.getenv('ZEABUR_URL', 'https://qq-verifier.zeabur.app')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 初始化数据库
def init_db():
    try:
        with sqlite3.connect(app.config['DB_FILE']) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS verification_codes (
                    email TEXT PRIMARY KEY,
                    code TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    is_used INTEGER DEFAULT 0
                )
            ''')
            cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON verification_codes(created_at)')
            conn.commit()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")

# 发送验证码邮件
def send_verification_email(to_email, code):
    try:
        sender_email = app.config['EMAIL_FROM']
        password = app.config['SMTP_PASSWORD']
        
        subject = "您的QQ群验证码"
        body = f"""
        <html>
            <body>
                <h2>QQ群验证信息</h2>
                <p>您请求的验证码是：<strong>{code}</strong></p>
                <p>请在申请加入QQ群时在「入群理由」中填写此验证码。</p>
                <p>提示：该验证码5分钟内有效。</p>
            </body>
        </html>
        """
        
        msg = MIMEText(body, 'html')
        msg['Subject'] = subject
        msg['From'] = sender_email
        msg['To'] = to_email
        
        # 使用SSL连接
        with smtplib.SMTP_SSL(app.config['SMTP_SERVER'], app.config['SMTP_PORT'], timeout=10) as server:
            server.login(sender_email, password)
            server.send_message(msg)
        logger.info(f"邮件成功发送至 {to_email}")
        return True
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        return False

# 清理过期验证码
def clean_expired_codes():
    expired_time = time.time() - app.config['CODE_EXPIRY']
    try:
        with sqlite3.connect(app.config['DB_FILE']) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM verification_codes WHERE created_at < ? OR is_used = 1", (expired_time,))
            conn.commit()
        logger.info("已清理过期验证码")
    except Exception as e:
        logger.error(f"清理过期验证码失败: {str(e)}")

# 自动保持应用活跃
def keep_alive():
    """自动保持应用活跃"""
    while True:
        try:
            # 访问健康检查端点
            response = requests.get(f"{app.config['ZEABUR_URL']}/health", timeout=10)
            logger.info(f"Keep-alive request: {response.status_code}")
        except Exception as e:
            logger.error(f"Keep-alive failed: {str(e)}")
        time.sleep(300)  # 每5分钟执行一次

# 路由：首页
@app.route('/')
def index():
    return render_template('index.html')

# 路由：生成验证码
@app.route('/request_code', methods=['POST'])
def request_code():
    # 检查请求是否为JSON格式
    if not request.is_json:
        return jsonify({'success': False, 'error': '请求必须使用 application/json Content-Type'}), 400
    
    data = request.get_json()
    email = data.get('email', '').strip()
    
    # 验证邮箱格式
    if not email or '@' not in email:
        return jsonify({'success': False, 'error': '无效的邮箱地址'}), 400
    
    # 生成随机验证码
    code = ''.join(random.choices('0123456789', k=app.config['CODE_LENGTH']))
    
    # 保存到数据库
    try:
        with sqlite3.connect(app.config['DB_FILE']) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO verification_codes (email, code, created_at, is_used)
                VALUES (?, ?, ?, 0)
            """, (email, code, time.time()))
            conn.commit()
        logger.info(f"为 {email} 生成验证码: {code}")
    except Exception as e:
        logger.error(f"数据库错误: {e}")
        return jsonify({'success': False, 'error': '系统错误'}), 500
    
    # 发送邮件
    if send_verification_email(email, code):
        return jsonify({'success': True, 'message': '验证码已发送'})
    else:
        return jsonify({'success': False, 'error': '邮件发送失败'}), 500

# 路由：验证验证码
@app.route('/verify_code', methods=['POST'])
def verify_code():
    # 检查请求是否为JSON格式
    if not request.is_json:
        return jsonify({'success': False, 'error': '请求必须使用 application/json Content-Type'}), 400
    
    data = request.get_json()
    email = data.get('email', '').strip()
    code = data.get('code', '').strip()
    
    # 清理过期验证码
    clean_expired_codes()
    
    # 验证验证码
    try:
        with sqlite3.connect(app.config['DB_FILE']) as conn:
            cursor = conn.cursor()
            row = cursor.execute("""
                SELECT * FROM verification_codes 
                WHERE email = ? AND code = ? AND is_used = 0
            """, (email, code)).fetchone()
            
            if not row:
     
