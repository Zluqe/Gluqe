import os

async def load_cogs(bot):
    for filename in os.listdir('./src/cogs'):
        if filename.endswith('.py'):
            try:
                await bot.load_extension(f'src.cogs.{filename[:-3]}')
                print(f'Loaded cog: {filename}')
            except Exception as e:
                print(f'❌ Failed to load cog {filename}: {e}')