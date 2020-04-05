# ip_bot
 This bot is used for regularly checking if the public IP changed then sends the new IP in discord. This uses webhooks to send ip updates to discord.
 When this bot check the public ip, it will use http://ipinfo.io/ip to receive the IP from.
 
 ##Configuration
 
 To use this bot. Create a local ``.env`` file with the values:
 
```
TOKEN=<token>
WEBHOOK=<webhook_url>
```

There are also more configuration on top of bot.py

```Python
DEBUG_ID = [109093669042151424]
CHECK_EVERY = 1800  # 30 minutes
TRUSTED_ROLE = 690223202420785260
```
DEBUG_ID is a list of user IDs. It will be users who get the highest role. Basically, when there are errors it will be DMed to these users, and they can use commands anywhere in the guild and in DMs

CHECK_EVERY is how many times in seconds to check the IP. This will use ipinfo website to grab the IP from. Just note, don't over do it. I'm not sure on their policy on multiple checks, but I believe they don't want to be spammed with calls

TRUSTED_ROLE is users who can use the bot. This is different from DEBUG_ID users, since trusted users can only use commands in the guild not in DMs
