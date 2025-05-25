import discord
from discord import app_commands
from discord.ext import commands
import requests
import os
import json
from dotenv import load_dotenv
import asyncio
import typing

load_dotenv()
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

if not DISCORD_BOT_TOKEN:
    print("CRITICAL ERROR: Discord bot token (DISCORD_BOT_TOKEN) not found in .env file!")
    exit()

GUILD_CONFIGS_FILE = "ptero_guild_configs.json"
ALL_GUILD_CONFIGS = {}
config_lock = asyncio.Lock()

async def load_all_guild_configs():
    global ALL_GUILD_CONFIGS
    async with config_lock:
        try:
            with open(GUILD_CONFIGS_FILE, 'r') as f:
                ALL_GUILD_CONFIGS = json.load(f)
                for guild_id_str in ALL_GUILD_CONFIGS:
                    if 'server_aliases' not in ALL_GUILD_CONFIGS[guild_id_str]:
                        ALL_GUILD_CONFIGS[guild_id_str]['server_aliases'] = {}
                    if 'default_pterodactyl_server_uuid' not in ALL_GUILD_CONFIGS[guild_id_str]:
                        ALL_GUILD_CONFIGS[guild_id_str]['default_pterodactyl_server_uuid'] = None
                print(f"Loaded Pterodactyl configurations for {len(ALL_GUILD_CONFIGS)} guilds from {GUILD_CONFIGS_FILE}")
        except FileNotFoundError:
            ALL_GUILD_CONFIGS = {}
            print(f"Config file {GUILD_CONFIGS_FILE} not found. It will be created on first configuration.")
        except json.JSONDecodeError:
            ALL_GUILD_CONFIGS = {}
            print(f"WARNING: File {GUILD_CONFIGS_FILE} is corrupted or empty. It will be overwritten on first configuration.")

async def save_all_guild_configs():
    async with config_lock:
        try:
            with open(GUILD_CONFIGS_FILE, 'w') as f:
                json.dump(ALL_GUILD_CONFIGS, f, indent=4)
        except IOError:
            print(f"CRITICAL ERROR: Failed to save configuration to {GUILD_CONFIGS_FILE}")

def get_guild_config(guild_id: int):
    guild_id_str = str(guild_id)
    config = ALL_GUILD_CONFIGS.get(guild_id_str)
    if config:
        if 'server_aliases' not in config:
            config['server_aliases'] = {}
        if 'default_pterodactyl_server_uuid' not in config:
            config['default_pterodactyl_server_uuid'] = None
    return config

def get_api_headers(api_key: str):
    if not api_key: return {}
    return {'Authorization': f'Bearer {api_key}', 'Accept': 'application/json', 'Content-Type': 'application/json'}

async def resolve_server_identifier(guild_config: dict, identifier: str) -> typing.Optional[str]:
    if not identifier: return None
    if guild_config and 'server_aliases' in guild_config:
        return guild_config['server_aliases'].get(identifier.lower(), identifier)
    return identifier

intents = discord.Intents.default()
intents.guilds = True
bot = commands.Bot(command_prefix="§", intents=intents)

@bot.event
async def on_ready():
    await load_all_guild_configs()
    print(f'Bot logged in as {bot.user.name} (ID: {bot.user.id})')
    print(f'Bot is on {len(bot.guilds)} guilds.')
    try:
        synced = await bot.tree.sync()
        print(f"Synchronized {len(synced)} slash commands.")
    except Exception as e:
        print(f"Error synchronizing slash commands: {e}")
    print('------')
    print("Bot is ready. Administrators on each guild must configure Pterodactyl integration.")

ptero_group = app_commands.Group(name="ptero", description="Commands for managing Pterodactyl servers")

def ensure_guild_config_structure(guild_id_str: str):
    if guild_id_str not in ALL_GUILD_CONFIGS:
        ALL_GUILD_CONFIGS[guild_id_str] = {}
    if 'server_aliases' not in ALL_GUILD_CONFIGS[guild_id_str]:
        ALL_GUILD_CONFIGS[guild_id_str]['server_aliases'] = {}
    if 'default_pterodactyl_server_uuid' not in ALL_GUILD_CONFIGS[guild_id_str]:
        ALL_GUILD_CONFIGS[guild_id_str]['default_pterodactyl_server_uuid'] = None


