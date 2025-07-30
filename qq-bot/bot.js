const { createBot } = require('qq-guild-bot');
const axios = require('axios');

// 强校验环境变量
if (!process.env.QQ_APP_ID || !process.env.QQ_BOT_TOKEN || !process.env.BACKEND_URL) {
  console.error('QQ机器人环境变量未配置');
  process.exit(1);
}

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
    
    console.log(`收到入群申请: 用户 ${userId}, 群组 ${groupId}, 理由: ${reason}`);
    
    // 提取邮箱和验证码
    const match = reason.match(/(\w+@\w+\.\w+)\s+(\d{6})/);
    
    if (!match) {
      console.log('未提供有效的邮箱和验证码');
      bot.setGroupAddRequest(event.flag, 'add', false, '请提供有效的邮箱和验证码');
      return;
    }
    
    const email = match[1];
    const code = match[2];
    
    console.log(`提取邮箱: ${email}, 验证码: ${code}`);
    
    // 验证验证码
    const response = await axios.post(`${process.env.BACKEND_URL}/verify-code`, {
      email,
      code
    });
    
    if (response.data.success) {
      console.log('验证码验证成功');
      // 验证通过，同意入群
      bot.setGroupAddRequest(event.flag, 'add', true);
      
      // 发送欢迎消息
      setTimeout(() => {
        bot.sendGroupMsg(groupId, `欢迎新成员 [CQ:at,qq=${userId}] 加入本群！`);
      }, 1000);
    } else {
      console.log('验证码验证失败:', response.data.error);
      // 验证失败，拒绝入群
      bot.setGroupAddRequest(event.flag, 'add', false, response.data.error || '验证码无效或已过期');
    }
  } catch (error) {
    console.error('处理入群申请失败:', error);
    bot.setGroupAddRequest(event.flag, 'add', false, '验证服务暂时不可用');
  }
});

// 启动机器人
bot.connect();
