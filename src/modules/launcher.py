from datetime import datetime

class Launch():
    def __init__(self, bot, token):
        self.bot = bot
        self.setup_events()
        self.bot.loop.create_task(self.start(token))

    def setup_events(self):
        @self.bot.event
        async def on_ready():
            print(f'🔱 On {len(self.bot.guilds)} guilds')
            print(f'🔱 Logged in as {self.bot.user} (ID: {self.bot.user.id})')
            print(f'🔱 Connected at {datetime.now().strftime('%H:%M:%S')}')
            print('=' * 25)

    async def start(self, token):
        try:
            self.bot.run(token)
        except Exception as e:
            print("Failed to start bot")
            print(e)
            exit()