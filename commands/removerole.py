import logging
import datetime
import discord
from discord.ext import commands
from discord import app_commands
from typing import Optional

import config  # DEVELOPMENT_GUILD_ID = 1366412463435944026
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

# Те же, что и в addrole
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
            return await interaction.response.send_message(
                "❗ У меня нет права **Manage Roles**, чтобы снимать роли.",
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

        if role not in member.roles:
            return await interaction.followup.send(
                f"ℹ️ У {member.mention} нет роли {role.mention}.",
                ephemeral=True
            )

        try:
            await member.remove_roles(role, reason=f"/removerole by {interaction.user}")
        except discord.Forbidden:
            return await interaction.followup.send(
                "❗ У меня нет прав на снятие этой роли.",
                ephemeral=True
            )
        except Exception as e:
            logging.exception("Ошибка при удалении роли")
            return await interaction.followup.send(
                f"❗ Не удалось убрать роль: {e}",
                ephemeral=True
            )

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

        await interaction.followup.send(
            f"✅ Роль {role.mention} снята у {member.mention}.{note}"
        )

    @slash_removerole.error
    async def slash_removerole_error(self, interaction: discord.Interaction, error):
        # Нет спец-роли
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

        # Прочие
        logging.exception("Ошибка в slash_removerole")
        if interaction.response.is_done():
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(RemoveRoleCog(bot))
