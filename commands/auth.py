# commands/auth.py

import re
import datetime
import logging

import discord
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from database import get_db, User
from roles.constants import (
    jlt_id,
    internship_id,
    wl_inquisitor_id,
    ji_id,
    NEEDS_AUTH_ROLE_ID,  # роль "неавторизованный сотрудник"
)
from typing import Optional

# Каналы
SUBMIT_CHANNEL_ID = 1384833941420118126  # канал, где пользователь подаёт заявку
ADMIN_CHANNEL_ID  = 1385728489755381962  # канал для админов


class AuthView(discord.ui.View):
    """View с кнопками принять/отклонить для админов."""

    def __init__(
        self,
        applicant: discord.Member,
        callsign: str,
        steamid: str,
        comment: str
    ):
        super().__init__(timeout=None)
        self.applicant = applicant
        self.callsign  = callsign
        self.steamid   = steamid
        self.comment   = comment

    @discord.ui.button(label="Принять", style=discord.ButtonStyle.success, custom_id="auth:accept")
    async def accept(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild  = interaction.guild
        member = guild.get_member(self.applicant.id)
        if not member:
            return await interaction.response.send_message(
                "❗ Заявка: пользователь ушёл с сервера.", ephemeral=True
            )

        # 1) выдаём роли и убираем NEEDS_AUTH
        roles_to_add = [
            role for role in (
                guild.get_role(jlt_id),
                guild.get_role(internship_id),
                guild.get_role(wl_inquisitor_id),
                guild.get_role(ji_id),
            ) if role
        ]
        needs = guild.get_role(NEEDS_AUTH_ROLE_ID)
        try:
            if needs and needs in member.roles:
                await member.remove_roles(needs, reason="Авторизация пройдена")
            if roles_to_add:
                await member.add_roles(
                    *roles_to_add,
                    reason=f"Авторизация одобрена {interaction.user}"
                )
        except Exception:
            logging.exception("Не удалось обновить роли при принятии заявки")

        # 2) правим embed в админке
        em = discord.Embed(
            title="✅ Заявка принята",
            description=(
                f"👤 Пользователь: {member.mention}\n"
                f"🎖️ Позывной: `{self.callsign}`\n"
                f"🔗 SteamID: `{self.steamid}`\n"
                f"📝 Комментарий: {self.comment}\n"
                f"✅ Проверяющий: {interaction.user.mention}"
            ),
            color=discord.Color.green(),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        await interaction.message.edit(embed=em, view=None)

        # 3) уведомляем пользователя
        ch = guild.get_channel(SUBMIT_CHANNEL_ID)
        if isinstance(ch, discord.TextChannel):
            notify = discord.Embed(
                title="✅ Ваша заявка принята",
                description=f"{member.mention}, поздравляем — вы авторизованы!",
                color=discord.Color.green(),
                timestamp=datetime.datetime.utcnow()
            )
            notify.set_thumbnail(url=config.EMBLEM_URL)
            notify.add_field(name="🎖️ Позывной",    value=self.callsign, inline=True)
            notify.add_field(name="🔗 SteamID",      value=self.steamid,  inline=True)
            notify.add_field(name="📝 Комментарий", value=self.comment,   inline=False)
            notify.add_field(name="👤 Проверяющий", value=interaction.user.mention, inline=False)
            await ch.send(embed=notify)

        await interaction.response.send_message("Пользователь авторизован.", ephemeral=True)


    @discord.ui.button(label="Отклонить", style=discord.ButtonStyle.danger, custom_id="auth:reject")
    async def reject(self, interaction: discord.Interaction, button: discord.ui.Button):
        guild  = interaction.guild
        member = guild.get_member(self.applicant.id)
        if not member:
            return await interaction.response.send_message(
                "❗ Заявка: пользователь ушёл с сервера.", ephemeral=True
            )

        # 1) выдаём роль "неавторизованный"
        needs = guild.get_role(NEEDS_AUTH_ROLE_ID)
        try:
            if needs and needs not in member.roles:
                await member.add_roles(needs, reason=f"Заявка отклонена {interaction.user}")
        except Exception:
            logging.exception("Не удалось выдать роль неавторизованного")

        # 2) правим embed в админке
        em = discord.Embed(
            title="❌ Заявка отклонена",
            description=(
                f"👤 Пользователь: {member.mention}\n"
                f"🎖️ Позывной: `{self.callsign}`\n"
                f"🔗 SteamID: `{self.steamid}`\n"
                f"📝 Комментарий: {self.comment}\n"
                f"❌ Проверяющий: {interaction.user.mention}"
            ),
            color=discord.Color.red(),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        await interaction.message.edit(embed=em, view=None)

        # 3) уведомляем пользователя
        ch = guild.get_channel(SUBMIT_CHANNEL_ID)
        if isinstance(ch, discord.TextChannel):
            notify = discord.Embed(
                title="❌ Ваша заявка отклонена",
                description=f"{member.mention}, к сожалению, вы не прошли авторизацию.",
                color=discord.Color.red(),
                timestamp=datetime.datetime.utcnow()
            )
            notify.set_thumbnail(url=config.EMBLEM_URL)
            notify.add_field(name="🎖️ Позывной",    value=self.callsign, inline=True)
            notify.add_field(name="🔗 SteamID",      value=self.steamid,  inline=True)
            notify.add_field(name="📝 Комментарий",  value=self.comment,  inline=False)
            notify.add_field(name="👤 Проверяющий",  value=interaction.user.mention, inline=False)
            await ch.send(embed=notify)

        await interaction.response.send_message("Заявка отклонена.", ephemeral=True)



class AuthCog(commands.Cog):
    """Cog для подачи заявки /auth и обработки кнопок."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="auth",
        description="Подать заявку на авторизацию в JI"
    )
    @app_commands.describe(
        callsign="Ваш позывной",
        steamid="Ваш SteamID (формат STEAM_X:Y:Z)",
        comment="Комментарий для проверяющего (необязательно)"
    )
    async def auth(
        self,
        interaction: discord.Interaction,
        callsign: str,
        steamid: str,
        comment: Optional[str] = ""
    ):
        member = interaction.user  # type: ignore

        # --- 1) Валидация ---
        if not re.fullmatch(r"STEAM_[0-5]:[01]:\d+", steamid):
            return await interaction.response.send_message(
                "❗ Неверный формат SteamID: STEAM_X:Y:Z", ephemeral=True
            )
        callsign = callsign.strip()
        if not callsign or len(callsign) > 64:
            return await interaction.response.send_message(
                "❗ Позывной должен быть 1–64 символа.", ephemeral=True
            )

        # --- 2) Запись в БД ---
        db = next(get_db())
        try:
            # уникальность позывного
            other = db.query(User).filter_by(call_sign=callsign).first()
            if other and other.discord_id != member.id:
                return await interaction.response.send_message(
                    "❗ Этот позывной уже используется.", ephemeral=True
                )
            # сохраняем/обновляем
            usr = db.query(User).filter_by(discord_id=member.id).first()
            if not usr:
                usr = User(discord_id=member.id, call_sign=callsign, steam_id=steamid)
                db.add(usr)
            else:
                usr.call_sign = callsign
                usr.steam_id  = steamid
            db.commit()
        except Exception:
            db.rollback()
            logging.exception("Ошибка при сохранении заявки в БД")
            return await interaction.response.send_message(
                "❗ Не удалось сохранить заявку.", ephemeral=True
            )
        finally:
            db.close()

        # --- 3) Ответ пользователю ---
        em = discord.Embed(
            title="✅ Ваша заявка отправлена на рассмотрение",
            description=(
                f"🎖️ Позывной: `{callsign}`\n"
                f"🔗 SteamID: `{steamid}`\n"
                f"📝 Комментарий: {comment or '—'}"
            ),
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        await interaction.response.send_message(embed=em, ephemeral=True)

        # --- 4) Отправка в админ-канал ---
        admin_ch = self.bot.get_channel(ADMIN_CHANNEL_ID)
        if isinstance(admin_ch, discord.TextChannel):
            em2 = discord.Embed(
                title="⏳ Заявка на рассмотрении",
                description=(
                    f"👤 Пользователь: {member.mention}\n"
                    f"🎖️ Позывной: `{callsign}`\n"
                    f"🔗 SteamID: `{steamid}`\n"
                    f"📝 Комментарий: {comment or '—'}"
                ),
                color=discord.Color.from_rgb(255, 255, 255),
                timestamp=datetime.datetime.utcnow()
            )
            em2.set_thumbnail(url=config.EMBLEM_URL)
            view = AuthView(
                applicant=interaction.user,
                callsign=callsign,
                steamid=steamid,
                comment=comment or "—"
            )
            await admin_ch.send(embed=em2, view=view)

    @commands.Cog.listener()
    async def on_ready(self):
        # регистрируем View для персистентности кнопок
        self.bot.add_view(AuthView(None, "", "", ""))


async def setup(bot: commands.Bot):
    await bot.add_cog(AuthCog(bot))
