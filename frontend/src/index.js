// frontend/src/index.js
const { useState } = React;

function App() {
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [messageType, setMessageType] = useState('');

  const handleSendCode = async () => {
    if (!email || !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
      setMessage('请输入有效的邮箱地址');
      setMessageType('error');
      return;
    }

    setIsLoading(true);
    setMessage('');
    setMessageType('');

    try {
      const response = await fetch('/send-code', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ email })
      });

      const data = await response.json();

      if (response.ok) {
        setMessage('验证码已发送到您的邮箱，请查收并填写到QQ入群申请中');
        setMessageType('success');
      } else {
        setMessage(data.error || '发送验证码失败');
        setMessageType('error');
      }
    } catch (error) {
      setMessage('网络错误，请重试');
      setMessageType('error');
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div>
      {message && (
        <div className={`message ${messageType === 'success' ? 'success' : 'error'}`}>
          {message}
        </div>
      )}
      
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
        <button 
          className="button" 
          onClick={handleSendCode} 
          disabled={isLoading}
        >
          {isLoading ? (
            <span>
              <i className="fas fa-spinner fa-spin"></i> 发送中...
            </span>
          ) : (
            <span>
              <i className="fas fa-paper-plane"></i> 获取QQ群验证码
            </span>
          )}
        </button>
      </div>
      
      <div className="instructions">
        <h3><i className="fas fa-info-circle"></i> 使用说明</h3>
        <ol>
          <li>输入您的邮箱地址</li>
          <li>点击"获取QQ群验证码"按钮</li>
          <li>查收邮件获取验证码</li>
          <li>在QQ入群申请中填写验证码</li>
          <li>QQ机器人会自动验证并处理您的入群申请</li>
        </ol>
      </div>
      
      <div className="info">
        <p><i className="fas fa-exclamation-circle"></i> <strong>注意：</strong></p>
        <p>• 验证码5分钟内有效，请及时使用</p>
        <p>• 每个邮箱每天最多可获取3次验证码</p>
        <p>• 如有问题，请联系QQ群管理员</p>
      </div>
    </div>
  );
}

ReactDOM.render(<App />, document.getElementById('app'));
