import discord, yaml
from discord.ext import commands
from pydactyl import PterodactylClient
from helpers.checks import is_blacklisted, is_owner, load_blacklist

# Load configuration data from a YAML file
def load_config():
    with open('config.yml', 'r') as f:
        return yaml.safe_load(f)

# Fetch the total count of users
def get_total_users():
    config = load_config()
    api = PterodactylClient(config['panel']['url'], config['panel']['api'])
    users = api.user.list_users()
    total_users = len(users['data'])
    return total_users

class NodeStats(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        config = load_config()
        self.api = PterodactylClient(config['panel']['url'], config['panel']['api'])

    @commands.hybrid_command(name='nodestats')
    @is_blacklisted()
    async def roles_command(self, ctx: commands.Context) -> None:
        """
        Displays stats for all nodes.
        """
        # Fetch node stats
        nodes = self.api.nodes.list_nodes()
        nodes_data = nodes.collect() if hasattr(nodes, 'collect') else list(nodes)

        embed = discord.Embed(
            title="Node Stats",
            description="Here are the stats for all nodes:",
            color=discord.Color.blue()
        )

        for node in nodes_data:
            attributes = node['attributes']
            name = attributes['name']
            total_memory = attributes['memory']
            used_memory = attributes['allocated_resources'].get('memory', 0)
            total_disk = attributes['disk']
            used_disk = attributes['allocated_resources'].get('disk', 0)
            fdqn = attributes['fqdn']

            embed.add_field(
                name=f"**{name}** - {fdqn}",
                value=(
                    f"- **Memory Allocated:** ``{used_memory}`` MB / ``{total_memory}`` MB\n"
                    f"- **Storage Allocated:** ``{used_disk}`` MB / ``{total_disk}`` MB"
                ),
                inline=False
            )
            embed.set_footer(text="Total Users: " + str(get_total_users()) + " • Powered by Zluqe")

        await ctx.send(embed=embed)


async def setup(bot):
    await bot.add_cog(NodeStats(bot))