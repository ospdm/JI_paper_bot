# commands/steam.py

import re
import logging

import discord
import config  # DEVELOPMENT_GUILD_ID = 1366412463435944026
from discord import app_commands
from discord.ext import commands
from sqlalchemy.exc import SQLAlchemyError

from database import get_db, User
from roles.constants import (
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
)

# Роли, которым разрешено пользоваться steam-командами
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
]

class SteamCog(commands.Cog):
    """
    Cog для управления привязкой SteamID:
      • /bindsteam <SteamID> [member]
      • /steamid [member]
      • /unbindsteam [member]
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _bind(self, steamid: str, member: discord.Member, send):
        if not re.fullmatch(r"STEAM_[0-5]:[01]:\d+", steamid):
            return await send(
                "❗ Неверный формат SteamID. Ожидается STEAM_X:Y:Z, где X—0–5, Y—0 или 1, Z—число.",
                ephemeral=True
            )
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if not user:
                user = User(discord_id=member.id, steam_id=steamid)
                db.add(user)
            else:
                user.steam_id = steamid
            db.commit()
        except SQLAlchemyError:
            db.rollback()
            logging.exception("Ошибка при привязке SteamID")
            return await send(
                "❗ Произошла ошибка при сохранении SteamID в базе.",
                ephemeral=True
            )
        finally:
            db.close()

        await send(f"✅ SteamID `{steamid}` привязан к {member.mention}.")

    async def _show(self, member: discord.Member, send):
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            sid = user.steam_id if user else None
        except SQLAlchemyError:
            logging.exception("Ошибка при получении SteamID из базы")
            return await send(
                "❗ Произошла ошибка при запросе SteamID из базы.",
                ephemeral=True
            )
        finally:
            db.close()

        if sid:
            await send(f"🔗 {member.mention} привязан SteamID: `{sid}`")
        else:
            await send(f"ℹ️ У {member.mention} нет привязанного SteamID.")

    async def _unbind(self, member: discord.Member, send):
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if user and user.steam_id:
                user.steam_id = None
                db.commit()
                await send(f"✅ SteamID отвязан от {member.mention}.")
            else:
                await send(f"ℹ️ У {member.mention} нет привязанного SteamID.")
        except SQLAlchemyError:
            db.rollback()
            logging.exception("Ошибка при отвязке SteamID")
            await send(
                "❗ Произошла ошибка при удалении SteamID из базы.",
                ephemeral=True
            )
        finally:
            db.close()

    # ========== Слэш-команды ==========

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(name="bindsteam", description="Привязать SteamID")
    @app_commands.describe(
        steamid="SteamID формата STEAM_X:Y:Z",
        member="Пользователь (по умолчанию — вы)"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def bindsteam(
        self,
        interaction: discord.Interaction,
        steamid: str,
        member: discord.Member = None
    ):
        if member is None:
            member = interaction.user  # type: ignore
        await interaction.response.defer()
        await self._bind(steamid, member, interaction.followup.send)

    @bindsteam.error
    async def bindsteam_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            embed = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        logging.exception("Необработанная ошибка в bindsteam")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(name="steamid", description="Показать привязанный SteamID")
    @app_commands.describe(
        member="Пользователь (по умолчанию — вы)"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def steamid(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        if member is None:
            member = interaction.user  # type: ignore
        await interaction.response.defer()
        await self._show(member, interaction.followup.send)

    @steamid.error
    async def steamid_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            embed = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        logging.exception("Необработанная ошибка в steamid")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(name="unbindsteam", description="Отвязать SteamID")
    @app_commands.describe(
        member="Пользователь (по умолчанию — вы)"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def unbindsteam(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        if member is None:
            member = interaction.user  # type: ignore
        await interaction.response.defer()
        await self._unbind(member, interaction.followup.send)

    @unbindsteam.error
    async def unbindsteam_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            embed = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            embed.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=embed, ephemeral=True)
        logging.exception("Необработанная ошибка в unbindsteam")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(SteamCog(bot))
