import discord
from discord.ext import commands
import json
import os
from dotenv import load_dotenv
import aiofiles # Use async file handling
import asyncio

# Load environment variables
load_dotenv()

# Bot Setup

up_time = 0

class MeaningsBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        super().__init__(command_prefix="?", intents=intents)
    async def setup_hook(self):
        asyncio.get_event_loop(). set_debug(True) #Set up debugging for blocking code
        global up_time
        up_time = discord.utils.utcnow().timestamp()

bot = MeaningsBot()

# Whitelisted user IDs who can add meanings
WHITELISTED_USERS = [
    802167689011134474  # Add more user IDs here
]


# Load meanings from JSON file
async def load_meanings():
    try:
        async with aiofiles.open("meanings.json", "r", encoding="utf-8") as f:
            content = await f.read()
            return json.loads(content)
    except FileNotFoundError:
        return {}


# Save meanings to JSON file
async def save_meanings(meanings):
    async with aiofiles.open("meanings.json", "w", encoding="utf-8") as f:
        data =json.dumps(meanings, indent=2, ensure_ascii=False)
        await f.write(data)


class AddMeaningModal(discord.ui.Modal, title="Add New Meaning"):
    def __init__(self):
        super().__init__()

    word = discord.ui.TextInput(
        label="Word/Phrase",
        placeholder='Enter the word or phrase (e.g., "sybau")',
        required=True,
        max_length=100,
    )

    meaning = discord.ui.TextInput(
        label="Meaning/Definition",
        placeholder='Enter the meaning (e.g., "Shut Your Bitch Ass Up")',
        style=discord.TextStyle.paragraph,
        required=True,
        max_length=1000,
    )

    example = discord.ui.TextInput(
        label="Example (Optional)",
        placeholder="Enter an example usage (optional)",
        style=discord.TextStyle.paragraph,
        required=False,
        max_length=500,
    )

    category = discord.ui.TextInput(
        label="Category (Optional)",
        placeholder='Enter a category (e.g., "Slang", "Internet")',
        required=False,
        max_length=50,
    )

    async def on_submit(self, interaction: discord.Interaction):
        meanings = await load_meanings()

        # Create meaning entry
        meaning_entry = {
            "meaning": self.meaning.value,
            "added_by": str(interaction.user),
            "added_at": str(interaction.created_at),
        }

        if self.example.value:
            meaning_entry["example"] = self.example.value

        if self.category.value:
            meaning_entry["category"] = self.category.value

        meanings[self.word.value.lower()] = meaning_entry
        await save_meanings(meanings)

        embed = discord.Embed(
            title=f"✅ Successfully added `{self.word.value.upper()}`!",
            color=0x00FF00,
            timestamp=discord.utils.utcnow()
        )
        embed.add_field(
            name="Meaning",
            value=(
                f"{f"- {self.meaning.value[:100]}" + "..."\
                if len(self.meaning.value) > 100\
                else f"- {self.meaning.value}"}"
            ),
            inline=False,
        )
        embed.set_footer(text=f"Added by @{interaction.user}", icon_url=interaction.user.display_avatar.url)
        await interaction.response.send_message(embed=embed, ephemeral=True)


@bot.event
async def on_ready():
    print(f"{bot.user} is online!")

    # Fancy status with server count and DND status
    server_count = len(bot.guilds)
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"meanings on {server_count} servers ✨",
    )
    await bot.change_presence(activity=activity, status=discord.Status.dnd)


