# commands/removewarn.py

import logging
import datetime
import discord
from typing import Optional
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from roles.constants import (
    WARN_ROLE_IDS,
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
)
from database import get_db, User, Warning

# Роли, которым разрешено вызывать /removewarn
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
]

class RemoveWarnCog(commands.Cog):
    """
    Cog для слэш-команды:
      • /removewarn count:<1|2|3> member:@user? reason:<текст>
    Снимает WARN-роль и удаляет запись WARN из БД.
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _make_embed(
        self,
        title: str,
        color: discord.Color = discord.Color.from_rgb(255, 255, 255)
    ) -> discord.Embed:
        em = discord.Embed(
            title=title,
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        return em

    async def _do_remove_warn(
        self,
        interaction: discord.Interaction,
        count: int,
        member: discord.Member,
        reason: str
    ):
        # 1) Проверяем корректность уровня
        if count not in WARN_ROLE_IDS:
            em = self._make_embed("❗ Неверный уровень WARN", color=discord.Color.red())
            em.add_field(name="🛑 Допустимые уровни", value="1, 2 или 3", inline=False)
            return await interaction.followup.send(embed=em, ephemeral=True)

        # 2) Проверяем наличие роли
        role_id = WARN_ROLE_IDS[count]
        role = interaction.guild.get_role(role_id) if interaction.guild else None
        if not role:
            em = self._make_embed(f"❗ Роль WARN {count}/3 не найдена", color=discord.Color.red())
            return await interaction.followup.send(embed=em, ephemeral=True)
        if role not in member.roles:
            em = self._make_embed("ℹ️ У пользователя нет WARN-ролей", color=discord.Color.orange())
            em.add_field(name="👤 Пользователь", value=member.mention, inline=False)
            return await interaction.followup.send(embed=em, ephemeral=True)

        # 3) Снимаем роль
        try:
            await member.remove_roles(role, reason=f"Снят WARN {count}/3 командой {interaction.user}")
        except discord.Forbidden:
            em = self._make_embed("❗ Нет прав", color=discord.Color.red())
            em.add_field(name="🔒 Ошибка", value="У меня нет прав на управление WARN-ролями.", inline=False)
            return await interaction.followup.send(embed=em, ephemeral=True)
        except Exception as e:
            logging.exception("Ошибка при снятии WARN")
            em = self._make_embed("❗ Ошибка", color=discord.Color.red())
            em.add_field(name="⚠️ Причина", value=str(e), inline=False)
            return await interaction.followup.send(embed=em, ephemeral=True)

        # 4) Удаляем запись из БД
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if user:
                last = (
                    db.query(Warning)
                      .filter_by(user_id=user.id, level=count)
                      .order_by(Warning.issued_at.desc())
                      .first()
                )
                if last:
                    db.delete(last)
                    db.commit()
        except Exception:
            logging.exception("Ошибка при удалении записи WARN из БД")
            db.rollback()
        finally:
            db.close()

        # 5) Итоговый эмбед
        em = self._make_embed(f"✅ Снят WARN {count}/3")
        em.add_field(name="👤 Пользователь", value=member.mention, inline=True)
        em.add_field(name="🛑 Уровень", value=f"{count}/3", inline=True)
        em.add_field(name="📝 Причина", value=reason, inline=False)
        await interaction.followup.send(embed=em)

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="removewarn",
        description="Снять WARN-роль у пользователя"
    )
    @app_commands.describe(
        count="Уровень WARN (1, 2 или 3)",
        member="Пользователь (по умолчанию — вы)",
        reason="Причина снятия WARN"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_removewarn(
        self,
        interaction: discord.Interaction,
        count: int,
        member: Optional[discord.Member] = None,
        reason: str = "Причина не указана"
    ):
        if member is None:
            member = interaction.user  # type: ignore
        await interaction.response.defer(thinking=True, ephemeral=True)
        await self._do_remove_warn(interaction, count, member, reason)

    @slash_removewarn.error
    async def slash_removewarn_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            em.add_field(name="Доступ имеют:", value=allowed or "—", inline=False)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        logging.exception("Необработанная ошибка в slash_removewarn")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(RemoveWarnCog(bot))
