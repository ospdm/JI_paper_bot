# commands/addrp.py

import datetime
import logging
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy import func

import discord
from discord import app_commands
from discord.ext import commands

from database import get_db, User, RPEntry
import config  # DEVELOPMENT_GUILD_ID и EMBLEM_URL в config.py
from roles.constants import (
    head_ji_id,
    adjutant_ji_id,
    leader_office_id,
    leader_penal_battalion_id,
    senate_id,
    head_curator_id,
    director_office_id,
    arc_id,
    lrc_gimel_id,
    lrc_id,
)

# Роли, которым разрешено вызывать /addrp и /removerp
ALLOWED_ISSUER_ROLES = [
    head_ji_id,
    adjutant_ji_id,
    leader_office_id,
    leader_penal_battalion_id,
    senate_id,
    head_curator_id,
    director_office_id,
    arc_id,
    lrc_gimel_id,
    lrc_id,
]

class RPCommands(commands.Cog):
    """Cog для выдачи и списания RP через слэш-команды /addrp и /removerp"""

    def __init__(self, bot: commands.Bot):
        self.bot = bot

    async def _apply_rp(
        self,
        actor: discord.User,
        member: discord.Member,
        amount: int,
        reason: str
    ) -> discord.Embed | None:
        """
        amount > 0: добавить,
        amount < 0: списать.
        """
        if amount == 0:
            return None

        db = next(get_db())
        try:
            # получаем или создаём пользователя
            user = db.query(User).filter_by(discord_id=member.id).first()
            if not user:
                user = User(discord_id=member.id)
                db.add(user)
                db.flush()

            # получаем или создаём issuer
            issuer = db.query(User).filter_by(discord_id=actor.id).first()
            if not issuer:
                issuer = User(discord_id=actor.id)
                db.add(issuer)
                db.flush()

            # создаём запись RPEntry
            entry = RPEntry(
                user_id=user.id,
                amount=amount,
                issued_by=issuer.id,
                reason=reason
            )
            db.add(entry)
            db.commit()

            # считаем новый баланс
            total_points = (
                db.query(func.coalesce(func.sum(RPEntry.amount), 0))
                  .filter(RPEntry.user_id == user.id)
                  .scalar()
                or 0
            )
        except SQLAlchemyError:
            db.rollback()
            logging.exception("Ошибка при записи RP в базу")
            return None
        finally:
            db.close()

        # строим Embed
        action = "➕ Выдано" if amount > 0 else "➖ Списано"
        em = discord.Embed(
            title="Judgement Investigation — Обновление RP-поинтов",
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        em.add_field(name="👤 Пользователь",     value=member.mention, inline=True)
        em.add_field(name="💠 Исполнитель",      value=actor.mention, inline=True)
        em.add_field(name=f"{action} RP-поинтов", value=str(abs(amount)), inline=True)
        em.add_field(name="📝 Причина",          value=reason, inline=False)
        em.add_field(name="🏅 Всего RP-поинтов",    value=str(total_points), inline=True)
        em.set_footer(
            text="— Всегда на страже ваших заслуг",
            icon_url=config.EMBLEM_URL
        )
        return em

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="addrp",
        description="Выдать RP пользователю"
    )
    @app_commands.describe(
        member="Пользователь, которому выдаём RP",
        amount="Количество очков (>0)",
        reason="Причина"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_addrp(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
        reason: str
    ):
        if amount <= 0:
            return await interaction.response.send_message(
                "❗ Для выдачи RP используйте положительное число.", ephemeral=True
            )

        await interaction.response.defer(thinking=True)
        embed = await self._apply_rp(
            actor=interaction.user,
            member=member,
            amount=amount,
            reason=reason
        )
        if embed is None:
            return await interaction.followup.send(
                "❗ Не удалось выдать RP. Проверьте логи.", ephemeral=True
            )
        await interaction.followup.send(embed=embed)

    @app_commands.guilds(discord.Object(id=config.DEVELOPMENT_GUILD_ID))
    @app_commands.command(
        name="removerp",
        description="Списать RP у пользователя"
    )
    @app_commands.describe(
        member="Пользователь, у которого списываем RP",
        amount="Количество очков (>0)",
        reason="Причина списания"
    )
    @app_commands.checks.has_any_role(*ALLOWED_ISSUER_ROLES)
    async def slash_removerp(
        self,
        interaction: discord.Interaction,
        member: discord.Member,
        amount: int,
        reason: str
    ):
        if amount <= 0:
            return await interaction.response.send_message(
                "❗ Для списания RP используйте положительное число.", ephemeral=True
            )

        await interaction.response.defer(thinking=True)
        embed = await self._apply_rp(
            actor=interaction.user,
            member=member,
            amount=-amount,  # минус для списания
            reason=reason
        )
        if embed is None:
            return await interaction.followup.send(
                "❗ Не удалось списать RP. Проверьте логи.", ephemeral=True
            )
        await interaction.followup.send(embed=embed)

    @slash_addrp.error
    async def slash_addrp_error(self, interaction: discord.Interaction, error):
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

        logging.exception("Ошибка в slash_addrp/removerp")
        if interaction.response.is_done():
            await interaction.followup.send(
                "❗ Произошла ошибка при выполнении команды.", ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "❗ Произошла ошибка при выполнении команды.", ephemeral=True
            )

async def setup(bot: commands.Bot):
    await bot.add_cog(RPCommands(bot))
