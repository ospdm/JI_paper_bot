# commands/jltinfo.py

import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL

# Ссылки
INFO_URL = "https://docs.google.com/document/d/1e4GRKmenwmAl_Uhnp7VC4laIBiXDJ7H1Pnhs7zb6XH4/edit?usp=sharing"
COURSE_URL = "https://docs.google.com/document/d/1QDAfihFlh40bYz6cb2bkGlYaQZCdY1dNXgry6T67j3M/edit?usp=sharing"

class JLTInfoCog(commands.Cog):
    """Команда /jltinfo — выдаёт стажёрам нужные документы."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="jltinfo",
        description="Полезные материалы и инструкции для стажёров"
    )
    async def jltinfo(self, interaction: discord.Interaction):
        """
        /jltinfo — отправляет два embed-сообщения:
          • Информация стажерам
          • Курс Молодого Следователя
        """

        # Первый embed
        em1 = discord.Embed(
            description=f"📄 [Информация стажерам]({INFO_URL})",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em1.set_thumbnail(url=config.EMBLEM_URL)

        # Второй embed
        em2 = discord.Embed(
            description=f"📄 [Курс Молодого Следователя]({COURSE_URL})",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em2.set_thumbnail(url=config.EMBLEM_URL)

        # Отправляем оба сразу
        await interaction.response.send_message(embeds=[em1, em2])

async def setup(bot: commands.Bot):
    await bot.add_cog(JLTInfoCog(bot))
