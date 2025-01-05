from datetime import datetime

async def setup_events(bot):
    @bot.event
    async def on_ready():
        print(f'On {len(bot.guilds)} guilds')
        print(f'Logged in as {bot.user} (ID: {bot.user.id})')
        print(f'Connected at {datetime.now().strftime('%H:%M:%S')}')
        print('=' * 25)

async def start(bot, token):
    try:
        await bot.start(token)
    except Exception as e:
        print("Failed to start bot")
        print(e)
        exit()