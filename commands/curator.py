# commands/curator.py

import datetime
import logging
from sqlalchemy.exc import SQLAlchemyError

import discord
from discord import app_commands
from discord.ext import commands

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from database import get_db, User
from roles.constants import (
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
)

# Роли, которым разрешено пользоваться curator-командами
ALLOWED_CURATOR_ROLES = [
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
]

# URL вашего bottom-изображения
LEGENDS_URL = (
    "https://media.discordapp.net/attachments/"
    "1303690765163036672/1360325913761415200/Legends.png"
)

class CuratorCog(commands.Cog):
    """
    Cog для управления куратором через слэш-команды:
      • /assigncurator — назначить куратора
      • /removecurator  — удалить куратора
      • /whoiscurator   — узнать куратора
    """

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    def _make_embed(
        self,
        title: str,
        description: str,
        color: discord.Color = discord.Color.from_rgb(255, 255, 255)
    ) -> discord.Embed:
        """Утилита для базового Embed с эмблемой и bottom-картинкой."""
        em = discord.Embed(
            title=title,
            description=description,
            color=color,
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        em.set_image(url=LEGENDS_URL)
        em.set_footer(
            text="— Воспитание новых талантов — наша главная задача",
            icon_url=config.EMBLEM_URL
        )
        return em

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="assigncurator",
        description="Назначить куратора"
    )
    @app_commands.describe(
        member="Пользователь, которому назначаем куратора",
        curator="Кто станет куратором"
    )
    @app_commands.checks.has_any_role(*ALLOWED_CURATOR_ROLES)
    async def assigncurator(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        curator: discord.Member
    ):
        """Сохраняет в БД, что curator теперь куратор для member."""
        await interaction.response.defer(thinking=True)
        db = next(get_db())
        try:
            # 1) User для member
            user = db.query(User).filter_by(discord_id=member.id).first()
            if not user:
                user = User(discord_id=member.id, call_sign=member.display_name)
                db.add(user); db.flush()

            # 2) User для curator
            cur = db.query(User).filter_by(discord_id=curator.id).first()
            if not cur:
                cur = User(discord_id=curator.id, call_sign=curator.display_name)
                db.add(cur); db.flush()

            # 3) Привязываем
            user.curator_id = cur.id
            db.commit()

            em = self._make_embed(
                title="✅ Куратор назначен",
                description=f"{curator.mention} теперь куратор для {member.mention}."
            )
            await interaction.followup.send(embed=em)
        except SQLAlchemyError:
            db.rollback()
            logging.exception("Ошибка при назначении куратора")
            em = self._make_embed(
                title="❗ Ошибка",
                description="Не удалось сохранить куратора в базе.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=em, ephemeral=True)
        finally:
            db.close()

    @assigncurator.error
    async def assigncurator_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_CURATOR_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            em.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            await interaction.response.send_message(embed=em, ephemeral=True)
        else:
            logging.exception("Ошибка в assigncurator")
            await interaction.response.send_message(
                "❗ Произошла непредвиденная ошибка.", ephemeral=True
            )

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="removecurator",
        description="Удалить куратора"
    )
    @app_commands.describe(
        member="Пользователь, у которого удаляем куратора"
    )
    @app_commands.checks.has_any_role(*ALLOWED_CURATOR_ROLES)
    async def removecurator(
        self,
        interaction: discord.Interaction,
        member: discord.Member
    ):
        """Удаляет у member назначенного куратора."""
        await interaction.response.defer(thinking=True)
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if not user or user.curator_id is None:
                em = self._make_embed(
                    title="ℹ️ Куратор не найден",
                    description=f"У {member.mention} куратор не назначен.",
                    color=discord.Color.orange()
                )
            else:
                user.curator_id = None
                db.commit()
                em = self._make_embed(
                    title="✅ Куратор удалён",
                    description=f"Куратор для {member.mention} успешно удалён."
                )
            await interaction.followup.send(embed=em)
        except SQLAlchemyError:
            db.rollback()
            logging.exception("Ошибка при удалении куратора")
            em = self._make_embed(
                title="❗ Ошибка",
                description="Не удалось удалить куратора из базы.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=em, ephemeral=True)
        finally:
            db.close()

    @removecurator.error
    async def removecurator_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_CURATOR_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            em.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            await interaction.response.send_message(embed=em, ephemeral=True)
        else:
            logging.exception("Ошибка в removecurator")
            await interaction.response.send_message(
                "❗ Произошла непредвиденная ошибка.", ephemeral=True
            )

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="whoiscurator",
        description="Узнать куратора пользователя"
    )
    @app_commands.describe(
        member="Пользователь (по умолчанию — вы)"
    )
    @app_commands.checks.has_any_role(*ALLOWED_CURATOR_ROLES)
    async def whoiscurator(
        self,
        interaction: discord.Interaction,
        member: discord.Member = None
    ):
        """Показывает текущего куратора для указанного пользователя."""
        if member is None:
            member = interaction.user  # type: ignore

        await interaction.response.defer(thinking=True)
        db = next(get_db())
        try:
            user = db.query(User).filter_by(discord_id=member.id).first()
            if user and user.curator_id:
                curator_rec = db.query(User).get(user.curator_id)
                if curator_rec:
                    cm = interaction.guild.get_member(curator_rec.discord_id) if interaction.guild else None
                    mention = cm.mention if cm else f"<@{curator_rec.discord_id}>"
                    desc = f"🔹 Куратор для {member.mention}: {mention}"
                else:
                    desc = f"ℹ️ Куратор для {member.mention} не найден в гильдии."
            else:
                desc = f"ℹ️ Для {member.mention} куратор не назначен."
            em = self._make_embed(
                title="ℹ️ Информация о кураторе",
                description=desc,
                color=discord.Color.blue()
            )
            await interaction.followup.send(embed=em)
        except SQLAlchemyError:
            logging.exception("Ошибка при получении информации о кураторе")
            em = self._make_embed(
                title="❗ Ошибка",
                description="Не удалось получить данные из базы.",
                color=discord.Color.red()
            )
            await interaction.followup.send(embed=em, ephemeral=True)
        finally:
            db.close()

    @whoiscurator.error
    async def whoiscurator_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_CURATOR_ROLES)
            em = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            em.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            em.set_thumbnail(url=config.EMBLEM_URL)
            await interaction.response.send_message(embed=em, ephemeral=True)
        else:
            logging.exception("Ошибка в whoiscurator")
            await interaction.response.send_message(
                "❗ Произошла непредвиденная ошибка.", ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(CuratorCog(bot))
