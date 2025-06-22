# commands/results.py

import datetime
import logging

import config  # DEVELOPMENT_GUILD_ID и EMBLEM_URL должны быть в config.py
import discord
from discord import app_commands
from discord.ext import commands
from discord.utils import get
from sqlalchemy import func

from database import SessionLocal, User, ActivityReport, InterrogationReport
from roles.constants import (
    REPORT_ROLE_IDS,
    vacation_id,
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    master_office_id, worker_office_id,
)

# Роли, которым разрешено вызывать /results
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    master_office_id, worker_office_id,
]

# Нижнее изображение
BOTTOM_IMAGE_URL = (
    "https://cdn.discordapp.com/attachments/"
    "1384127668391510070/1385682813801730259/image.png"
)

class ResultsCog(commands.Cog):
    """
    Cog для слэш-команды /results:
      выводит сводку по выполнению недельной нормы и список отпускников.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _do_results(self, interaction: discord.Interaction):
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        week_end   = week_start + datetime.timedelta(days=6)

        guild = interaction.guild
        if guild is None:
            return await interaction.followup.send(
                "❗ Команду можно использовать только на сервере.",
                ephemeral=True
            )

        session = SessionLocal()
        try:
            # Собираем строки в description
            lines: list[str] = [f"**Результаты за {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}:**"]

            emoji_ok   = get(guild.emojis, name="Odobreno") or "✅"
            emoji_fail = get(guild.emojis, name="Otkazano") or "❌"

            for role_id in REPORT_ROLE_IDS:
                role = guild.get_role(role_id)
                if not role:
                    continue
                lines.append(f"\n__{role.name}__")
                for member in role.members:
                    db_user = session.query(User).filter_by(discord_id=member.id).first()
                    if db_user:
                        duties = (
                            session.query(func.coalesce(func.sum(ActivityReport.duties), 0))
                                   .filter(
                                       ActivityReport.user_id == db_user.id,
                                       ActivityReport.date.between(week_start, week_end)
                                   )
                                   .scalar()
                        ) or 0
                        interviews = (
                            session.query(func.count(InterrogationReport.id))
                                   .filter(
                                       InterrogationReport.user_id == db_user.id,
                                       InterrogationReport.date.between(week_start, week_end)
                                   )
                                   .scalar()
                        ) or 0
                    else:
                        duties = interviews = 0

                    ok = (duties >= 3 and interviews >= 1)
                    emoji = emoji_ok if ok else emoji_fail
                    lines.append(f"{member.mention}: дежурств {duties}, допросов {interviews} {emoji}")

            # Отпускники
            vac_role = guild.get_role(vacation_id)
            if vac_role and vac_role.members:
                lines.append("\n**В отпуске:**")
                for m in vac_role.members:
                    lines.append(f"{m.mention}")

            description = "\n".join(lines)

            # Формируем эмбед
            em = discord.Embed(
                title="Judgement Investigation — Итоги недели",
                description=description,
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.utcnow()
            )
            # миниатюра — ваш логотип
            em.set_thumbnail(url=config.EMBLEM_URL)
            # картинка внизу
            em.set_image(url=BOTTOM_IMAGE_URL)

            await interaction.followup.send(embed=em)

        except Exception:
            logging.exception("Ошибка в обработке /results")
            await interaction.followup.send(
                "❗ Произошла ошибка при формировании результатов.",
                ephemeral=True
            )
        finally:
            session.close()

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="results",
        description="Сводка по недельной норме и отпускникам"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_results(self, interaction: discord.Interaction):
        """
        Слэш-команда /results — выводит сводку по нормам и отпускникам.
        """
        await interaction.response.defer(thinking=True)
        await self._do_results(interaction)

    @slash_results.error
    async def slash_results_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            err = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            err.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=err, ephemeral=True)

        logging.exception("Необработанная ошибка в slash_results")
        if not interaction.response.is_done():
            await interaction.response.send_message(
                "❗ Произошла ошибка при выполнении команды.",
                ephemeral=True
            )
        else:
            await interaction.followup.send(
                "❗ Произошла ошибка при выполнении команды.",
                ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(ResultsCog(bot))
