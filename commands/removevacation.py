# commands/removevacation.py

import logging
import datetime

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
import discord
from discord import app_commands
from discord.ext import commands

from database import get_db, User, Vacation
from roles.constants import  (
    vacation_id,
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    master_office_id, worker_office_id,
)

# Роли, которым разрешено вызывать /removevacation
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    master_office_id, worker_office_id,
]

# Баннер внизу эмбедов
REMOVE_VACATION_BANNER = (
    "https://media.discordapp.net/attachments/"
    "1384127668391510070/1385719931613483048/image.png"
)


class RemoveVacationCog(commands.Cog):
    """
    Cog с единственной слэш-командой /removevacation:
    снимает отпускную роль и закрывает запись в БД.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_embed(self, send: callable, *, title: str, description: str, ephemeral: bool):
        em = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        em.set_image(url=REMOVE_VACATION_BANNER)
        await send(embed=em, ephemeral=ephemeral)

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="removevacation",
        description="Снять отпускную роль у пользователя и закрыть запись в базе"
    )
    @app_commands.describe(
        member="Пользователь, у которого снимаем отпуск"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_removevacation(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        # Defer + ephemeral, потом используем followup
        await interaction.response.defer(ephemeral=True)

        # 1) Получаем роль отпуска
        guild = interaction.guild
        role = guild.get_role(vacation_id) if guild else None
        if not role:
            return await self._send_embed(
                interaction.followup.send,
                title="❗ Роль не найдена",
                description="Роль отпуска не найдена на сервере.",
                ephemeral=True
            )

        # 2) Проверяем наличие роли у пользователя
        if role not in member.roles:
            return await self._send_embed(
                interaction.followup.send,
                title="ℹ️ Нет роли",
                description=f"У {member.mention} нет отпускной роли.",
                ephemeral=True
            )

        # 3) Снимаем роль
        try:
            await member.remove_roles(role, reason=f"/removevacation by {interaction.user}")
        except discord.Forbidden:
            return await self._send_embed(
                interaction.followup.send,
                title="❗ Нет прав",
                description="У меня нет прав на снятие этой роли.",
                ephemeral=True
            )
        except Exception as e:
            logging.exception("Ошибка при снятии отпускной роли")
            return await self._send_embed(
                interaction.followup.send,
                title="❗ Ошибка",
                description=f"Не удалось снять роль: {e}",
                ephemeral=True
            )

        # 4) Закрываем запись в БД
        note = ""
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if user:
                vac = (
                    db.query(Vacation)
                      .filter_by(user_id=user.id, active=True)
                      .order_by(Vacation.start_at.desc())
                      .first()
                )
                if vac:
                    vac.active = False
                    vac.end_at = datetime.datetime.utcnow()
                    db.commit()
                    note = "\nℹ️ Запись отпуска закрыта в базе."
        except Exception:
            logging.exception("Ошибка при закрытии записи отпуска в БД")
        finally:
            db.close()

        # 5) Финальный ответ
        await self._send_embed(
            interaction.followup.send,
            title="✅ Отпуск снят",
            description=f"Отпускная роль **{role.name}** снята у {member.mention}.{note}",
            ephemeral=True
        )

    @slash_removevacation.error
    async def slash_removevacation_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            em.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=em, ephemeral=True)

        logging.exception("Ошибка в slash_removevacation")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RemoveVacationCog(bot))
