import discord, yaml
from discord.ext import commands
from discord import app_commands
from pydactyl import PterodactylClient
from collections import defaultdict
from helpers.checks import is_blacklisted

# Load configuration data from a YAML file
def load_config():
    with open('config.yml', 'r') as f:
        return yaml.safe_load(f)

# Total Users
def get_total_users():
    config = load_config()
    api = PterodactylClient(config['panel']['url'], config['panel']['api'])

    total_users = 0
    page = 1

    while True:
        users_page = api.user.list_users(params={'page': page, 'per_page': 100})
        users = users_page.get('data', [])
        total_users += len(users)

        if len(users) < 100:
            break

        page += 1

    return total_users

class Pterodactyl(commands.Cog):
    def __init__(self, bot):
        self.bot = bot
        config = load_config()
        self.api = PterodactylClient(config['panel']['url'], config['panel']['api'])

    @commands.hybrid_command(name='nodestats')
    @app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
    @is_blacklisted()
    async def roles_command(self, ctx: commands.Context) -> None:
        """
        Displays stats for all nodes, including total servers per node.
        """
        try:
            servers = self.api.servers.list_servers().collect()
            servers_per_node = defaultdict(int)

            for server in servers:
                node_id = server['attributes'].get('node')
                if node_id is not None:
                    servers_per_node[node_id] += 1

            nodes = self.api.nodes.list_nodes()
            nodes_data = nodes.collect() if hasattr(nodes, 'collect') else list(nodes)

            embed = discord.Embed(
                title="🖥️ Node Stats",
                description="Here are the stats for all nodes:",
                color=discord.Color.blue()
            )

            for node in nodes_data:
                attributes = node['attributes']
                node_id = attributes['id']
                name = attributes['name']
                fqdn = attributes['fqdn']
                total_memory = attributes['memory']
                used_memory = attributes['allocated_resources'].get('memory', 0)
                total_disk = attributes['disk']
                used_disk = attributes['allocated_resources'].get('disk', 0)
                total_servers = servers_per_node.get(node_id, 0)

                embed.add_field(
                    name=f"**{name}** - {fqdn}",
                    value=(
                        f"- **Memory Allocated:** `{used_memory}` MB / `{total_memory}` MB\n"
                        f"- **Storage Allocated:** `{used_disk}` MB / `{total_disk}` MB\n"
                        f"- **Total Servers:** `{total_servers}`"
                    ),
                    inline=False
                )

            embed.set_footer(text="Total Users: " + str(get_total_users()) + " • Powered by Zluqe")
            await ctx.send(embed=embed)

        except Exception as e:
            await ctx.send(f"❌ Error fetching node stats: {e}")

async def setup(bot):
    await bot.add_cog(Pterodactyl(bot))
