import os
import smtplib
import random
import time
import logging
import psycopg2
from email.mime.text import MIMEText
from flask import Flask, request, jsonify, render_template
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)

# 配置设置
app.config['SMTP_SERVER'] = os.getenv('SMTP_SERVER', 'smtp-mail.outlook.com')
app.config['SMTP_PORT'] = int(os.getenv('SMTP_PORT', '587'))
app.config['EMAIL_FROM'] = os.getenv('EMAIL_FROM', 'rbx-hnqc@outlook.com')
app.config['SMTP_PASSWORD'] = os.getenv('SMTP_PASSWORD', 'HNQC2025')
app.config['CODE_LENGTH'] = 6
app.config['CODE_EXPIRY'] = 300  # 5分钟

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 获取数据库连接
def get_db_connection():
    conn = psycopg2.connect(
        host=os.getenv('DB_HOST'),
        database=os.getenv('DB_NAME'),
        user=os.getenv('DB_USER'),
        password=os.getenv('DB_PASSWORD'),
        port=os.getenv('DB_PORT')
    )
    return conn

# 初始化数据库
def init_db():
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # 创建验证码表
        cur.execute('''
            CREATE TABLE IF NOT EXISTS verification_codes (
                id SERIAL PRIMARY KEY,
                email TEXT NOT NULL UNIQUE,
                code TEXT NOT NULL,
                created_at BIGINT NOT NULL,
                is_used BOOLEAN DEFAULT FALSE
            )
        ''')
        
        # 创建索引
        cur.execute('CREATE INDEX IF NOT EXISTS idx_email ON verification_codes(email)')
        cur.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON verification_codes(created_at)')
        
        conn.commit()
        logger.info("数据库初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {str(e)}")
    finally:
        if conn:
            conn.close()

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
        
        with smtplib.SMTP(app.config['SMTP_SERVER'], app.config['SMTP_PORT']) as server:
            server.starttls()
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
        conn = get_db_connection()
        cur = conn.cursor()
        cur.execute("DELETE FROM verification_codes WHERE created_at < %s OR is_used = TRUE", (expired_time,))
        conn.commit()
        logger.info("已清理过期验证码")
    except Exception as e:
        logger.error(f"清理过期验证码失败: {str(e)}")
    finally:
        if conn:
            conn.close()

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
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            INSERT INTO verification_codes (email, code, created_at, is_used)
            VALUES (%s, %s, %s, FALSE)
            ON CONFLICT (email) DO UPDATE SET
                code = EXCLUDED.code,
                created_at = EXCLUDED.created_at,
                is_used = FALSE
        """, (email, code, int(time.time())))
        
        conn.commit()
        logger.info(f"为 {email} 生成验证码: {code}")
    except Exception as e:
        logger.error(f"数据库错误: {e}")
        return jsonify({'success': False, 'error': '系统错误'}), 500
    finally:
        if conn:
            conn.close()
    
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
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute("""
            SELECT id FROM verification_codes 
            WHERE email = %s AND code = %s AND is_used = FALSE
        """, (email, code))
        
        row = cur.fetchone()
        
        if not row:
            return jsonify({'success': False, 'error': '验证码无效或已使用'}), 400
        
        # 标记为已使用
        cur.execute("UPDATE verification_codes SET is_used = TRUE WHERE id = %s", (row[0],))
        conn.commit()
        
        logger.info(f"{email} 验证成功")
        return jsonify({'success': True, 'message': '验证成功！您可以使用此验证码加入QQ群'})
    except Exception as e:
        logger.error(f"验证失败: {str(e)}")
        return jsonify({'success': False, 'error': '系统错误'}), 500
    finally:
        if conn:
            conn.close()

if __name__ == '__main__':
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