@bot.command(name="meaning")
async def meaning_command(ctx:commands.Context, *, word : str =None):
    """Shows the meaning of a word/phrase"""

    if not word:
        embed = discord.Embed(
            title="❌ Error",
            description="Please provide a word!\nExample: `?meaning sybau`",
            color=0xFF0000,
        )
        await ctx.send(embed=embed)
        return

    meanings = await load_meanings()
    word_lower = word.lower()

    if word_lower in meanings:
        meaning_data = meanings[word_lower]

        embed = discord.Embed(
            title=f"Word: `{word_lower}`",
            color=0x00FF88,
        )
        # Additional fields if available
        embed.add_field(name="📖 Meaning",
                        value=f"- {meaning_data["meaning"]}")
        if "example" in meaning_data:
            embed.add_field(
                name="💡 Example", value=f"- {meaning_data["example"]}", inline=False
            )

        if "category" in meaning_data:
            embed.add_field(
                name="🏷️ Category", value=f"- {meaning_data["category"]}", inline=True
            )
        embed.set_footer(text="Meanings Bot | Know your slang!")
        embed.set_footer(text=f"Requested by @{ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)
    else:
        embed = discord.Embed(
            title="❓ I don't know this word yet",
            description=f"**{word.upper()}** is not in my database.\n\nYou can suggest it to the bot owner so they can add it!",
            color=0xFFAA00,
        )
        embed.set_footer(text="New words are added regularly!")
        await ctx.send(embed=embed)


@bot.command(name="addmeaning")
async def add_meaning_modal(ctx:commands.Context):
    """Opens a modal to add a new meaning (whitelisted users only)"""

    # Check if user is whitelisted
    if ctx.author.id not in WHITELISTED_USERS:
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="Only whitelisted users can add new meanings!",
            color=0xFF0000,
        )
        await ctx.send(embed=embed)
        return

    # Send modal
    modal = AddMeaningModal()
    await ctx.send(
        "Click the button below to add a new meaning!", view=ModalView(modal)
    )


