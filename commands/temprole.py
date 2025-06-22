# commands/temprole.py

import re
import asyncio
import datetime
import logging

import config
import discord
from discord import app_commands
from discord.ext import commands
from typing import Optional

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

# Словарь всех ключ→ID ролей
ROLE_MAP: dict[str, int] = {}
ROLE_MAP.update(RANKS_MAP)
ROLE_MAP.update(CORPS_MAP)
ROLE_MAP.update(VACATION_MAP)
ROLE_MAP.update(POST_MAP)

# Разрешённые ID ролей для выдачи
ALLOWED_ROLE_IDS = set(ROLE_MAP.values())

# Роли, которым можно вызывать /tempaddrole
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


class TempRoleCog(commands.Cog):
    """
    Cog для временной выдачи ролей через слэш:
      • /tempaddrole <роль> <длительность> <@member>
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _apply_role(
        self,
        role: discord.Role,
        duration: str,
        member: discord.Member,
        send: callable
    ):
        # 1) проверяем, что роль поддерживается
        if role.id not in ALLOWED_ROLE_IDS:
            mentions = " ".join(f"<@&{rid}>" for rid in ALLOWED_ROLE_IDS)
            return await send(
                f"❗ Роль {role.mention} не поддерживается этой командой.\n"
                f"Доступные роли: {mentions}",
                ephemeral=True
            )

        # 2) парсим длительность
        m = re.fullmatch(
            r'(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?',
            duration
        )
        if not m:
            return await send(
                "❗ Неверный формат длительности. Пример: `1d2h30m` или `45m`.",
                ephemeral=True
            )
        days    = int(m.group('days') or 0)
        hours   = int(m.group('hours') or 0)
        minutes = int(m.group('minutes') or 0)
        total_seconds = days*86400 + hours*3600 + minutes*60
        if total_seconds <= 0:
            return await send("❗ Длительность должна быть больше нуля.", ephemeral=True)

        # 3) выдаём роль
        try:
            await member.add_roles(role, reason=f"TempRole {duration}")
            await send(f"✅ Роль **{role.name}** выдана {member.mention} на `{duration}`.")
        except discord.Forbidden:
            return await send("❗ У меня нет прав на управление этой ролью.", ephemeral=True)
        except Exception as e:
            logging.exception("Ошибка при выдаче временной роли")
            return await send(f"❗ Не удалось выдать роль: {e}", ephemeral=True)

        # 4) если отпуск — сохраняем в БД
        if role.id in VACATION_MAP.values():
            db = next(get_db())
            try:
                user = db.query(User).filter_by(discord_id=member.id).first()
                if not user:
                    user = User(discord_id=member.id, call_sign=None)
                    db.add(user); db.flush()
                now = datetime.datetime.utcnow()
                vac = Vacation(
                    user_id=user.id,
                    start_at=now,
                    end_at=now + datetime.timedelta(seconds=total_seconds),
                    active=True
                )
                db.add(vac)
                db.commit()
            except Exception:
                logging.exception("Ошибка при сохранении отпуска в БД")
            finally:
                db.close()

        # 5) планируем снятие
        async def _remove():
            await asyncio.sleep(total_seconds)
            try:
                await member.remove_roles(role, reason=f"Истёк срок {duration}")
                try:
                    await send(f"⌛ Время вышло: роль **{role.name}** снята с {member.mention}.")
                except:
                    pass
                if role.id in VACATION_MAP.values():
                    db2 = next(get_db())
                    try:
                        u2 = db2.query(User).filter_by(discord_id=member.id).first()
                        if u2:
                            last = (
                                db2.query(Vacation)
                                   .filter_by(user_id=u2.id, active=True)
                                   .order_by(Vacation.start_at.desc())
                                   .first()
                            )
                            if last:
                                last.active = False
                                last.end_at = datetime.datetime.utcnow()
                                db2.commit()
                    except Exception:
                        logging.exception("Ошибка при закрытии отпуска в БД")
                    finally:
                        db2.close()
            except Exception:
                logging.exception("Ошибка при снятии временной роли")

        self.bot.loop.create_task(_remove())

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="tempaddrole",
        description="Выдать пользователю роль на указанное время (e.g. 1d2h30m)"
    )
    @app_commands.describe(
        role="Роль для выдачи (упоминание)",
        duration="Длительность: NdNhNm, например 1d2h30m или 45m",
        member="Пользователь, которому выдаётся роль"
    )
    @app_commands.checks.has_permissions(manage_roles=True)
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def tempaddrole(
        self,
        interaction: discord.Interaction,
        role: discord.Role,
        duration: str,
        member: discord.Member  # теперь обязательно
    ):
        # проверяем право бота
        me = interaction.guild.me  # type: ignore
        if not me.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "❗ У меня нет права **Manage Roles**, чтобы выдавать роли.",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True)
        await self._apply_role(role, duration, member, interaction.followup.send)

    @tempaddrole.error
    async def tempaddrole_error(self, interaction: discord.Interaction, error):
        # нет ни одной из спец-ролей
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

        # нет права Manage Roles у юзера
        if isinstance(error, app_commands.MissingPermissions):
            return await interaction.response.send_message(
                "❌ Для этой команды нужно право Manage Roles",
                ephemeral=True
            )

        # всё остальное
        logging.exception("Ошибка в tempaddrole")
        if interaction.response.is_done():
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(TempRoleCog(bot))
