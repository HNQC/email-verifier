import os
import random
import time
import logging
import threading
import requests
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError

app = Flask(__name__)

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{os.environ['MYSQL_USERNAME']}:{os.environ['MYSQL_PASSWORD']}"
    f"@{os.environ['MYSQL_HOST']}:{os.environ['MYSQL_PORT']}/{os.environ['MYSQL_DATABASE']}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# SendCloud 配置
app.config['SENDCLOUD_API_USER'] = os.getenv('SENDCLOUD_API_USER', 'sc_yg739l_test_N8nase')
app.config['SENDCLOUD_API_KEY'] = os.getenv('SENDCLOUD_API_KEY', 'e0ca44d9578a1db2b71b9ca2198daf2e')
app.config['SENDCLOUD_FROM_EMAIL'] = os.getenv('SENDCLOUD_FROM_EMAIL', 'no-reply@sendcloud.com')
app.config['SENDCLOUD_FROM_NAME'] = os.getenv('SENDCLOUD_FROM_NAME', 'QQ群验证服务')
app.config['CODE_LENGTH'] = 6
app.config['CODE_EXPIRY'] = 300  # 5分钟
app.config['ZEABUR_URL'] = os.getenv('ZEABUR_URL', 'https://qq-verifier.zeabur.app')

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# 初始化数据库
db = SQLAlchemy(app)

# 验证码数据模型
class VerificationCode(db.Model):
    __tablename__ = "verification_codes"
    email = db.Column(db.String(128), primary_key=True)
    code = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.Float, nullable=False)
    is_used = db.Column(db.Boolean, default=False)

# 创建数据库表
with app.app_context():
    try:
        db.create_all()
        logger.info("数据库表创建成功")
    except Exception as e:
        logger.error(f"数据库表创建失败: {str(e)}")

# 自动保持应用活跃
def keep_alive():
    """自动保持应用活跃"""
    while True:
        try:
            # 访问健康检查端点
            response = requests.get(f"{app.config['ZEABUR_URL']}/health", timeout=10)
            logger.info(f"保持活跃请求: {response.status_code}")
        except Exception as e:
            logger.error(f"保持活跃失败: {str(e)}")
        time.sleep(300)  # 每5分钟执行一次

# 启动保持活跃线程
keep_alive_thread = threading.Thread(target=keep_alive)
keep_alive_thread.daemon = True
keep_alive_thread.start()

# 发送验证码邮件（使用 SendCloud API）
def send_verification_email(to_email, code):
    try:
        # SendCloud API 配置
        api_user = app.config['SENDCLOUD_API_USER']
        api_key = app.config['SENDCLOUD_API_KEY']
        from_email = app.config['SENDCLOUD_FROM_EMAIL']
        from_name = app.config['SENDCLOUD_FROM_NAME']
        
        subject = "您的QQ群验证码"
        html_content = f"""
        <html>
            <body>
                <h2>QQ群验证信息</h2>
                <p>您请求的验证码是：<strong>{code}</strong></p>
                <p>请在申请加入QQ群时在「入群理由」中填写此验证码。</p>
                <p>提示：该验证码5分钟内有效。</p>
            </body>
        </html>
        """
        
        # 构建 API 请求
        url = "https://api.sendcloud.net/apiv2/mail/send"
        data = {
            "apiUser": api_user,
            "apiKey": api_key,
            "from": f"{from_name} <{from_email}>",
            "to": to_email,
            "subject": subject,
            "html": html_content,
            "respEmailId": "true"
        }
        
        # 发送请求
        response = requests.post(url, data=data)
        result = response.json()
        
        # 检查响应
        if result.get('result') == True:
            logger.info(f"邮件成功发送至 {to_email}")
            return True
        else:
            logger.error(f"邮件发送失败: {result.get('message', '未知错误')}")
            return False
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        return False

# 清理过期验证码
def clean_expired_codes():
    expired_time = time.time() - app.config['CODE_EXPIRY']
    try:
        # 删除过期或已使用的验证码
        VerificationCode.query.filter(
            (VerificationCode.created_at < expired_time) | 
            (VerificationCode.is_used == True)
        ).delete()
        db.session.commit()
        logger.info("已清理过期验证码")
    except Exception as e:
        logger.error(f"清理过期验证码失败: {str(e)}")
        db.session.rollback()

# 健康检查端点
@app.route('/health')
def health_check():
    """健康检查端点"""
    return "OK", 200

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
        # 使用 upsert 操作（存在则更新，不存在则插入）
        existing_code = VerificationCode.query.get(email)
        if existing_code:
            existing_code.code = code
            existing_code.created_at = time.time()
            existing_code.is_used = False
        else:
            new_code = VerificationCode(
                email=email,
                code=code,
                created_at=time.time(),
                is_used=False
            )
            db.session.add(new_code)
        
        db.session.commit()
        logger.info(f"为 {email} 生成验证码: {code}")
    except SQLAlchemyError as e:
        logger.error(f"数据库错误: {str(e)}")
        db.session.rollback()
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
        verification_code = VerificationCode.query.filter_by(
            email=email,
            code=code,
            is_used=False
        ).first()
        
        if not verification_code:
            return jsonify({'success': False, 'error': '验证码无效或已使用'}), 400
        
        # 标记为已使用
        verification_code.is_used = True
        db.session.commit()
        
        logger.info(f"{email} 验证成功")
        return jsonify({'success': True, 'message': '验证成功！您可以使用此验证码加入QQ群'})
    except SQLAlchemyError as e:
        logger.error(f"验证失败: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': '系统错误'}), 500

# 数据库测试端点
@app.route('/db_test')
def db_test():
    """测试数据库连接"""
    try:
        db.session.execute("SELECT 1")
        return "数据库连接成功"
    except Exception as e:
        return f"数据库连接失败: {str(e)}"

# 邮件测试端点
@app.route('/mail_test')
def mail_test():
    """测试邮件发送"""
    try:
        success = send_verification_email("test@example.com", "123456")
        return "邮件发送成功" if success else "邮件发送失败"
    except Exception as e:
        return f"邮件错误: {str(e)}"

# 日志查看端点
@app.route('/logs')
def view_logs():
    """查看日志"""
    # 在实际环境中，您可能需要从文件系统读取日志
    return "日志查看功能需要配置日志文件"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
