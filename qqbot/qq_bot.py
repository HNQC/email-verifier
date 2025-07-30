import re
from datetime import datetime, timedelta
import mysql.connector
from qqbot import QQBot, Event
from qqbot.command import MessageCommand

# 数据库配置（与后端服务一致）
DB_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'your_mysql_password',  # 替换为你的MySQL密码
    'database': 'hnqc_verification'
}

# 创建数据库连接
def create_db_connection():
    return mysql.connector.connect(**DB_CONFIG)

# 验证验证码是否有效
def verify_verification_code(email, code):
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    
    cursor.execute(
        "SELECT * FROM verification_codes WHERE email = %s AND code = %s AND created_at > %s AND used = 0",
        (email, code, datetime.now() - timedelta(minutes=10))
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if result:
        # 标记为已使用
        conn = create_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE verification_codes SET used = 1 WHERE id = %s", (result['id'],))
        conn.commit()
        cursor.close()
        conn.close()
        return True
    
    return False

# 处理入群申请事件
def handle_group_invite(event: Event, bot: QQBot):
    # 从事件中提取信息
    group_id = event.group_id
    user_id = event.user_id
    message = event.content.strip()
    
    # 使用正则提取验证码（6位数字）
    match = re.search(r'(\d{6})', message)
    if not match:
        bot.reject_group_apply(group_id, user_id, "请提供有效的6位验证码")
        return
    
    code = match.group(1)
    
    # 验证验证码
    # 注意：这里需要先获取用户邮箱，实际使用中需要通过其他方式获取
    # 可以根据实际场景调整，例如要求用户提前在网站上绑定QQ号
    
    # 这里简化为验证数据库中的第一个匹配项
    conn = create_db_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT email FROM verification_codes WHERE code = %s AND created_at > %s AND used = 0",
        (code, datetime.now() - timedelta(minutes=10))
    )
    result = cursor.fetchone()
    cursor.close()
    conn.close()
    
    if result:
        # 标记为已使用
        conn = create_db_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE verification_codes SET used = 1 WHERE code = %s", (code,))
        conn.commit()
        cursor.close()
        conn.close()
        
        bot.approve_group_apply(group_id, user_id)
    else:
        bot.reject_group_apply(group_id, user_id, "验证码无效或已过期")

# 主函数
def main():
    # 创建QQ机器人实例
    bot = QQBot()
    # 注册群申请事件处理器
    bot.on('group.apply', handle_group_invite)
    # 启动机器人
    bot.start()

if __name__ == '__main__':
    main()