@ptero_group.command(name="set_api", description="Sets the Pterodactyl API key for this guild.")
@app_commands.describe(api_key="Your API key from the Pterodactyl panel")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_set_api(interaction: discord.Interaction, api_key: str):
    guild_id_str = str(interaction.guild.id)
    ensure_guild_config_structure(guild_id_str)
    ALL_GUILD_CONFIGS[guild_id_str]['api_key'] = api_key
    await save_all_guild_configs()
    await interaction.response.send_message(f"✅ Pterodactyl API key for guild **{interaction.guild.name}** has been set.", ephemeral=True)

@ptero_group.command(name="set_url", description="Sets the Pterodactyl panel URL for this guild.")
@app_commands.describe(panel_url="Full URL of your Pterodactyl panel (e.g., https://panel.example.com)")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_set_url(interaction: discord.Interaction, panel_url: str):
    guild_id_str = str(interaction.guild.id)
    if not (panel_url.startswith('http://') or panel_url.startswith('https://')):
        await interaction.response.send_message("❌ Invalid URL format. URL should start with `http://` or `https://`.", ephemeral=True)
        return
    ensure_guild_config_structure(guild_id_str)
    ALL_GUILD_CONFIGS[guild_id_str]['panel_url'] = panel_url.rstrip('/')
    await save_all_guild_configs()
    await interaction.response.send_message(f"✅ Pterodactyl panel URL for guild **{interaction.guild.name}** has been set to: `{ALL_GUILD_CONFIGS[guild_id_str]['panel_url']}`", ephemeral=True)

