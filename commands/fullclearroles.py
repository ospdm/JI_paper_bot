# commands/fullclearroles.py

import logging
import datetime

import discord
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from roles.constants import (
    arc_id,
    lrc_gimel_id,
    lrc_id,
    head_ji_id,
    adjutant_ji_id,
    leader_office_id,
    leader_penal_battalion_id,
    senate_id,
    director_office_id,
    leader_main_corps_id,
    leader_gimel_id,
)

# Роли, которым разрешено вызывать /fullclearroles и /returnroles
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
]


class FullClearRolesCog(commands.Cog):
    """
    Cog для слэш-команд:
      • /fullclearroles @user <комментарий> — снять у пользователя все роли (кроме @everyone)
      • /returnroles     @user           — вернуть снятые ранее роли
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        # память про снятые роли: member_id -> [role_id, ...]
        self._cleared_roles: dict[int, list[int]] = {}

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="fullclearroles",
        description="Снять у пользователя все роли (кроме @everyone)"
    )
    @app_commands.describe(
        member="Пользователь, у которого нужно снять роли",
        comment="Комментарий для протокола"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_fullclearroles(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        comment: str
    ):
        await interaction.response.defer(thinking=True)

        # роли, которые снимем
        to_remove = [
            role for role in member.roles
            if role != interaction.guild.default_role
        ]
        # сохраняем их ID в память
        self._cleared_roles[member.id] = [r.id for r in to_remove]

        try:
            if to_remove:
                await member.remove_roles(
                    *to_remove,
                    reason=f"Full clear by {interaction.user}: {comment}"
                )

            em = discord.Embed(
                title="⚠️ Все роли очищены",
                description=(
                    f"👤 Пользователь: {member.mention}\n"
                    f"📝 Комментарий: {comment}\n"
                    f"👮 Исполнитель: {interaction.user.mention}"
                ),
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            await interaction.followup.send(embed=em)

        except discord.Forbidden:
            await interaction.followup.send(
                "❗ У меня нет прав на удаление ролей у этого пользователя.",
                ephemeral=True
            )
        except Exception as e:
            logging.exception("Ошибка при выполнении fullclearroles")
            await interaction.followup.send(
                f"❗ Произошла ошибка: {e}", ephemeral=True
            )

    @slash_fullclearroles.error
    async def slash_fullclearroles_error(
        self,
        interaction: discord.Interaction,
        error
    ):
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

        logging.exception("Необработанная ошибка в slash_fullclearroles")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)


    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="returnroles",
        description="Вернуть ранее снятые у пользователя роли"
    )
    @app_commands.describe(
        member="Пользователь, у которого вернуть роли"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_returnroles(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        await interaction.response.defer(thinking=True)

        saved = self._cleared_roles.get(member.id)
        if not saved:
            em = discord.Embed(
                title="ℹ️ Нечего возвращать",
                description=f"У {member.mention} нет сохранённых ролей для возврата.",
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            return await interaction.followup.send(embed=em)

        # восстанавливаем роли
        guild = interaction.guild
        roles = []
        for rid in saved:
            role = guild.get_role(rid)
            if role:
                roles.append(role)
        try:
            if roles:
                await member.add_roles(
                    *roles,
                    reason=f"Return roles by {interaction.user}"
                )
            # очистим память
            del self._cleared_roles[member.id]

            em = discord.Embed(
                title="✅ Роли возвращены",
                description=(
                    f"👤 Пользователь: {member.mention}\n"
                    f"🔄 Количество ролей: {len(roles)}\n"
                    f"👮 Исполнитель: {interaction.user.mention}"
                ),
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.utcnow()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            # покажем список имён восстановленных ролей
            if roles:
                em.add_field(
                    name="📋 Роли",
                    value=", ".join(r.name for r in roles),
                    inline=False
                )
            await interaction.followup.send(embed=em)

        except discord.Forbidden:
            await interaction.followup.send(
                "❗ У меня нет прав на добавление ролей этому пользователю.",
                ephemeral=True
            )
        except Exception as e:
            logging.exception("Ошибка при выполнении returnroles")
            await interaction.followup.send(
                f"❗ Произошла ошибка: {e}", ephemeral=True
            )

    @slash_returnroles.error
    async def slash_returnroles_error(
        self,
        interaction: discord.Interaction,
        error
    ):
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

        logging.exception("Необработанная ошибка в slash_returnroles")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(FullClearRolesCog(bot))
