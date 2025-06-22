# commands/warn.py

import logging
import datetime
import discord
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

# Роли, которым разрешено выдавать WARN
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
]

# Баннер для эмбеда
WARN_BANNER_URL = (
    "https://media.discordapp.net/attachments/"
    "1384127668391510070/1385719730823761972/image.png"
)

class WarnCog(commands.Cog):
    """
    Cog для выдачи WARN-ролей:
      • /warn count:<1|2|3> member:<@user> reason:<причина>
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
        em.set_image(url=WARN_BANNER_URL)
        return em

    async def _do_warn(
        self,
        count: int,
        member: discord.Member,
        reason: str,
        send: callable,
        issuer_id: int
    ):
        # 1) Проверка уровня
        if count not in (1, 2, 3):
            em = self._make_embed(
                "❗ Неверный уровень WARN",
                color=discord.Color.red()
            )
            em.add_field(name="🛑 Допустимые уровни", value="1, 2 или 3", inline=False)
            return await send(embed=em, ephemeral=True)

        # 2) Получаем роль на сервере
        role_id = WARN_ROLE_IDS.get(count)
        role = member.guild.get_role(role_id) if role_id else None
        if not role:
            em = self._make_embed(
                f"❗ Роль WARN {count}/3 не найдена",
                color=discord.Color.red()
            )
            return await send(embed=em, ephemeral=True)

        # 3) Снимаем старые и выдаём новую
        to_remove = [
            member.guild.get_role(rid)
            for lvl, rid in WARN_ROLE_IDS.items() if lvl != count
            if member.guild.get_role(rid) in member.roles
        ]
        try:
            if to_remove:
                await member.remove_roles(*to_remove, reason=f"Обновление WARN до {count}/3")
            await member.add_roles(role, reason=f"Выдан WARN {count}/3")
        except discord.Forbidden:
            em = self._make_embed(
                "❗ Нет прав",
                color=discord.Color.red()
            )
            em.add_field(name="🔒 Ошибка", value="У меня нет прав на управление WARN-ролями.", inline=False)
            return await send(embed=em, ephemeral=True)
        except Exception as e:
            logging.exception("Ошибка при выдаче WARN")
            em = self._make_embed(
                "❗ Ошибка при выдаче",
                color=discord.Color.red()
            )
            em.add_field(name="⚠️ Причина", value=str(e), inline=False)
            return await send(embed=em, ephemeral=True)

        # 4) Запись в БД
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if not user:
                user = User(discord_id=member.id)
                db.add(user); db.flush()

            issuer = db.query(User).filter_by(discord_id=issuer_id).first()
            if not issuer:
                issuer = User(discord_id=issuer_id)
                db.add(issuer); db.flush()

            db.add(Warning(user_id=user.id, level=count, issued_by=issuer.id))
            db.commit()
        except Exception:
            logging.exception("Ошибка при сохранении WARN в БД")
            db.rollback()
        finally:
            db.close()

        # 5) Итоговое сообщение
        em = self._make_embed(f"✅ Выдан WARN {count}/3")
        em.add_field(name="👤 Пользователь", value=member.mention, inline=True)
        em.add_field(name="🛑 Варнов", value=f"{count}/3", inline=True)
        em.add_field(name="📝 Причина", value=reason, inline=False)
        await send(embed=em)

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="warn",
        description="Выдать WARN-роль пользователю (1–3)"
    )
    @app_commands.describe(
        count="Уровень WARN (1, 2 или 3)",
        member="Пользователь, которому выдается WARN",
        reason="Причина выдачи WARN"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def warn(
        self,
        interaction: discord.Interaction,
        count: int,
        member: discord.Member,
        reason: str
    ):
        await interaction.response.defer(thinking=True)
        await self._do_warn(count, member, reason, interaction.followup.send, interaction.user.id)

    @warn.error
    async def warn_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="У вас нет доступа к этой команде.",
                color=discord.Color.red()
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            em.add_field(name="Доступ имеют:", value=allowed or "—", inline=False)
            return await interaction.response.send_message(embed=em, ephemeral=True)

        logging.exception("Необработанная ошибка в warn")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(WarnCog(bot))
