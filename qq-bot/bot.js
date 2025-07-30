const { createBot } = require('qq-guild-bot');
const axios = require('axios');

const bot = createBot({
  appID: process.env.QQ_APP_ID,
  token: process.env.QQ_BOT_TOKEN,
  intents: ['PUBLIC_GUILD_MESSAGES'],
});

// 监听入群申请
bot.on('GROUP_ADD_REQUEST', async (event) => {
  try {
    const userId = event.user_id;
    const groupId = event.group_id;
    const reason = event.comment; // 用户填写的入群理由
    
    // 提取邮箱和验证码
    const match = reason.match(/(\w+@\w+\.\w+)\s+(\d{6})/);
    
    if (!match) {
      // 没有提供验证码，拒绝入群
      bot.setGroupAddRequest(event.flag, 'add', false, '请提供有效的邮箱和验证码');
      return;
    }
    
    const email = match[1];
    const code = match[2];
    
    // 验证验证码
    const response = await axios.post('http://your-backend-url/verify-code', {
      email,
      code
    });
    
    if (response.data.success) {
      // 验证通过，同意入群
      bot.setGroupAddRequest(event.flag, 'add', true);
      
      // 发送欢迎消息
      bot.sendGroupMsg(groupId, `欢迎新成员 [CQ:at,qq=${userId}] 加入[HNQC]！`);
    } else {
      // 验证失败，拒绝入群
      bot.setGroupAddRequest(event.flag, 'add', false, '验证码无效或已过期');
    }
  } catch (error) {
    console.error('处理入群申请失败:', error);
    bot.setGroupAddRequest(event.flag, 'add', false, '验证服务暂时不可用');
  }
});

// 启动机器人
bot.connect();
