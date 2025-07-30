require('dotenv').config();
const express = require('express');
const bodyParser = require('body-parser');
const { v4: uuidv4 } = require('uuid');
const nodemailer = require('nodemailer');
const { Pool } = require('pg');

// 强校验关键环境变量
['DATABASE_URL', 'EMAIL_USER', 'EMAIL_PASS'].forEach(env => {
  if (!process.env[env]) {
    console.error(`环境变量${env}未配置，服务无法启动！`);
    process.exit(1);
  }
});

const app = express();
app.use(bodyParser.json());

// 健康检查接口
app.get('/health', (req, res) => {
  res.status(200).json({ status: 'ok' });
});

// 解析数据库连接字符串
function parseDbUrl(url) {
  const pattern = /^(?:([^:\/?#\s]+):\/\/)?(?:([^@\/?#\s]+)@)?([^\/?#\s]+)?(?:\/([^?#\s]*))?(?:[?]([^#\s]*))?(?:#(.*))?$/;
  const matches = url.match(pattern);
  
  if (!matches) {
    throw new Error('无效的数据库连接字符串');
  }
  
  return {
    user: matches[2] ? matches[2].split(':')[0] : undefined,
    password: matches[2] ? matches[2].split(':')[1] : undefined,
    host: matches[3] ? matches[3].split(':')[0] : undefined,
    port: matches[3] ? matches[3].split(':')[1] : undefined,
    database: matches[4],
    ssl: { rejectUnauthorized: false }
  };
}

// 创建数据库连接池
let pool;
try {
  const config = parseDbUrl(process.env.DATABASE_URL);
  pool = new Pool(config);
  console.log('数据库配置解析成功');
} catch (error) {
  console.error('数据库配置解析失败:', error);
  process.exit(1);
}

// 初始化表
async function createTable() {
  try {
    await pool.query(`
      CREATE TABLE IF NOT EXISTS verification_codes (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
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

// 邮件发送配置
const transporter = nodemailer.createTransport({
  host: 'smtp.forwardemail.net',
  port: 465,
  secure: true,
  auth: {
    user: process.env.EMAIL_USER,
    pass: process.env.EMAIL_PASS
  }
});

// 发送验证码接口
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
      'INSERT INTO verification_codes (id, email, code) VALUES ($1, $2, $3)',
      [id, email, code]
    );

    // 发送邮件
    await transporter.sendMail({
      from: `"[HNQC]验证码服务" <verify@hnqc.dpdns.org>`,
      to: email,
      subject: '[HNQC]您的QQ群验证码',
      html: `<div>您的验证码是：<b>${code}</b></div>`
    });
    
    res.json({ success: true, message: '验证码已发送' });
  } catch (error) {
    console.error('发送验证码失败:', error);
    res.status(500).json({ error: '发送验证码失败', detail: error.message || error });
  }
});

// 验证接口
app.post('/verify-code', async (req, res) => {
  const { email, code } = req.body;
  
  if (!email || !code) {
    return res.status(400).json({ error: '邮箱和验证码不能为空' });
  }
  
  try {
    // 查找验证码
    const result = await pool.query(
      `SELECT * FROM verification_codes 
       WHERE email = $1 AND code = $2 
       AND created_at > NOW() - INTERVAL '5 minutes'
       AND is_used = false`,
      [email, code]
    );
    
    if (result.rows.length === 0) {
      return res.status(400).json({ error: '验证码无效或已过期' });
    }
    
    // 标记为已使用
    await pool.query(
      'UPDATE verification_codes SET is_used = true WHERE id = $1',
      [result.rows[0].id]
    );
    
    res.json({ success: true, message: '验证成功' });
  } catch (error) {
    console.error('验证失败:', error);
    res.status(500).json({ error: '验证失败', detail: error.message || error });
  }
});

// 定时清理验证码
setInterval(async () => {
  try {
    await pool.query("DELETE FROM verification_codes WHERE created_at < NOW() - INTERVAL '10 minutes'");
    console.log('已清理过期验证码');
  } catch (error) {
    console.error('清理验证码失败:', error);
  }
}, 10 * 60 * 1000); // 每10分钟清理一次

// 云平台端口监听
const PORT = process.env.PORT || 3000;
app.listen(PORT, () => {
  console.log(`后端服务运行在端口 ${PORT}`);
});
