# commands/denied.py

import logging
import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from sqlalchemy import delete
from database import SessionLocal, ActivityReport, InterrogationReport, User
from roles.constants import (
    CHANNELS,
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    worker_office_id, master_office_id,
)

# Роли, которым разрешено отклонять отчёты
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    worker_office_id, master_office_id,
]


class DeniedCog(commands.Cog):
    """Команда /denied — отклонить отчёт прямо в треде и удалить его из БД"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="denied",
        description="Отклонить отчёт в текущем треде"
    )
    @app_commands.describe(
        reason="Причина отказа"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def denied(
        self,
        interaction: discord.Interaction,
        reason: str
    ):
        # 1) Убедимся, что мы в нужном треде
        if not isinstance(interaction.channel, discord.Thread):
            return await interaction.response.send_message(
                "❗ Эту команду можно использовать только внутри треда с отчётом.",
                ephemeral=True
            )
        if interaction.channel.parent_id not in (CHANNELS['activity'], CHANNELS['interrogation']):
            act, intr = CHANNELS['activity'], CHANNELS['interrogation']
            return await interaction.response.send_message(
                f"❗ Используйте эту команду только в тредах каналов:\n"
                f"• Активность — <#{act}>\n"
                f"• Допросы   — <#{intr}>",
                ephemeral=True
            )

        # 2) defer чтобы можно было потом followup
        await interaction.response.defer(ephemeral=True)

        # 3) находим ID связанного отчёта
        ev = self.bot.get_cog("Events")
        ar_id = ev.thread_to_activity.get(interaction.channel.id)
        ir_id = ev.thread_to_interrogation.get(interaction.channel.id)
        if ar_id is None and ir_id is None:
            return await interaction.followup.send(
                "❗ Не удалось найти запись отчёта для этого треда.", ephemeral=True
            )

        session = SessionLocal()
        try:
            # 4) достаём report и discord_id пользователя
            if ar_id:
                report = session.get(ActivityReport, ar_id)
            else:
                report = session.get(InterrogationReport, ir_id)
            user_rec = session.get(User, report.user_id)
            user_discord_id = user_rec.discord_id if user_rec else None

            # 5) удаляем отчёт из БД
            if ar_id:
                session.execute(delete(ActivityReport).where(ActivityReport.id == ar_id))
            else:
                session.execute(delete(InterrogationReport).where(InterrogationReport.id == ir_id))
            session.commit()
        except Exception:
            logging.exception("Ошибка при удалении отчёта из БД")
            return await interaction.followup.send(
                "❗ Произошла ошибка при удалении записи.", ephemeral=True
            )
        finally:
            session.close()

        # 6) уведомляем автора прямо в треде
        guild = interaction.guild
        if user_discord_id:
            member = guild.get_member(user_discord_id)
            mention = member.mention if member else f"<@{user_discord_id}>"
        else:
            mention = "пользователь"

        embed = discord.Embed(
            title="❌ Ваш отчёт отклонён",
            description=(
                f"{mention}, ваш отчёт **удалён**.\n"
                f"**Причина:** {reason}"
            ),
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        embed.set_thumbnail(url=config.EMBLEM_URL)
        embed.set_footer(
            text=f"Отказал {interaction.user.mention}",
            icon_url=interaction.user.display_avatar.url
        )
        await interaction.channel.send(embed=embed)

        # 7) подтверждаем модератору
        await interaction.followup.send(
            "✅ Отчёт удалён и пользователь уведомлён.", ephemeral=True
        )

    async def cog_app_command_error(self, interaction: discord.Interaction, error: app_commands.AppCommandError):
        # обработка MissingAnyRole
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            em.add_field(name="Доступ имеют роли:", value=allowed or "—", inline=False)
            if not interaction.response.is_done():
                await interaction.response.send_message(embed=em, ephemeral=True)
            else:
                await interaction.followup.send(embed=em, ephemeral=True)
            return
        logging.exception("Необработанная ошибка в DeniedCog.denied")

async def setup(bot: commands.Bot):
    await bot.add_cog(DeniedCog(bot))
