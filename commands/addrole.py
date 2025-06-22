# commands/addrole.py

import logging
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

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
import config  # DEVELOPMENT_GUILD_ID = 1366412463435944026
from database import get_db, User

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
            return await interaction.response.send_message(
                "❗ У меня нет права **Manage Roles**, чтобы выдавать роли.",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True)

        if member is None:
            member = interaction.user  # type: ignore

        if role.id not in ALLOWED_ROLE_IDS:
            mentions = " ".join(f"<@&{rid}>" for rid in ROLE_MAP.values())
            return await interaction.followup.send(
                f"❗ Роль {role.mention} не поддерживается этой командой.\n"
                f"Доступные: {mentions}",
                ephemeral=True
            )

        if role in member.roles:
            return await interaction.followup.send(
                f"ℹ️ У {member.mention} уже есть роль {role.mention}.",
                ephemeral=True
            )

        try:
            await member.add_roles(role, reason=f"/addrole by {interaction.user}")
        except discord.Forbidden:
            return await interaction.followup.send(
                "❗ У меня нет прав на выдачу этой роли.",
                ephemeral=True
            )
        except Exception as e:
            logging.exception("Ошибка при выдаче роли")
            return await interaction.followup.send(
                f"❗ Не удалось выдать роль: {e}",
                ephemeral=True
            )

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

        await interaction.followup.send(
            f"✅ Роль {role.mention} выдана {member.mention}."
        )

    @slash_addrole.error
    async def slash_addrole_error(self, interaction: discord.Interaction, error):
        # Если у пользователя нет одной из спец-ролей
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            embed = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступ к этой команде.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)

        # Прочие ошибки
        logging.exception("Необработанная ошибка в slash_addrole")
        if interaction.response.is_done():
            await interaction.followup.send("❗ Произошла ошибка при выполнении команды.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Произошла ошибка при выполнении команды.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(AddRoleCog(bot))