class ModalView(discord.ui.View):
    def __init__(self, modal):
        super().__init__(timeout=300)
        self.modal = modal

    @discord.ui.button(
        label="Add Meaning", style=discord.ButtonStyle.primary, emoji="➕"
    )
    async def add_meaning_button(
        self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(self.modal)


@bot.command(name="list")
async def list_meanings(ctx:commands.Context):
    """Shows all available words"""
    meanings : dict = await load_meanings()

    if not meanings:
        embed = discord.Embed(
            title="📝 Word List",
            description="No words in the database yet!",
            color=0xFFAA00,
        )
        await ctx.send(embed=embed)
        return

    # Split into multiple embeds if too many words
    word_list = list(meanings.keys())
    words_per_embed = 20

    for i in range(0, len(word_list), words_per_embed):
        chunk = word_list[i : i + words_per_embed]
        word_text = "\n".join([f"1. {word.upper()}" for word in chunk])

        embed = discord.Embed(
            title=f"📝 Available Words ({i+1}-{min(i+words_per_embed, len(word_list))} of {len(word_list)})",
            description=word_text,
            color=0x0099FF,
        )
        embed.set_footer(text="Use ?meaning [word] for details")
        await ctx.send(embed=embed)


@bot.command(name="deletemeaning")
async def delete_meaning_command(ctx:commands.Context, *, word: str=None):
    """Deletes a meaning from the database (whitelisted users only)"""

    # Check if user is whitelisted
    if ctx.author.id not in WHITELISTED_USERS:
        embed = discord.Embed(
            title="🚫 Access Denied",
            description="Only whitelisted users can delete meanings!",
            color=0xFF0000,
        )
        await ctx.send(embed=embed)
        return

    if not word:
        embed = discord.Embed(
            title="❌ Error",
            description="Please provide a word to delete!\nExample: `?deletemeaning sybau`",
            color=0xFF0000,
        )
        await ctx.send(embed=embed)
        return

    meanings = await load_meanings()
    word_lower = word.lower()

    if word_lower not in meanings:
        embed = discord.Embed(
            title="❓ Word Not Found",
            description=f"**{word.upper()}** is not in the database!",
            color=0xFFAA00,
        )
        await ctx.send(embed=embed)
        return

    # Show confirmation embed
    embed = discord.Embed(
        title="⚠️ Confirm Deletion",
        description=f"Do you really want to delete **{word.upper()}**?",
        color=0xFF9900,
    )
    embed.add_field(
        name="Current Meaning",
        value=(
            meanings[word_lower]["meaning"][:200] + "..."
            if len(meanings[word_lower]["meaning"]) > 200
            else meanings[word_lower]["meaning"]
        ),
        inline=False,
    )
    embed.add_field(
        name="⚡ Action Required",
        value="Type `yes` to confirm deletion or `no` to cancel",
        inline=False,
    )

    await ctx.send(embed=embed)

    def check(msg:discord.Message):
        return msg.channel == ctx.channel and msg.author == ctx.author and  msg.content.lower() in ("yes", "no") 
    try:
        answer = await bot.wait_for("message", check=check, timeout=180)
    except asyncio.TimeoutError:
        return await ctx.send(f"Took too long, deletiong cancelled.")
     
    if answer.content.lower() == "yes":
        del meanings[word]
        await save_meanings(meanings)

        embed = discord.Embed(
            title="✅ Meaning Deleted",
            description=f"`**{word.upper()}**` has been successfully deleted from the database!",
            color=0x00FF00,
            timestamp=discord.utils.utcnow()
        )
        embed.set_footer(text=f"Deleted by @{ctx.author}", icon_url=ctx.author.display_avatar.url)
        await ctx.send(embed=embed)

    else:
        meanings = await load_meanings()
        embed = discord.Embed(
        title="❌ Deletion Cancelled",
        description=f"Deletion of `**{word.upper()}**` has been cancelled!",
        color=0x00FF00,
        timestamp=discord.utils.utcnow())
        await ctx.send(embed=embed)
        embed.set_footer(text=f"Cancelled by @{ctx.author}", icon_url=ctx.author.display_avatar.url)


@bot.command(name="stats")
async def stats_command(ctx:commands.Context):
    """Shows bot statistics"""
    global up_time
    """Get uptime and convert to words"""
    current_uptime = int(discord.utils.utcnow().timestamp() - up_time)
    days = current_uptime // 86400
    hours = (current_uptime % 86400) // 3600
    minutes = (current_uptime % 3600) // 60
    seconds = current_uptime % 60
    up_time_list = []
    if days > 0:
        up_time_list.append(f"{days} day{'s' if days > 1 else ''}")
    if hours > 0:
        up_time_list.append(f"{hours} hour{'s' if hours > 1 else ''}")
    if minutes > 0:
        up_time_list.append(f"{minutes} minute{'s' if minutes > 1 else ''}")
    if seconds > 0:
        up_time_list.append(f"{seconds} second{'s' if seconds != 1 else ''}")
    uptime_to_words = ' and '.join(up_time_list)
    meanings :dict = await load_meanings()

    embed = discord.Embed(title="📊 Bot Statistics", 
                          description=f">>> **Total Words:** {len(meanings.keys())}\n**Servers:** {len(bot.guilds)}\
                            \n**Users:** {len(bot.users)}\n**Uptime:** {uptime_to_words}",
                          color=0x00FF88)
    embed.set_author(name=f"Meannings Bot", icon_url=bot.user.display_avatar.url)
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    await ctx.send(embed=embed)


@bot.event
async def on_guild_join(guild:discord.Guild):
    """Update status when bot joins a new server"""
    server_count = len(bot.guilds)
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"meanings on {server_count} servers ✨",
    )
    await bot.change_presence(activity=activity, status=discord.Status.dnd)


@bot.event
async def on_guild_remove(guild:discord.Guild):
    """Update status when bot leaves a server"""
    server_count = len(bot.guilds)
    activity = discord.Activity(
        type=discord.ActivityType.watching,
        name=f"meanings on {server_count} servers ✨",
    )
    await bot.change_presence(activity=activity, status=discord.Status.dnd)


@bot.command(name="ping")
async def ping_command(ctx:commands.Context):
    """Shows the bot's latency"""
    latency = bot.latency * 1000  # Convert to milliseconds
    embed = discord.Embed(
        title="🏓 Pong!", description=f"Latency: **{latency:.2f} ms**", color=0x00FF88
    )
    await ctx.send(embed=embed)


# Start the bot
if __name__ == "__main__":
    bot.run(os.getenv("DISCORD_TOKEN"))
