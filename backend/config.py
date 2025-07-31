import os

SENDCLOUD_API_USER = os.environ.get('SENDCLOUD_API_USER', 'HNQC2025')
SENDCLOUD_API_KEY = os.environ.get('SENDCLOUD_API_KEY', '09ea3daff4c5698556dfa85bc7471892')
FROM_DOMAIN = os.environ.get('SENDCLOUD_FROM_DOMAIN', 'hnqc.dpdns.org')
FROM_EMAIL = os.environ.get('SENDCLOUD_FROM', 'rbx-hnqc@outlook.com')

# 数据库配置
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'mysql'),
    'user': os.environ.get('DB_USER', 'root'),  # 这里建议用 root，除非你目标数据库用户名确实是 mysql
    'password': os.environ.get('DB_PASSWORD', ''),
    'database': os.environ.get('DB_NAME', 'zeabur')
}

EMAIL_TEMPLATE = """
<html>
<body style="font-family: Arial, sans-serif; background-color: #0a0a15; color: #e0e0ff; padding: 20px;">
    <div style="max-width: 600px; margin: 0 auto; background: rgba(15, 15, 30, 0.8); border-radius: 16px; padding: 30px; border: 1px solid rgba(42, 148, 224, 0.3);">
        <h1 style="text-align: center; color: #2a94e0; margin-bottom: 30px;">HNQC验证码</h1>
        <p style="font-size: 18px; line-height: 1.6;">您的验证码是：</p>
        <div style="font-size: 32px; font-weight: bold; color: #2a94e0; text-align: center; margin: 30px 0; letter-spacing: 5px;">{code}</div>
        <p style="font-size: 16px; color: #a0a0c0;">请在10分钟内使用此验证码完成验证。</p>
        <p style="font-size: 14px; color: #8888bb; margin-top: 30px; border-top: 1px solid rgba(42, 148, 224, 0.2); padding-top: 20px;">
            此邮件由HNQC验证系统自动发送，请勿回复。
        </p>
    </div>
</body>
</html>
"""
