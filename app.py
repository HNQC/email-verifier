import os
import random
import time
import logging
import threading
import requests
import re
import json
from datetime import datetime, timedelta
from flask import Flask, request, jsonify, render_template
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import text

app = Flask(__name__)

# 数据库配置
app.config['SQLALCHEMY_DATABASE_URI'] = (
    f"mysql+pymysql://{os.environ['MYSQL_USERNAME']}:{os.environ['MYSQL_PASSWORD']}"
    f"@{os.environ['MYSQL_HOST']}:{os.environ['MYSQL_PORT']}/{os.environ['MYSQL_DATABASE']}"
)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
    'pool_size': 5,
    'pool_recycle': 300,
    'pool_pre_ping': True
}

# SendCloud 配置
app.config['SENDCLOUD_API_USER'] = os.getenv('SENDCLOUD_API_USER', 'sc_yg739l_test_N8nase')
app.config['SENDCLOUD_API_KEY'] = os.getenv('SENDCLOUD_API_KEY', 'e0ca44d9578a1db2b71b9ca2198daf2e')
app.config['SENDCLOUD_FROM_EMAIL'] = os.getenv('SENDCLOUD_FROM_EMAIL', 'no-reply@sendcloud.com')
app.config['SENDCLOUD_FROM_NAME'] = os.getenv('SENDCLOUD_FROM_NAME', 'QQ群验证服务')
app.config['CODE_LENGTH'] = 6
app.config['CODE_EXPIRY'] = 300  # 5分钟
app.config['ZEABUR_URL'] = os.getenv('ZEABUR_URL', 'https://qq-verifier.zeabur.app')
app.config['DISPOSABLE_DOMAINS'] = [
    'mailinator.com', 'tempmail.com', '10minutemail.com',
    'guerrillamail.com', 'trashmail.com', 'yopmail.com'
]

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

