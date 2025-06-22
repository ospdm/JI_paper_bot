# commands/removerole.py

import logging
import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from database import get_db, User, Vacation
from roles.constants import (
    RANKS_MAP,
    CORPS_MAP,
    VACATION_MAP,
    POST_MAP,
    arc_id,
    lrc_gimel_id,
    lrc_id,
    head_ji_id,
    adjutant_ji_id,
    leader_office_id,
    leader_penal_battalion_id,
    senate_id,
    head_curator_id,
    director_office_id,
    leader_main_corps_id,
    leader_gimel_id,
)

# Собираем все роли для снятия
ROLE_MAP = {}
ROLE_MAP.update(RANKS_MAP)
ROLE_MAP.update(CORPS_MAP)
ROLE_MAP.update(VACATION_MAP)
ROLE_MAP.update(POST_MAP)
ALLOWED_ROLE_IDS = set(ROLE_MAP.values())

# Те же роли, что и в addrole
ALLOWED_ISSUER_ROLES = [
    arc_id,
    lrc_gimel_id,
    lrc_id,
    head_ji_id,
    adjutant_ji_id,
    leader_office_id,
    leader_penal_battalion_id,
    senate_id,
    head_curator_id,
    director_office_id,
    leader_main_corps_id,
    leader_gimel_id,
]


class RemoveRoleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _make_embed(
        self,
        title: str,
        description: Optional[str] = None,
        color: discord.Color = discord.Color.from_rgb(255, 255, 255),
    ) -> discord.Embed:
        em = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        return em

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="removerole",
        description="Снять роль у пользователя (через упоминание роли)"
    )
    @app_commands.describe(
        role="Роль для снятия",
        member="Пользователь, у которого снимаем роль (по умолчанию — вы)"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_removerole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        member: Optional[discord.Member] = None
    ):
        # Проверяем, что бот может управлять ролями
        me = interaction.guild.me  # type: ignore
        if not me.guild_permissions.manage_roles:
            em = self._make_embed(
                title="❗ Нет права Manage Roles",
                description="У меня нет права **Manage Roles**, чтобы снимать роли.",
                color=discord.Color.red()
            )
            return await interaction.response.send_message(embed=em, ephemeral=True)

        await interaction.response.defer(thinking=True)

        if member is None:
            member = interaction.user  # type: ignore

        # Нет такой роли у пользователя
        if role not in member.roles:
            em = self._make_embed(
                title="ℹ️ Роли нет",
                description=f"У {member.mention} нет роли {role.mention}.",
                color=discord.Color.orange()
            )
            return await interaction.followup.send(embed=em, ephemeral=True)

        # Пытаемся снять
        try:
            await member.remove_roles(role, reason=f"/removerole by {interaction.user}")
        except discord.Forbidden:
            em = self._make_embed(
                title="❗ Нет прав",
                description="У меня нет прав на снятие этой роли.",
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=em, ephemeral=True)
        except Exception as e:
            logging.exception("Ошибка при удалении роли")
            em = self._make_embed(
                title="❗ Не удалось удалить роль",
                description=str(e),
                color=discord.Color.red()
            )
            return await interaction.followup.send(embed=em, ephemeral=True)

        # Если это отпускная роль — закрываем запись в БД
        note = ""
        if role.id in VACATION_MAP.values():
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
                logging.exception("Ошибка при закрытии записи отпуска")
            finally:
                db.close()

        # Успешный Embed
        em = self._make_embed(
            title="✅ Роль снята",
            description=f"Роль {role.mention} снята у {member.mention}.{note}",
            color=discord.Color.green()
        )
        await interaction.followup.send(embed=em)

    @slash_removerole.error
    async def slash_removerole_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            em = self._make_embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            em.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=em, ephemeral=True)

        logging.exception("Ошибка в slash_removerole")
        em = self._make_embed(
            title="❗ Произошла ошибка",
            color=discord.Color.red()
        )
        await interaction.response.send_message(embed=em, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RemoveRoleCog(bot))
