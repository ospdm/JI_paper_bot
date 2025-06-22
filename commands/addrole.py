# commands/addrole.py

import logging
import datetime
from typing import Optional

import discord
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from database import get_db, User
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
    curator_id,
    worker_office_id,
    master_office_id,
)

# Собираем все мапы ролей
ROLE_MAP = {}
ROLE_MAP.update(RANKS_MAP)
ROLE_MAP.update(CORPS_MAP)
ROLE_MAP.update(VACATION_MAP)
ROLE_MAP.update(POST_MAP)

# ID ролей, которые можно выдавать через эту команду
ALLOWED_ROLE_IDS = set(ROLE_MAP.values())

# Роли, которым разрешено вызывать /addrole
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
    curator_id,
    worker_office_id,
    master_office_id,
]


class AddRoleCog(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="addrole",
        description="Выдать роль пользователю (через упоминание роли)"
    )
    @app_commands.describe(
        role="Роль для выдачи (выберите из списка)",
        member="Пользователь, которому выдаём роль (по умолчанию — вы)"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_addrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        member: Optional[discord.Member] = None
    ):
        # Проверяем, что у бота есть право Manage Roles
        me = interaction.guild.me  # type: ignore
        if not me.guild_permissions.manage_roles:
            em = discord.Embed(
                title="❗ Нет права Manage Roles",
                description="У меня нет права **Manage Roles**, чтобы выдавать роли.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        await interaction.response.defer(thinking=True)

        if member is None:
            member = interaction.user  # type: ignore

        if role in member.roles:
            em = discord.Embed(
                title="ℹ️ Роль уже есть",
                description=f"У {member.mention} уже есть роль {role.mention}.",
                color=discord.Color.orange(),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            return await interaction.followup.send(embed=em, ephemeral=True)

        try:
            await member.add_roles(role, reason=f"/addrole by {interaction.user}")
        except discord.Forbidden:
            em = discord.Embed(
                title="❗ Нет прав",
                description="У меня нет прав на выдачу этой роли.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            return await interaction.followup.send(embed=em, ephemeral=True)
        except Exception as e:
            logging.exception("Ошибка при выдаче роли")
            em = discord.Embed(
                title="❗ Не удалось выдать роль",
                description=str(e),
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            return await interaction.followup.send(embed=em, ephemeral=True)

        # Обновляем БД (если роль — ранг или корпус)
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if not user:
                user = User(discord_id=member.id)
                db.add(user)
                db.flush()

            if role.id in RANKS_MAP.values() and user.current_rank_id != role.id:
                user.current_rank_id = role.id
            if role.id in CORPS_MAP.values() and user.current_corps_id != role.id:
                user.current_corps_id = role.id

            db.commit()
        except Exception:
            logging.exception("Ошибка при обновлении User после addrole")
            db.rollback()
        finally:
            db.close()

        # — Успешный ответ —
        success = discord.Embed(
            title="✅ Роль выдана",
            description=f"Роль {role.mention} выдана {member.mention}.",
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        success.set_thumbnail(url=config.EMBLEM_URL)
        await interaction.followup.send(embed=success)

    @slash_addrole.error
    async def slash_addrole_error(self, interaction: discord.Interaction, error):
        # Если у пользователя нет одной из спец-ролей
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступ к этой команде.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            em.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=em, ephemeral=True)

        # Прочие ошибки
        logging.exception("Необработанная ошибка в slash_addrole")
        if interaction.response.is_done():
            await interaction.followup.send("❗ Произошла ошибка при выполнении команды.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Произошла ошибка при выполнении команды.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AddRoleCog(bot))