# 邮箱验证函数
def validate_email(email):
    """验证邮箱格式并返回规范化邮箱"""
    # 基本格式验证
    if not re.match(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$", email):
        return None
    
    # 拆分邮箱地址
    local_part, domain = email.split('@')
    
    # 规范化邮箱（小写处理）
    normalized_email = f"{local_part.lower()}@{domain.lower()}"
    
    # 检查一次性邮箱域名
    if domain.lower() in app.config['DISPOSABLE_DOMAINS']:
        return None
    
    return normalized_email

# 添加邮箱到 SendCloud 白名单
def add_to_sendcloud_whitelist(email):
    """将邮箱添加到 SendCloud 白名单"""
    try:
        api_user = app.config['SENDCLOUD_API_USER']
        api_key = app.config['SENDCLOUD_API_KEY']
        
        url = "https://api.sendcloud.net/apiv2/whitelist/add"
        data = {
            "apiUser": api_user,
            "apiKey": api_key,
            "mailAddress": email
        }
        
        response = requests.post(url, data=data)
        
        # 尝试解析响应
        try:
            result = response.json()
        except json.JSONDecodeError:
            logger.error(f"添加白名单响应不是有效的JSON: {response.text}")
            return False
        
        if result.get('result') == True:
            logger.info(f"已将 {email} 添加到 SendCloud 白名单")
            return True
        else:
            error_msg = result.get('message', '未知错误')
            logger.error(f"添加白名单失败: {error_msg}")
            return False
    except Exception as e:
        logger.error(f"添加白名单失败: {str(e)}")
        return False

# 发送验证码邮件（使用 SendCloud API）
def send_verification_email(to_email, code):
    try:
        # 验证邮箱格式
        validated_email = validate_email(to_email)
        if not validated_email:
            logger.error(f"无效邮箱地址: {to_email}")
            return {
                'success': False,
                'error': '无效邮箱地址',
                'details': '请提供有效的邮箱地址'
            }
        
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
                <p>QQ机器人会自动验证您的验证码。</p>
                <p style="font-size: 12px; color: #666;">
                    如果您不希望再收到此类邮件，
                    <a href="https://yourdomain.com/unsubscribe?email={to_email}">点击退订</a>
                </p>
            </body>
        </html>
        """
        
        # 构建 API 请求
        url = "https://api.sendcloud.net/apiv2/mail/send"
        data = {
            "apiUser": api_user,
            "apiKey": api_key,
            "from": f"{from_name} <{from_email}>",
            "to": validated_email,
            "subject": subject,
            "html": html_content,
            "respEmailId": "true"
        }
        
        # 发送请求
        response = requests.post(url, data=data)
        
        # 尝试解析响应
        try:
            result = response.json()
        except json.JSONDecodeError:
            logger.error(f"SendCloud响应不是有效的JSON: {response.text}")
            return {
                'success': False,
                'error': '邮件发送失败',
                'details': 'SendCloud响应格式错误'
            }
        
        # 检查响应
        if result.get('result') == True:
            logger.info(f"邮件成功发送至 {validated_email}")
            return True
        else:
            error_msg = result.get('message', '未知错误')
            logger.error(f"邮件发送失败: {error_msg}")
            
            # 处理特定错误
            if "invalid email" in error_msg.lower():
                return {
                    'success': False,
                    'error': '无效邮箱地址',
                    'details': '请提供有效的邮箱地址'
                }
            elif "quota" in error_msg.lower():
                return {
                    'success': False,
                    'error': '发送配额不足',
                    'details': '已达到每日发送限制'
                }
            elif "not in whitelist" in error_msg.lower():
                # 自动添加到白名单
                if add_to_sendcloud_whitelist(validated_email):
                    # 重试发送邮件
                    logger.info(f"重试发送邮件至 {validated_email}")
                    response = requests.post(url, data=data)
                    
                    try:
                        result = response.json()
                    except json.JSONDecodeError:
                        logger.error(f"SendCloud响应不是有效的JSON: {response.text}")
                        return {
                            'success': False,
                            'error': '邮件发送失败',
                            'details': 'SendCloud响应格式错误'
                        }
                    
                    if result.get('result') == True:
                        logger.info(f"邮件成功发送至 {validated_email} (重试)")
                        return True
                    else:
                        error_msg = result.get('message', '未知错误')
                        logger.error(f"邮件发送失败 (重试): {error_msg}")
                        return {
                            'success': False,
                            'error': '邮件发送失败',
                            'details': f"重试失败: {error_msg}"
                        }
                else:
                    return {
                        'success': False,
                        'error': '邮件发送失败',
                        'details': '无法将邮箱添加到白名单'
                    }
            else:
                return {
                    'success': False,
                    'error': '邮件发送失败',
                    'details': error_msg
                }
    except Exception as e:
        logger.error(f"发送邮件失败: {str(e)}")
        return {
            'success': False,
            'error': '邮件发送失败',
            'details': str(e)
        }

# 清理过期验证码
def clean_expired_codes():
    expired_time = time.time() - app.config['CODE_EXPIRY']
    try:
        # 删除过期验证码
        VerificationCode.query.filter(
            VerificationCode.created_at < expired_time
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
    validated_email = validate_email(email)
    if not validated_email:
        return jsonify({
            'success': False,
            'error': '无效邮箱地址',
            'details': '请提供有效的邮箱地址'
        }), 400
    
    # 清理过期验证码
    clean_expired_codes()
    
    # 生成随机验证码
    code = ''.join(random.choices('0123456789', k=app.config['CODE_LENGTH']))
    
    # 保存到数据库
    try:
        # 使用 upsert 操作（存在则更新，不存在则插入）
        existing_code = VerificationCode.query.get(validated_email)
        if existing_code:
            existing_code.code = code
            existing_code.created_at = time.time()
        else:
            new_code = VerificationCode(
                email=validated_email,
                code=code,
                created_at=time.time()
            )
            db.session.add(new_code)
        
        db.session.commit()
        logger.info(f"为 {validated_email} 生成验证码: {code}")
    except SQLAlchemyError as e:
        logger.error(f"数据库错误: {str(e)}")
        db.session.rollback()
        return jsonify({'success': False, 'error': '系统错误'}), 500
    
    # 发送邮件
    result = send_verification_email(validated_email, code)
    
    if result is True:
        return jsonify({
            'success': True,
            'message': '验证码已发送',
            'instructions': '请将验证码提供给QQ机器人进行验证'
        })
    elif isinstance(result, dict):
        return jsonify(result)
    else:
        return jsonify({
            'success': False,
            'error': '邮件发送失败',
            'details': '未知错误'
        })

# 邮件测试端点
@app.route('/mail_test')
def mail_test():
    """测试邮件发送"""
    try:
        result = send_verification_email("test@example.com", "123456")
        if result is True:
            return "邮件发送成功"
        elif isinstance(result, dict):
            return jsonify(result)
        else:
            return "邮件发送失败"
    except Exception as e:
        return f"邮件错误: {str(e)}"

# 发送记录端点
@app.route('/send_records')
def send_records():
    """查看发送记录"""
    try:
        # 获取 SendCloud 发送记录
        api_user = app.config['SENDCLOUD_API_USER']
        api_key = app.config['SENDCLOUD_API_KEY']
        
        # 使用正确的API端点
        url = "https://api.sendcloud.net/apiv2/mail/stat/list"
        params = {
            "apiUser": api_user,
            "apiKey": api_key,
            "startDate": (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d"),
            "endDate": datetime.now().strftime("%Y-%m-%d"),
            "limit": 100
        }
        
        response = requests.get(url, params=params)
        
        # 尝试解析响应
        try:
            result = response.json()
        except json.JSONDecodeError:
            logger.error(f"SendCloud响应不是有效的JSON: {response.text}")
            return f"获取发送记录失败: 响应不是有效的JSON，原始响应: {response.text}"
        
        if result.get('result') == True:
            records = result.get('info', {}).get('dataList', [])
            return jsonify(records)
        else:
            error_msg = result.get('message', '未知错误')
            return f"获取发送记录失败: {error_msg}"
    except Exception as e:
        return f"获取发送记录失败: {str(e)}"

# 数据库测试端点
@app.route('/db_test')
def db_test():
    """测试数据库连接"""
    try:
        # 使用 text() 包装 SQL 语句
        db.session.execute(text("SELECT 1"))
        return "数据库连接成功"
    except Exception as e:
        return f"数据库连接失败: {str(e)}"

# 白名单检查端点
@app.route('/check_whitelist')
def check_whitelist():
    """检查邮箱是否在白名单中"""
    try:
        # 获取邮箱参数
        email = request.args.get('email', '')
        if not email:
            return "请提供邮箱参数，例如：/check_whitelist?email=your@email.com"
        
        # 验证邮箱格式
        validated_email = validate_email(email)
        if not validated_email:
            return "无效邮箱地址"
        
        # 尝试发送测试邮件
        result = send_verification_email(validated_email, "000000")
        
        if result is True:
            return f"邮箱 {validated_email} 在白名单中"
        elif isinstance(result, dict) and "not in whitelist" in result.get('details', '').lower():
            return f"邮箱 {validated_email} 不在白名单中"
        else:
            return f"检查失败: {result.get('details', '未知错误')}"
    except Exception as e:
        return f"检查失败: {str(e)}"

# 添加白名单端点
@app.route('/add_whitelist')
def add_whitelist():
    """手动添加邮箱到白名单"""
    try:
        # 获取邮箱参数
        email = request.args.get('email', '')
        if not email:
            return "请提供邮箱参数，例如：/add_whitelist?email=your@email.com"
        
        # 验证邮箱格式
        validated_email = validate_email(email)
        if not validated_email:
            return "无效邮箱地址"
        
        # 添加到白名单
        if add_to_sendcloud_whitelist(validated_email):
            return f"已将 {validated_email} 添加到白名单"
        else:
            return f"添加白名单失败"
    except Exception as e:
        return f"添加白名单失败: {str(e)}"

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
