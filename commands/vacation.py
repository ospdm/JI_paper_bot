# commands/vacation.py

import re
import datetime
import asyncio
import logging

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
import discord
from discord import app_commands
from discord.ext import commands

from roles.constants import (
    vacation_id,
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    master_office_id, worker_office_id,
)
from database import get_db, User, Vacation

# Роли, которым разрешено вызывать /vacation
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    master_office_id, worker_office_id,
]

# Картинка-баннер, выводимая внизу эмбедов
VACATION_BANNER_URL = (
    "https://cdn.discordapp.com/attachments/"
    "1384127668391510070/1385716749281792152/image.png"
)


class VacationCog(commands.Cog):
    """
    Cog для выдачи отпускной роли через слэш:
      • /vacation member:<@user> duration:<XдYчZм>
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _send_embed(self, send: callable, *, title: str, description: str, ephemeral: bool):
        em = discord.Embed(
            title=title,
            description=description,
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        em.set_image(url=VACATION_BANNER_URL)
        await send(embed=em, ephemeral=ephemeral)

    async def _do_vacation(self, member: discord.Member, duration: str, send: callable):
        # 1) Парсим русские суффиксы: XдYчZм
        m = re.fullmatch(
            r'(?:(?P<days>\d+)д)?(?:(?P<hours>\d+)ч)?(?:(?P<minutes>\d+)м)?',
            duration
        )
        if not m or all(v is None for v in m.groupdict().values()):
            return await self._send_embed(
                send,
                title="❗ Ошибка формата",
                description="Неверный формат длительности. Пример: `2д5ч30м`, `3д`, `4ч` или `45м`.",
                ephemeral=True
            )
        days    = int(m.group('days') or 0)
        hours   = int(m.group('hours') or 0)
        minutes = int(m.group('minutes') or 0)
        total_seconds = days*86400 + hours*3600 + minutes*60
        if total_seconds <= 0:
            return await self._send_embed(
                send,
                title="❗ Ошибка формата",
                description="Длительность должна быть больше нуля.",
                ephemeral=True
            )

        # 2) Получаем роль отпуска
        role = member.guild.get_role(vacation_id)
        if not role:
            return await self._send_embed(
                send,
                title="❗ Роль не найдена",
                description="Роль отпуска не найдена на сервере.",
                ephemeral=True
            )

        # 3) Выдаём роль
        try:
            await member.add_roles(role, reason=f"Отпуск на {duration}")
        except discord.Forbidden:
            return await self._send_embed(
                send,
                title="❗ Нет прав",
                description="У меня нет прав на управление этой ролью.",
                ephemeral=True
            )
        except Exception as e:
            logging.exception("Ошибка выдачи роли отпуска")
            return await self._send_embed(
                send,
                title="❗ Ошибка",
                description=f"Не удалось выдать роль отпуска: {e}",
                ephemeral=True
            )

        # 4) Сохраняем запись в БД
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if not user:
                user = User(discord_id=member.id)
                db.add(user)
                db.flush()
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
            logging.exception("Ошибка при сохранении записи отпуска в БД")
        finally:
            db.close()

        # 5) Подтверждение автору
        await self._send_embed(
            send,
            title="🏖️ Отпуск выдан",
            description=(
                f"Роль **{role.name}** выдана {member.mention} на **{duration}**.\n"
                f"Запись создана и будет автоматически закрыта после окончания срока."
            ),
            ephemeral=False
        )

        # 6) Запускаем фоновую задачу для автоматического снятия
        async def _remove():
            await asyncio.sleep(total_seconds)
            try:
                await member.remove_roles(role, reason="Истёк срок отпуска")
                # уведомление о снятии роли
                await self._send_embed(
                    send,
                    title="⌛ Отпуск завершён",
                    description=f"Роль **{role.name}** снята с {member.mention}. Приятной работы!",
                    ephemeral=False
                )
                # закрываем запись в БД
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
                    logging.exception("Ошибка при закрытии записи отпуска в БД")
                finally:
                    db2.close()
            except Exception:
                logging.exception("Ошибка при снятии роли отпуска после истечения срока")

        self.bot.loop.create_task(_remove())

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="vacation",
        description="Выдать отпускную роль на указанное время (e.g. 2д5ч или 45м)"
    )
    @app_commands.describe(
        member="Пользователь, которому выдаётся отпуск",
        duration="Длительность: XдYчZм, например 2д5ч или 45м"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def vacation(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        duration: str
    ):
        """
        /vacation @пользователь duration:<XдYчZм>
        """
        # Проверяем, что у бота есть право Manage Roles
        bot_member = interaction.guild.get_member(self.bot.user.id)  # type: ignore
        if not bot_member.guild_permissions.manage_roles:
            return await interaction.response.send_message(
                "❗ У меня нет права **Manage Roles**, чтобы выдавать роли.",
                ephemeral=True
            )

        await interaction.response.defer(thinking=True)
        await self._do_vacation(member, duration, interaction.followup.send)

    @vacation.error
    async def vacation_error(self, interaction: discord.Interaction, error):
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

        logging.exception("Необработанная ошибка в vacation")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(VacationCog(bot))
