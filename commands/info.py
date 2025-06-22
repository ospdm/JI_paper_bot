# commands/info.py

import datetime
import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import func
from sqlalchemy.exc import SQLAlchemyError

import config  # DEVELOPMENT_GUILD_ID и EMBLEM_URL прописаны в config.py
from database import (
    get_db,
    User,
    RPEntry,
    ActivityReport,
    InterrogationReport,
    Warning,
    Vacation,
)
from roles.constants import (
    arc_id, lrc_gimel_id, lrc_id,
    mjr_gimel_id, mjr_id, cpt_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id,
    senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    curator_id, worker_office_id, master_office_id,
    POST_MAP, CORPS_MAP,
)

# ID вашей тестовой гильдии
DEVELOPMENT_GUILD_ID = config.DEVELOPMENT_GUILD_ID

# Список ролей, которым разрешён /info
ALLOWED_ISSUER_ROLES = [
    arc_id, lrc_gimel_id, lrc_id,
    mjr_gimel_id, mjr_id, cpt_id,
    head_ji_id, adjutant_ji_id,
    leader_office_id, leader_penal_battalion_id, senate_id,
    director_office_id, leader_main_corps_id, leader_gimel_id,
    curator_id, worker_office_id, master_office_id,
]

# Публичный URL вашей GIF-анимации
GIF_URL = (
    "https://cdn.discordapp.com/attachments/1384127668391510070/1385679853310709870/ezgif-4e2ad6939c4e6f.gif?ex=6856f26d&is=6855a0ed&hm=1625a22d725fe8e02528fe66921df7f79387c3c1b46cdb1456aa64a69be9e748&"
)


