import React, { useState } from 'react';
import './App.css';

function App() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleSendCode = async () => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setMessage('请输入有效的邮箱地址');
      return;
    }

    setIsLoading(true);
    setMessage('');

    try {
      const response = await fetch('/send-code', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage('验证码已发送到您的邮箱，请查收并填写到QQ入群申请中');
      } else {
        setMessage(data.error || '发送验证码失败');
      }
    } catch (error) {
      setMessage('网络错误，请重试');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="container">
      <div className="card">
        <h1>QQ群验证服务</h1>
        
        {message && <div className={`message ${message.includes('成功') ? 'success' : 'error'}`}>{message}</div>}
        
        <div className="form-group">
          <label htmlFor="email">您的邮箱：</label>
          <input
            type="email"
            id="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            placeholder="例如：yourname@example.com"
            disabled={isLoading}
          />
          <button onClick={handleSendCode} disabled={isLoading}>
            {isLoading ? '发送中...' : '获取QQ群验证码'}
          </button>
        </div>
        
        <div className="instructions">
          <h3>使用说明</h3>
          <ol>
            <li>输入您的邮箱地址</li>
            <li>点击"获取QQ群验证码"按钮</li>
            <li>查收邮件获取验证码</li>
            <li>在QQ入群申请中填写验证码</li>
            <li>QQ机器人会自动验证并处理您的入群申请</li>
          </ol>
        </div>
        
        <div className="info">
          <p><strong>注意：</strong>验证码5分钟内有效，请及时使用</p>
          <p>如有问题，请联系QQ群管理员</p>
        </div>
      </div>
    </div>
  );
}

export default App;