@ptero_group.command(name="set_default", description="Sets the default Pterodactyl server for this Discord guild.")
@app_commands.describe(server_identifier="ID (UUID) or alias of the Pterodactyl server to be set as default.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_set_default(interaction: discord.Interaction, server_identifier: str):
    guild_id_str = str(interaction.guild.id)
    ensure_guild_config_structure(guild_id_str)
    guild_config = ALL_GUILD_CONFIGS[guild_id_str]

    resolved_uuid = await resolve_server_identifier(guild_config, server_identifier)

    guild_config['default_pterodactyl_server_uuid'] = resolved_uuid
    await save_all_guild_configs()

    ptero_server_display_name = await get_pterodactyl_server_name(guild_config, resolved_uuid)

    await interaction.response.send_message(f"✅ Pterodactyl server **{ptero_server_display_name}** (ID: `{resolved_uuid}`) has been set as default for **{interaction.guild.name}**.", ephemeral=True)


@ptero_group.command(name="config", description="Displays the current Pterodactyl configuration for this guild.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_config(interaction: discord.Interaction):
    guild_config = get_guild_config(interaction.guild.id)
    embed = discord.Embed(title=f"⚙️ Pterodactyl Configuration for: {interaction.guild.name}", color=discord.Color.orange())
    panel_url_value = "Not set. Use `/ptero set_url <URL>`."
    api_key_value = "Not set. Use `/ptero set_api <KEY>`."
    default_server_value = "Not set. Use `/ptero set_default <ID_or_alias>`."

    if guild_config:
        if guild_config.get('panel_url'):
            panel_url_value = f"`{guild_config['panel_url']}`"
        if guild_config.get('api_key'):
            api_key = guild_config['api_key']
            masked_key = api_key[:4] + "..." + api_key[-4:] if len(api_key) > 8 else api_key
            api_key_value = f"`{masked_key}`"
        if guild_config.get('default_pterodactyl_server_uuid'):
            default_uuid = guild_config['default_pterodactyl_server_uuid']
            default_server_display_name = await get_pterodactyl_server_name(guild_config, default_uuid)
            default_server_value = f"**{default_server_display_name}** (ID: `{default_uuid}`)"

    embed.add_field(name="Panel URL", value=panel_url_value, inline=False)
    embed.add_field(name="API Key", value=api_key_value, inline=False)
    embed.add_field(name="Default Pterodactyl Server", value=default_server_value, inline=False)
    await interaction.response.send_message(embed=embed, ephemeral=True)

@ptero_group.command(name="set_alias", description="Sets or updates an alias for a Pterodactyl server ID.")
@app_commands.describe(alias_name="Friendly name for the server (e.g., 'survival')", ptero_server_id="Actual server ID (UUID) from the Pterodactyl panel")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_set_alias(interaction: discord.Interaction, alias_name: str, ptero_server_id: str):
    guild_id_str = str(interaction.guild.id)
    ensure_guild_config_structure(guild_id_str)
    alias_name_lower = alias_name.lower()

    ALL_GUILD_CONFIGS[guild_id_str]['server_aliases'][alias_name_lower] = ptero_server_id
    await save_all_guild_configs()
    await interaction.response.send_message(f"✅ Alias `'{alias_name_lower}'` has been set for Pterodactyl server ID: `{ptero_server_id}`.", ephemeral=True)

@ptero_group.command(name="delete_alias", description="Deletes a defined Pterodactyl server alias.")
@app_commands.describe(alias_name="Name of the alias to delete")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_delete_alias(interaction: discord.Interaction, alias_name: str):
    guild_id_str = str(interaction.guild.id)
    alias_name_lower = alias_name.lower()
    guild_config = get_guild_config(interaction.guild.id)

    if guild_config and 'server_aliases' in guild_config and alias_name_lower in guild_config['server_aliases']:
        del ALL_GUILD_CONFIGS[guild_id_str]['server_aliases'][alias_name_lower]
        await save_all_guild_configs()
        await interaction.response.send_message(f"✅ Alias `'{alias_name_lower}'` has been deleted.", ephemeral=True)
    else:
        await interaction.response.send_message(f"❌ Alias `'{alias_name_lower}'` not found.", ephemeral=True)

@ptero_group.command(name="aliases", description="Displays a list of defined Pterodactyl server aliases.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_aliases(interaction: discord.Interaction):
    guild_config = get_guild_config(interaction.guild.id)
    aliases = guild_config.get('server_aliases', {}) if guild_config else {}

    if not aliases:
        await interaction.response.send_message("ℹ️ No Pterodactyl server aliases defined for this Discord guild.", ephemeral=True)
        return

    embed = discord.Embed(title=f"📜 Defined Pterodactyl Aliases for: {interaction.guild.name}", color=discord.Color.info())
    description = ""
    for alias, uuid in aliases.items():
        description += f"`{alias}` ➔ `{uuid}`\n"
    if not description: description = "No aliases."
    embed.description = description
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def check_guild_pterodactyl_config_and_respond(interaction: discord.Interaction):
    guild_config = get_guild_config(interaction.guild.id)
    if not guild_config or not guild_config.get('api_key') or not guild_config.get('panel_url'):
        message = (f"❌ Pterodactyl configuration for guild **{interaction.guild.name}** is incomplete. "
                   "An administrator must use `/ptero set_api` and `/ptero set_url` commands.")
        if not interaction.response.is_done(): await interaction.response.send_message(message, ephemeral=True)
        else: await interaction.followup.send(message, ephemeral=True)
        return None
    return guild_config

@ptero_group.command(name="help", description="Displays a list of available Pterodactyl bot commands.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_help(interaction: discord.Interaction):
    embed = discord.Embed(
        title=f"Help - Pterodactyl Bot for: {interaction.guild.name}",
        description="List of available commands (administrator permissions required):",
        color=discord.Color.blue()
    )
    embed.add_field(name="Bot Configuration", value="`/ptero set_api <API_KEY>`\n`/ptero set_url <PANEL_URL>`\n`/ptero set_default <ID_or_alias>`\n`/ptero config`", inline=False)
    embed.add_field(name="Server Alias Management", value="`/ptero set_alias <alias_name> <PTERO_SERVER_ID>`\n`/ptero delete_alias <alias_name>`\n`/ptero aliases`", inline=False)
    embed.add_field(name="Pterodactyl Server Information", value="`/ptero list_servers`", inline=False)
    embed.add_field(name="Pterodactyl Server Control", value=(
        "`/ptero status [ID_or_alias]`\n"
        "`/ptero start [ID_or_alias]`\n"
        "`/ptero stop [ID_or_alias]`\n"
        "`/ptero restart [ID_or_alias]`\n"
        "`/ptero kill [ID_or_alias]`\n"
        "`/ptero command <ID_or_alias> <command>` (ID/alias required for command)"
    ), inline=False)
    embed.add_field(name="Pterodactyl Server Queue", value=(
        "`/ptero join_queue [ID_or_alias]`\n"
        "`/ptero queue_status [ID_or_alias]`"
    ), inline=False)
    embed.set_footer(text="In control commands, [ID_or_alias] is optional if a default server is set.")
    await interaction.response.send_message(embed=embed, ephemeral=True)

async def get_pterodactyl_server_name(guild_config: dict, resolved_ptero_uuid: str) -> str:
    if not guild_config or not guild_config.get('panel_url') or not guild_config.get('api_key') or not resolved_ptero_uuid: return resolved_ptero_uuid if resolved_ptero_uuid else "Unknown server"
    api_headers = get_api_headers(guild_config['api_key'])
    if not api_headers: return resolved_ptero_uuid
    try:
        response = requests.get(f"{guild_config['panel_url']}/api/client/servers/{resolved_ptero_uuid}", headers=api_headers, timeout=10)
        response.raise_for_status()
        data = response.json()
        return data.get('attributes', {}).get('name', resolved_ptero_uuid)
    except: return resolved_ptero_uuid

async def get_server_id_to_use(interaction: discord.Interaction, guild_config: dict, server_identifier: typing.Optional[str]) -> typing.Optional[str]:
    if server_identifier:
        return await resolve_server_identifier(guild_config, server_identifier)
    elif guild_config.get('default_pterodactyl_server_uuid'):
        return guild_config['default_pterodactyl_server_uuid']
    else:
        message = ("❌ No server identifier provided, and no default Pterodactyl server is set for this guild. "
                   "Use `/ptero set_default <ID_or_alias>` or provide an identifier in the command.")
        if not interaction.response.is_done(): await interaction.response.send_message(message, ephemeral=True)
        else: await interaction.followup.send(message, ephemeral=True)
        return None

@ptero_group.command(name="status", description="Checks the status and resources of a Pterodactyl server.")
@app_commands.describe(server_identifier="ID or alias of the Pterodactyl server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_status(interaction: discord.Interaction, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return

    actual_ptero_server_id = await get_server_id_to_use(interaction, guild_config, server_identifier)
    if not actual_ptero_server_id: return

    ptero_server_display_name = await get_pterodactyl_server_name(guild_config, actual_ptero_server_id)

    initial_message = f"⏳ Checking Pterodactyl server status: **{ptero_server_display_name}**"
    if server_identifier and server_identifier.lower() != actual_ptero_server_id.lower() and server_identifier.lower() != ptero_server_display_name.lower():
        initial_message += f" (alias: `{server_identifier}`, ID: `{actual_ptero_server_id}`)..."
    else:
        initial_message += f" (ID: `{actual_ptero_server_id}`)..."
    await interaction.followup.send(initial_message)

    api_headers = get_api_headers(guild_config['api_key'])
    try:
        api_url = f"{guild_config['panel_url']}/api/client/servers/{actual_ptero_server_id}/resources"
        response = requests.get(api_url, headers=api_headers, timeout=10)
        response.raise_for_status()
        data = response.json(); attributes = data.get('attributes', {}); status_text = attributes.get('current_state', 'unknown')
        resources = attributes.get('resources', {}); ram_current_bytes = resources.get('memory_bytes', 0); ram_current_mb = ram_current_bytes / (1024**2)
        cpu_absolute = resources.get('cpu_absolute', 0); disk_bytes = resources.get('disk_bytes', 0); disk_mb = disk_bytes / (1024**2)
        limits = attributes.get('limits', {}); ram_limit_mb = limits.get('memory', 0) if limits.get('memory', 0) > 0 else "Unlimited"
        disk_limit_mb = limits.get('disk', 0) if limits.get('disk', 0) > 0 else "Unlimited"; cpu_limit = limits.get('cpu', 0) if limits.get('cpu', 0) > 0 else "Unlimited"
        color = discord.Color.green() if status_text == 'running' else (discord.Color.orange() if status_text in ('stopping', 'starting') else (discord.Color.red() if status_text == 'offline' else discord.Color.greyple()))
        embed = discord.Embed(title=f"📊 Status: {ptero_server_display_name}", description=f"Pterodactyl ID: `{actual_ptero_server_id}`", color=color)
        embed.add_field(name="Status", value=status_text.capitalize(), inline=True); embed.add_field(name="CPU", value=f"{cpu_absolute:.2f}% / {cpu_limit}%", inline=True)
        embed.add_field(name="RAM", value=f"{ram_current_mb:.2f} MB / {ram_limit_mb} MB", inline=True); embed.add_field(name="Disk", value=f"{disk_mb:.2f} MB / {disk_limit_mb} MB", inline=True)
        network_data = resources.get('network', {}); rx_bytes = network_data.get('rx_bytes', 0); tx_bytes = network_data.get('tx_bytes', 0)
        embed.add_field(name="Network (Received)", value=f"{rx_bytes / (1024**2):.2f} MB", inline=True); embed.add_field(name="Network (Sent)", value=f"{tx_bytes / (1024**2):.2f} MB", inline=True)
        embed.set_footer(text=f"Discord Guild: {interaction.guild.name} | By: {interaction.user.display_name}"); embed.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=embed)
    except requests.exceptions.HTTPError as errh:
        msg = f"HTTP Error: {errh.response.status_code}"
        resolved_id_for_error = actual_ptero_server_id or server_identifier
        if errh.response.status_code == 404: msg = f"❌ Pterodactyl server with ID `{resolved_id_for_error}` not found on `{guild_config['panel_url']}`."
        elif errh.response.status_code == 403: msg = f"❌ Insufficient permissions (API key) to read Pterodactyl server status `{resolved_id_for_error}`."
        else: msg += f" - {errh.response.text[:500]}"
        await interaction.followup.send(msg)
    except Exception as e: print(f"Error in ptero_status: {e}"); await interaction.followup.send(f"❌ An unexpected error occurred: {e}")

async def send_pterodactyl_power_command(interaction: discord.Interaction, guild_config: dict, server_identifier: typing.Optional[str], command: str, friendly_name: str):
    actual_ptero_server_id = await get_server_id_to_use(interaction, guild_config, server_identifier)
    if not actual_ptero_server_id: return

    ptero_server_display_name = await get_pterodactyl_server_name(guild_config, actual_ptero_server_id)

    initial_message = f"⏳ Sending '{friendly_name}' to Pterodactyl: **{ptero_server_display_name}**"
    if server_identifier and server_identifier.lower() != actual_ptero_server_id.lower() and server_identifier.lower() != ptero_server_display_name.lower():
        initial_message += f" (alias: `{server_identifier}`, ID: `{actual_ptero_server_id}`)..."
    else:
        initial_message += f" (ID: `{actual_ptero_server_id}`)..."
    await interaction.followup.send(initial_message)


    api_url = f"{guild_config['panel_url']}/api/client/servers/{actual_ptero_server_id}/power"
    payload = {'signal': command}
    api_headers = get_api_headers(guild_config['api_key'])
    try:
        response = requests.post(api_url, headers=api_headers, json=payload, timeout=15)
        response.raise_for_status()
        await interaction.followup.send(f"✅ Command '{friendly_name}' sent to **{ptero_server_display_name}**.")
    except requests.exceptions.HTTPError as errh:
        msg = f"HTTP Error: {errh.response.status_code}"
        resolved_id_for_error = actual_ptero_server_id or server_identifier
        if errh.response.status_code == 404: msg = f"❌ Pterodactyl server with ID `{resolved_id_for_error}` not found."
        elif errh.response.status_code == 403: msg = f"❌ Insufficient permissions (API key) for action '{friendly_name}' on server `{resolved_id_for_error}`."
        elif errh.response.status_code == 409:
             try: status_message = errh.response.json().get('errors', [{}])[0].get('detail', 'Request conflict.')
             except: status_message = "Request conflict (e.g., server already in that state)."
             msg = f"⚠️ Cannot '{friendly_name}' on `{resolved_id_for_error}`. {status_message}"
        else: msg += f" - {errh.response.text[:500]}"
        await interaction.followup.send(msg)
    except Exception as e: print(f"Error in send_power_command ({command}): {e}"); await interaction.followup.send(f"❌ Unexpected error '{friendly_name}': {e}")

@ptero_group.command(name="start", description="Starts a Pterodactyl server.")
@app_commands.describe(server_identifier="ID or alias of the server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_start(interaction: discord.Interaction, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return
    await send_pterodactyl_power_command(interaction, guild_config, server_identifier, "start", "Start")

@ptero_group.command(name="stop", description="Stops a Pterodactyl server.")
@app_commands.describe(server_identifier="ID or alias of the server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_stop(interaction: discord.Interaction, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return
    await send_pterodactyl_power_command(interaction, guild_config, server_identifier, "stop", "Stop")

@ptero_group.command(name="restart", description="Restarts a Pterodactyl server.")
@app_commands.describe(server_identifier="ID or alias of the server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_restart(interaction: discord.Interaction, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return
    await send_pterodactyl_power_command(interaction, guild_config, server_identifier, "restart", "Restart")

@ptero_group.command(name="kill", description="Forces a Pterodactyl server to stop (kill).")
@app_commands.describe(server_identifier="ID or alias of the server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_kill(interaction: discord.Interaction, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return
    await send_pterodactyl_power_command(interaction, guild_config, server_identifier, "kill", "Forced stop")

@ptero_group.command(name="command", description="Sends a command to the Pterodactyl server console.")
@app_commands.describe(command="Command to send", server_identifier="ID or alias of the server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_command(interaction: discord.Interaction, command: str, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return

    actual_ptero_server_id = await get_server_id_to_use(interaction, guild_config, server_identifier)
    if not actual_ptero_server_id: return

    ptero_server_display_name = await get_pterodactyl_server_name(guild_config, actual_ptero_server_id)

    initial_message = f"⏳ Sending command to **{ptero_server_display_name}**"
    if server_identifier and server_identifier.lower() != actual_ptero_server_id.lower() and server_identifier.lower() != ptero_server_display_name.lower():
        initial_message += f" (alias: `{server_identifier}`, ID: `{actual_ptero_server_id}`): `{command}`..."
    else:
        initial_message += f" (ID: `{actual_ptero_server_id}`): `{command}`..."
    await interaction.followup.send(initial_message)

    api_url = f"{guild_config['panel_url']}/api/client/servers/{actual_ptero_server_id}/command"
    payload_cmd = {'command': command}
    api_headers = get_api_headers(guild_config['api_key'])
    try:
        response = requests.post(api_url, headers=api_headers, json=payload_cmd, timeout=10)
        response.raise_for_status()
        await interaction.followup.send(f"✅ Command `{command}` sent to **{ptero_server_display_name}**.")
    except requests.exceptions.HTTPError as errh:
        msg = f"HTTP Error: {errh.response.status_code}"
        resolved_id_for_error = actual_ptero_server_id or server_identifier
        if errh.response.status_code == 404: msg = f"❌ Pterodactyl server with ID `{resolved_id_for_error}` not found."
        elif errh.response.status_code == 403: msg = f"❌ Insufficient permissions (API key) to send commands to server `{resolved_id_for_error}`."
        elif errh.response.status_code == 502: msg = f"❌ Server `{resolved_id_for_error}` is likely not running (error 502)."
        else: msg += f" - {errh.response.text[:500]}"
        await interaction.followup.send(msg)
    except Exception as e: print(f"Error in ptero_command: {e}"); await interaction.followup.send(f"❌ Unexpected error: {e}")

@ptero_group.command(name="join_queue", description="Joins the queue for a Pterodactyl server.")
@app_commands.describe(server_identifier="ID or alias of the server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_join_queue(interaction: discord.Interaction, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return

    actual_ptero_server_id = await get_server_id_to_use(interaction, guild_config, server_identifier)
    if not actual_ptero_server_id: return

    ptero_server_display_name = await get_pterodactyl_server_name(guild_config, actual_ptero_server_id)

    initial_message = f"⏳ Attempting to join queue for: **{ptero_server_display_name}**"
    if server_identifier and server_identifier.lower() != actual_ptero_server_id.lower() and server_identifier.lower() != ptero_server_display_name.lower():
        initial_message += f" (alias: `{server_identifier}`, ID: `{actual_ptero_server_id}`)..."
    else:
        initial_message += f" (ID: `{actual_ptero_server_id}`)..."
    await interaction.followup.send(initial_message)

    api_url = f"{guild_config['panel_url']}/api/client/servers/{actual_ptero_server_id}/join-queue"
    api_headers = get_api_headers(guild_config['api_key'])
    try:
        response = requests.post(api_url, headers=api_headers, timeout=15)
        response.raise_for_status()
        try:
            response_data = response.json(); message = response_data.get('attributes', {}).get('message', "Join request sent.")
            position = response_data.get('attributes', {}).get('position')
            if position is not None: message += f" Position: {position}."
            await interaction.followup.send(f"✅ {message} (Server: **{ptero_server_display_name}**)")
        except json.JSONDecodeError: await interaction.followup.send(f"✅ Join queue request sent for **{ptero_server_display_name}**.")
    except requests.exceptions.HTTPError as errh:
        error_message = f"HTTP Error: {errh.response.status_code}"
        try: error_details = errh.response.json().get('errors', [{}])[0].get('detail', 'API error.')
        except: error_details = errh.response.text[:100]
        error_message += f" - {error_details}"
        resolved_id_for_error = actual_ptero_server_id or server_identifier
        if errh.response.status_code == 409: error_message = f"⚠️ Cannot join queue for `{resolved_id_for_error}`. {error_details}"
        await interaction.followup.send(f"❌ {error_message}")
    except Exception as e: print(f"Error in ptero_join_queue: {e}"); await interaction.followup.send(f"❌ Unexpected error: {e}")

@ptero_group.command(name="queue_status", description="Checks the status of the queue for a Pterodactyl server.")
@app_commands.describe(server_identifier="ID or alias of the server (optional, if default is set).")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_queue_status(interaction: discord.Interaction, server_identifier: typing.Optional[str] = None):
    await interaction.response.defer(ephemeral=False)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return

    actual_ptero_server_id = await get_server_id_to_use(interaction, guild_config, server_identifier)
    if not actual_ptero_server_id: return

    ptero_server_display_name = await get_pterodactyl_server_name(guild_config, actual_ptero_server_id)

    initial_message = f"⏳ Checking queue status for: **{ptero_server_display_name}**"
    if server_identifier and server_identifier.lower() != actual_ptero_server_id.lower() and server_identifier.lower() != ptero_server_display_name.lower():
        initial_message += f" (alias: `{server_identifier}`, ID: `{actual_ptero_server_id}`)..."
    else:
        initial_message += f" (ID: `{actual_ptero_server_id}`)..."
    await interaction.followup.send(initial_message)

    api_url = f"{guild_config['panel_url']}/api/client/servers/{actual_ptero_server_id}"
    api_headers = get_api_headers(guild_config['api_key'])
    try:
        response = requests.get(api_url, headers=api_headers, timeout=10)
        response.raise_for_status()
        data = response.json(); attributes = data.get('attributes', {})
        is_queued = attributes.get('is_queued', False); position = attributes.get('position')
        estimated_time_seconds = attributes.get('estimated_time_seconds'); queue_length = attributes.get('queue_length', 0)
        embed = discord.Embed(title=f"რი Queue Status: {ptero_server_display_name}", description=f"Pterodactyl ID: `{actual_ptero_server_id}`", color=discord.Color.blue() if is_queued else discord.Color.light_grey())
        embed.add_field(name="In Queue?", value="Yes ✅" if is_queued else "No ❌", inline=True); embed.add_field(name="Queue Length", value=str(queue_length), inline=True)
        if is_queued and position is not None: embed.add_field(name="Your Position", value=str(position), inline=True)
        if estimated_time_seconds is not None:
            minutes, seconds = divmod(estimated_time_seconds, 60)
            estimated_time_str = f"{minutes} min {seconds} sec" if minutes > 0 else f"{seconds} sec"
            embed.add_field(name="Estimated Time", value=estimated_time_str, inline=True)
        embed.set_footer(text=f"Discord Guild: {interaction.guild.name} | By: {interaction.user.display_name}"); embed.timestamp = discord.utils.utcnow()
        await interaction.followup.send(embed=embed)
    except requests.exceptions.HTTPError as errh:
        error_message = f"HTTP Error: {errh.response.status_code}"
        try: error_details = errh.response.json().get('errors', [{}])[0].get('detail', 'API error.')
        except: error_details = errh.response.text[:100]
        error_message += f" - {error_details}"
        await interaction.followup.send(f"❌ {error_message}")
    except Exception as e: print(f"Error in ptero_queue_status: {e}"); await interaction.followup.send(f"❌ Unexpected error: {e}")

@ptero_group.command(name="list_servers", description="Displays a list of Pterodactyl servers available for the API key.")
@app_commands.checks.has_permissions(administrator=True)
@app_commands.guild_only()
async def ptero_list_servers(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    guild_config = await check_guild_pterodactyl_config_and_respond(interaction)
    if not guild_config: return

    api_headers = get_api_headers(guild_config['api_key'])
    try:
        api_url = f"{guild_config['panel_url']}/api/client"
        response = requests.get(api_url, headers=api_headers, timeout=15)
        response.raise_for_status()

        data = response.json()
        servers_data = data.get('data', [])

        if not servers_data:
            await interaction.followup.send("ℹ️ No Pterodactyl servers found for the configured API key.", ephemeral=True)
            return

        embed = discord.Embed(
            title=f"🖥️ Available Pterodactyl Servers ({len(servers_data)})",
            description=f"Panel: `{guild_config['panel_url']}`",
            color=discord.Color.dark_teal()
        )

        output_text = []
        for server_obj in servers_data:
            attrs = server_obj.get('attributes', {})
            server_name = attrs.get('name', 'No Name')
            server_uuid = attrs.get('uuid', 'No UUID')
            server_identifier = attrs.get('identifier', server_uuid)

            output_text.append(f"**Name:** `{server_name}`\n  **ID (identifier):** `{server_identifier}`\n  **UUID:** `{server_uuid}`\n")

        full_description = "\n".join(output_text)

        if len(full_description) > 4000:
            full_description = full_description[:3900] + "\n\n... (list too long, partial list shown)"

        embed.description = full_description
        await interaction.followup.send(embed=embed, ephemeral=True)

    except requests.exceptions.HTTPError as errh:
        msg = f"HTTP Error while fetching server list: {errh.response.status_code}"
        if errh.response.status_code == 403: msg += " - Insufficient permissions (API key) to list servers."
        else:
            try: msg += f" - {errh.response.json().get('errors', [{}])[0].get('detail', errh.response.text[:100])}"
            except: msg += f" - {errh.response.text[:100]}"
        await interaction.followup.send(f"❌ {msg}", ephemeral=True)
    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"❌ A connection error occurred while fetching the server list: {e}", ephemeral=True)
    except Exception as e:
        print(f"Unexpected error in ptero_list_servers: {e}")
        await interaction.followup.send(f"❌ An unexpected error occurred while fetching the server list.", ephemeral=True)

bot.tree.add_command(ptero_group)

@bot.tree.error
async def on_app_command_error(interaction: discord.Interaction, error: app_commands.AppCommandError):
    original_error = error.original if isinstance(error, app_commands.CommandInvokeError) else error

    if isinstance(original_error, app_commands.MissingPermissions) or isinstance(error, app_commands.MissingPermissions):
        message = f"🚫 {interaction.user.mention}, you do not have administrator permissions on this Discord guild to use this command!"
    elif isinstance(original_error, app_commands.NoPrivateMessage) or isinstance(error, app_commands.NoPrivateMessage):
         message = "🚫 This command can only be used in a guild."
    else:
        print(f"Unhandled slash command error '{interaction.data.get('name', 'unknown') if interaction.data else 'unknown'}': {original_error}")
        message = "❌ An internal bot error occurred. Please contact its administrator."

    if not interaction.response.is_done():
        await interaction.response.send_message(message, ephemeral=True)
    else:
        try:
            await interaction.followup.send(message, ephemeral=True)
        except discord.errors.InteractionResponded: pass
        except Exception as e_followup: print(f"Error sending followup after main error: {e_followup}")

if __name__ == "__main__":
    if DISCORD_TOKEN:
        async def main():
            await load_all_guild_configs()
            await bot.start(DISCORD_TOKEN)

        try:
            asyncio.run(main())
        except discord.errors.LoginFailure:
            print("CRITICAL ERROR: Failed to log in the bot. Check your token (DISCORD_TOKEN).")
        except KeyboardInterrupt:
            print("Bot stopped by user.")
        except Exception as e:
            print(f"An unexpected error occurred during bot startup: {e}")
    else:
        print("CRITICAL ERROR: Discord bot token (DISCORD_TOKEN) not found.")
