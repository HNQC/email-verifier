const { Pool } = require('pg');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: { rejectUnauthorized: false }
});

// 创建验证码表
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
  }
}

createTable();

module.exports = {
  query: (text, params) => pool.query(text, params),
};