class InfoCog(commands.Cog):
    """
    • /info @user  — публичную информацию о любом пользователе
    • /myinfo      — личную информацию о себе (ephemeral)
    """
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _gather_info(self, member: discord.Member):
        today = datetime.date.today()
        week_start = today - datetime.timedelta(days=today.weekday())
        week_end = week_start + datetime.timedelta(days=6)

        db = next(get_db())
        try:
            db_user = db.query(User).filter_by(discord_id=member.id).first()

            total_points = (
                db.query(func.coalesce(func.sum(RPEntry.amount), 0))
                  .filter(RPEntry.user_id == (db_user.id if db_user else None))
                  .scalar()
                or 0
            )

            vac_rec = None
            if db_user:
                vac_rec = (
                    db.query(Vacation)
                      .filter(Vacation.user_id == db_user.id, Vacation.active == True)
                      .order_by(Vacation.end_at.desc())
                      .first()
                )
            vac_status = "В отпуске" if vac_rec else "Не в отпуске"

            warn_rec = (
                db.query(func.coalesce(func.max(Warning.level), 0))
                  .filter(Warning.user_id == (db_user.id if db_user else None))
                  .scalar()
                or 0
            )

            black_status = "Да" if (db_user and db_user.black_mark) else "Нет"

            rank = "Нет"
            for rid, title in [
                (arc_id,       "Полковник"),
                (lrc_gimel_id, "Подполковник GIMEL"),
                (lrc_id,       "Подполковник"),
                (mjr_gimel_id, "Майор GIMEL"),
                (mjr_id,       "Майор"),
                (cpt_id,       "Капитан"),
            ]:
                role_obj = member.guild.get_role(rid)
                if role_obj and role_obj in member.roles:
                    rank = title
                    break

            steamid = db_user.steam_id if (db_user and db_user.steam_id) else "Не привязан"

            if db_user and db_user.curator_id:
                curator_db = db.query(User).get(db_user.curator_id)
                if curator_db:
                    cm = member.guild.get_member(curator_db.discord_id)
                    curator = cm.mention if cm else f"<@{curator_db.discord_id}>"
                else:
                    curator = "Не назначен"
            else:
                curator = "Не назначен"

            total_duties = (
                db.query(func.coalesce(func.sum(ActivityReport.duties), 0))
                  .filter(ActivityReport.user_id == (db_user.id if db_user else None))
                  .scalar()
                or 0
            )
            total_interviews = (
                db.query(func.count(InterrogationReport.id))
                  .filter(InterrogationReport.user_id == (db_user.id if db_user else None))
                  .scalar()
                or 0
            )

            weekly_duties = (
                db.query(func.coalesce(func.sum(ActivityReport.duties), 0))
                  .filter(
                      ActivityReport.user_id == (db_user.id if db_user else None),
                      ActivityReport.date.between(week_start, week_end)
                  )
                  .scalar()
                or 0
            )
            weekly_interviews = (
                db.query(func.count(InterrogationReport.id))
                  .filter(
                      InterrogationReport.user_id == (db_user.id if db_user else None),
                      InterrogationReport.date.between(week_start, week_end)
                  )
                  .scalar()
                or 0
            )

            positions = [
                member.guild.get_role(rid).name
                for _, rid in POST_MAP.items()
                if (r := member.guild.get_role(rid)) and r in member.roles
            ]
            corps = [
                member.guild.get_role(rid).name
                for _, rid in CORPS_MAP.items()
                if (r := member.guild.get_role(rid)) and r in member.roles
            ]

            return {
                "member": member,
                "total_points": total_points,
                "vac_status": vac_status,
                "warn_rec": warn_rec,
                "black_status": black_status,
                "rank": rank,
                "position": ", ".join(positions) or "Нет",
                "corps": ", ".join(corps) or "Не назначен",
                "id": member.id,
                "steamid": steamid,
                "curator": curator,
                "total_duties": total_duties,
                "total_interviews": total_interviews,
                "weekly_duties": weekly_duties,
                "weekly_interviews": weekly_interviews,
                "week_start": week_start,
                "week_end": week_end,
            }

        except SQLAlchemyError:
            logging.exception("Ошибка в _gather_info")
            return None
        finally:
            db.close()

    @app_commands.guilds(discord.Object(id=DEVELOPMENT_GUILD_ID))
    @app_commands.command(name="info", description="Показать информацию о пользователе")
    @app_commands.describe(member="Пользователь")
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_info(self, interaction: discord.Interaction, member: discord.Member):
        data = await self._gather_info(member)
        if data is None:
            return await interaction.response.send_message(
                "❗ Ошибка при чтении базы.", ephemeral=True
            )

        em = discord.Embed(
            title="Judgement Investigation",
            description=f"Статистика пользователя {member.mention}",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        # теперь берём эмблему из config
        em.set_thumbnail(url=config.EMBLEM_URL)

        em.add_field(name="✅ Баллы",         value=str(data["total_points"]),    inline=True)
        em.add_field(name="🏖️ Отпуск",       value=data["vac_status"],           inline=True)
        em.add_field(name="⚠️ Выговоры",     value=f"{data['warn_rec']}/3",       inline=True)
        em.add_field(name="⚫ Черная метка", value=data["black_status"],         inline=True)
        em.add_field(name="🎖️ Звание",       value=data["rank"],                 inline=True)
        em.add_field(name="✏️ Должность",    value=data["position"],             inline=True)
        em.add_field(name="🏛️ Корпус",       value=data["corps"],                inline=True)
        em.add_field(name="🆔 ID",            value=str(data["id"]),              inline=True)
        em.add_field(name="🔗 SteamID",      value=data["steamid"],              inline=True)
        em.add_field(name="🕵 Куратор",      value=data["curator"],              inline=True)

        em.add_field(name="\u200b", value="**Отчетность за всё время:**", inline=False)
        em.add_field(name="• Дежурств",   value=str(data["total_duties"]),    inline=True)
        em.add_field(name="• Допросов",   value=str(data["total_interviews"]),inline=True)

        em.add_field(
            name="\u200b",
            value=f"**За {data['week_start']:%d.%m.%Y}–{data['week_end']:%d.%m.%Y}:**",
            inline=False
        )
        em.add_field(name="• Дежурств",   value=str(data["weekly_duties"]),   inline=True)
        em.add_field(name="• Допросов",   value=str(data["weekly_interviews"]),inline=True)

        # GIF внизу
        em.set_image(url=GIF_URL)

        await interaction.response.send_message(embed=em)

    @slash_info.error
    async def slash_info_error(self, interaction: discord.Interaction, error):
        if isinstance(error, app_commands.MissingAnyRole):
            allowed = " ".join(f"<@&{rid}>" for rid in ALLOWED_ISSUER_ROLES)
            err = discord.Embed(
                title="❌ Доступ запрещён",
                description="Вы не имеете доступа к этой команде.",
                color=discord.Color.red()
            )
            err.add_field(
                name="Доступ имеют следующие роли:",
                value=allowed or "—",
                inline=False
            )
            return await interaction.response.send_message(embed=err, ephemeral=True)

        logging.exception("Ошибка в slash_info")
        if not interaction.response.is_done():
            await interaction.response.send_message("❗ Произошла ошибка.", ephemeral=True)
        else:
            await interaction.followup.send("❗ Произошла ошибка.", ephemeral=True)

    @app_commands.guilds(discord.Object(id=DEVELOPMENT_GUILD_ID))
    @app_commands.command(name="myinfo", description="Показать информацию о себе")
    async def slash_myinfo(self, interaction: discord.Interaction):
        data = await self._gather_info(interaction.user)  # type: ignore
        if data is None:
            return await interaction.response.send_message(
                "❗ Ошибка при чтении базы.", ephemeral=True
            )

        em = discord.Embed(
            title="Judgement Investigation\n  Личная статистика",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)

        em.add_field(name="✅ Баллы",         value=str(data["total_points"]),    inline=True)
        em.add_field(name="🏖️ Отпуск",       value=data["vac_status"],           inline=True)
        em.add_field(name="⚠️ Выговоры",     value=f"{data['warn_rec']}/3",       inline=True)
        em.add_field(name="⚫ Черная метка", value=data["black_status"],         inline=True)
        em.add_field(name="🎖️ Звание",       value=data["rank"],                 inline=True)
        em.add_field(name="✏️ Должность",    value=data["position"],             inline=True)
        em.add_field(name="🏛️ Корпус",       value=data["corps"],                inline=True)
        em.add_field(name="🆔 ID",            value=str(data["id"]),              inline=True)
        em.add_field(name="🔗 SteamID",      value=data["steamid"],              inline=True)
        em.add_field(name="🕵 Куратор",      value=data["curator"],              inline=True)
        em.add_field(name="\u200b", value="**Отчетность за всё время:**", inline=False)
        em.add_field(name="• Дежурств",   value=str(data["total_duties"]),    inline=True)
        em.add_field(name="• Допросов",   value=str(data["total_interviews"]),inline=True)

        em.add_field(
            name="\u200b",
            value=f"**За {data['week_start']:%d.%m.%Y}–{data['week_end']:%d.%m.%Y}:**",
            inline=False
        )
        em.add_field(name="• Дежурств",   value=str(data["weekly_duties"]),   inline=True)
        em.add_field(name="• Допросов",   value=str(data["weekly_interviews"]),inline=True)

        # GIF внизу
        em.set_image(url=GIF_URL)

        await interaction.response.send_message(embed=em, ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(InfoCog(bot))
