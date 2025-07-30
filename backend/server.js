require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const { v4: uuidv4 } = require('uuid');
const nodemailer = require('nodemailer');
const mysql = require('mysql2/promise');

const app = express();
app.use(bodyParser.json());

// 强校验关键环境变量
['MYSQL_HOST', 'MYSQL_USER', 'MYSQL_PASSWORD', 'MYSQL_DATABASE', 
 'EMAIL_USER', 'EMAIL_PASS'].forEach(env => {
  if (!process.env[env]) {
    console.error(`环境变量${env}未配置，服务无法启动！`);
    process.exit(1);
  }
});

// MySQL 连接池
const pool = mysql.createPool({
  host: process.env.MYSQL_HOST,
  user: process.env.MYSQL_USER,
  password: process.env.MYSQL_PASSWORD,
  database: process.env.MYSQL_DATABASE,
  waitForConnections: true,
  connectionLimit: 10,
  queueLimit: 0
});

// 创建表
async function createTable() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS verification_codes (
        id VARCHAR(36) PRIMARY KEY,
        email VARCHAR(255) NOT NULL,
        code VARCHAR(6) NOT NULL,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        is_used BOOLEAN DEFAULT false
      )
    `);
    console.log('数据库表创建成功');
  } catch (err) {
    console.error('数据库表创建失败:', err);
    process.exit(1);
  }
}

createTable();

// SendCloud 邮件配置
const transporter = nodemailer.createTransport({
  host: 'smtp.sendcloud.net',
  port: 465,
  secure: true,
  auth: {
    user: process.env.EMAIL_USER, // HNQC2025
    pass: process.env.EMAIL_PASS  // 97b07234f8299cbc80c22768016a8cef
  }
});

// 发送验证码
app.post('/send-code', async (req, res) => {
  const { email } = req.body;
  
  if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
    return res.status(400).json({ error: '无效的邮箱地址' });
  }

  const code = Math.floor(100000 + Math.random() * 900000).toString();
  const id = uuidv4();

  try {
    // 保存到数据库
    await pool.query(
      'INSERT INTO verification_codes (id, email, code) VALUES (?, ?, ?)',
      [id, email, code]
    );

    // 发送邮件
    await transporter.sendMail({
      from: `"QQ群验证服务" <verify@hnqc.dpdns.org>`,
      to: email,
      subject: '您的QQ群验证码',
      html: `
        <div style="font-family: Arial, sans-serif; max-width: 600px; margin: 0 auto;">
          <h2 style="color: #1a73e8;">QQ群验证信息</h2>
          <p>您请求的验证码是：</p>
          <div style="background: #f8f9fa; border: 1px dashed #dadce0; 
              padding: 15px; text-align: center; margin: 20px 0; 
              font-size: 24px; font-weight: bold; color: #1a73e8;">
            ${code}
          </div>
          <p>请在申请加入QQ群时在「入群理由」中填写此验证码。</p>
          <p>提示：该验证码5分钟内有效。</p>
          <p>QQ机器人会自动验证您的验证码。</p>
        </div>
      `
    });

    res.json({ success: true, message: '验证码已发送' });
  } catch (error) {
    console.error('发送验证码失败:', error);
    res.status(500).json({ error: '发送验证码失败' });
  }
});

// 验证验证码
app.post('/verify-code', async (req, res) => {
  const { email, code } = req.body;
  
  if (!email || !code) {
    return res.status(400).json({ error: '邮箱和验证码不能为空' });
  }

  try {
    // 查找验证码
    const [rows] = await pool.query(
      `SELECT * FROM verification_codes 
       WHERE email = ? AND code = ? 
       AND created_at > NOW() - INTERVAL 5 MINUTE
       AND is_used = false`,
      [email, code]
    );

    if (rows.length === 0) {
      return res.status(400).json({ error: '验证码无效或已过期' });
    }

    // 标记为已使用
    await pool.query(
      'UPDATE verification_codes SET is_used = true WHERE id = ?',
      [rows[0].id]
    );

    res.json({ success: true, message: '验证成功' });
  } catch (error) {
    console.error('验证失败:', error);
    res.status(500).json({ error: '验证失败' });
  }
});

// 清理过期验证码
setInterval(async () => {
  try {
    await pool.query(
      "DELETE FROM verification_codes WHERE created_at < NOW() - INTERVAL 10 MINUTE"
    );
    console.log('已清理过期验证码');
  } catch (error) {
    console.error('清理验证码失败:', error);
  }
}, 10 * 60 * 1000); // 每10分钟清理一次

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`后端服务运行在端口 ${PORT}`);
});
