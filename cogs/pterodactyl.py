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

# Fetch the total count of users
def get_total_users():
    config = load_config()
    api = PterodactylClient(config['panel']['url'], config['panel']['api'])
    users = api.user.list_users()
    total_users = len(users['data'])
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
            # Fetch all servers and group them by node ID
            servers = self.api.servers.list_servers().collect()
            servers_per_node = defaultdict(int)

            for server in servers:
                node_id = server['attributes'].get('node')
                if node_id is not None:
                    servers_per_node[node_id] += 1

            # Fetch node stats
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
                total_servers = servers_per_node.get(node_id, 0)  # Get server count from grouped data

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