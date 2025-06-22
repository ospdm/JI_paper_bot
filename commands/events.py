# commands/events.py

import logging
import datetime
import re

import discord
from discord.ext import commands
from discord.utils import get
from sqlalchemy import func

import config  # DEVELOPMENT_GUILD_ID, EMBLEM_URL
from database import SessionLocal, User, ActivityReport, InterrogationReport
from roles.constants import CHANNELS

class Events(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.call_sign_to_thread: dict[str, tuple[discord.Thread, datetime.date]] = {}
        self.thread_to_activity: dict[int, int] = {}
        self.thread_to_interrogation: dict[int, int] = {}
        self.EMOJI_OK: discord.Emoji | None = None
        self.EMOJI_FAIL: discord.Emoji | None = None

    async def on_ready(self):
        # Загрузка эмодзи и участников
        if not self.bot.guilds:
            print("Warning: бот не состоит ни в одной гильдии.")
            return
        guild0 = self.bot.guilds[0]
        self.EMOJI_OK = get(guild0.emojis, name="Odobreno")
        self.EMOJI_FAIL = get(guild0.emojis, name="Otkazano")
        print(f"Бот запущен как {self.bot.user}. OK={self.EMOJI_OK}, FAIL={self.EMOJI_FAIL}")

        for guild in self.bot.guilds:
            cnt = 0
            async for m in guild.fetch_members(limit=None):
                cnt += 1
            print(f"Загружено {cnt} участников из гильдии «{guild.name}»")
        print("Участники загружены, теперь role.members будет непустым.")

    def _make_embed(self, description: str) -> discord.Embed:
        """Утилита: белый Embed с эмблемой."""
        em = discord.Embed(
            description=description,
            color=discord.Color.from_rgb(255, 255, 255),
            timestamp=datetime.datetime.utcnow()
        )
        em.set_thumbnail(url=config.EMBLEM_URL)
        return em

    def parse_activity_report(self, text: str) -> tuple[str, int, datetime.date] | None:
        parts = text.split('[Ваш позывной]')
        if len(parts) < 2:
            return None
        call_sign = next(
            (l.strip() for l in parts[1].splitlines()
             if l.strip() and not l.strip().startswith('Идентификационный номер')),
            None
        )
        if not call_sign:
            return None

        parts = text.split('[Количество Активных Дежурств в течении Недели]')
        if len(parts) < 2:
            return None
        duties = next(
            (int(l.strip()) for l in parts[1].splitlines() if l.strip().isdigit()),
            None
        )
        if duties is None:
            return None

        date = None
        parts = text.split('[Дата заполнения]')
        if len(parts) > 1:
            for l in parts[1].splitlines():
                s = l.strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                    try:
                        date = datetime.datetime.strptime(s, '%Y-%m-%d').date()
                        break
                    except Exception:
                        pass
        if date is None:
            return None
        return call_sign, duties, date

    def parse_interrogation_report(self, text: str) -> tuple[str, datetime.date] | None:
        parts = text.split('[Ваш позывной]')
        if len(parts) < 2:
            return None
        call_sign = next(
            (l.strip() for l in parts[1].splitlines()
             if l.strip() and not l.strip().startswith('Идентификационный номер')),
            None
        )
        if not call_sign:
            return None

        date = None
        parts = text.split('[Дата]')
        if len(parts) > 1:
            for l in parts[1].splitlines():
                s = l.strip()
                if re.fullmatch(r"\d{4}-\d{2}-\d{2}", s):
                    try:
                        date = datetime.datetime.strptime(s, '%Y-%m-%d').date()
                        break
                    except Exception:
                        pass
        if date is None:
            return None
        return call_sign, date

    async def resolve_member_by_callsign(
        self,
        guild: discord.Guild,
        call_sign: str
    ) -> discord.Member | None:
        key = call_sign.lower()
        for m in guild.members:
            if (m.display_name and m.display_name.lower() == key) \
            or (m.name and m.name.lower() == key):
                return m
        return None

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message):
        logging.info(f"[Events] on_message: {message.channel.id} from {message.author}")
        if message.author.id == self.bot.user.id:
            return

        # собираем текст из embed'ов
        raw = message.content or ""
        if message.embeds:
            e = message.embeds[0]
            if e.description:
                raw += "\n" + e.description
            for f in e.fields:
                raw += f"\n{f.name}\n{f.value}"

        db = SessionLocal()
        guild = message.guild
        try:
            # — Активность —
            if guild and message.channel.id == CHANNELS['activity']:
                parsed = self.parse_activity_report(raw)
                logging.info(f"[Events] parsed activity: {parsed}")
                if parsed:
                    call_sign, duties, date = parsed
                    member = await self.resolve_member_by_callsign(guild, call_sign) or message.author

                    # User в БД
                    db_user = db.query(User).filter_by(discord_id=member.id).first()
                    if not db_user:
                        db_user = User(discord_id=member.id, call_sign=call_sign)
                        db.add(db_user); db.commit()
                    elif db_user.call_sign != call_sign:
                        db_user.call_sign = call_sign; db.commit()

                    week_start = date - datetime.timedelta(days=date.weekday())
                    week_end = week_start + datetime.timedelta(days=6)
                    interviews = (
                        db.query(func.count(InterrogationReport.id))
                          .filter(
                              InterrogationReport.user_id == db_user.id,
                              InterrogationReport.date.between(week_start, week_end)
                          )
                          .scalar() or 0
                    )

                    ar = ActivityReport(
                        user_id=db_user.id,
                        duties=duties,
                        interviews=interviews,
                        date=date
                    )
                    db.add(ar); db.commit()

                    # создаём тред
                    try:
                        thread = await message.create_thread(
                            name=f"Оценка {call_sign}", auto_archive_duration=1440
                        )
                        self.call_sign_to_thread[call_sign] = (thread, date)
                        self.thread_to_activity[thread.id] = ar.id

                        ok = (duties >= 3 and interviews >= 1)
                        emoji = "✅" if ok else "❌"

                        # первый embed: упоминание пользователя + результат
                        em1 = self._make_embed(f"{member.mention} {emoji}")
                        await thread.send(embed=em1)

                        # второй embed: детальная сводка с упоминанием
                        desc = (
                            f"{emoji} Недельная норма для {member.mention} "
                            f"{'выполнена' if ok else 'не выполнена'}.\n"
                            f"• Дежурств – {duties}\n"
                            f"• Допросов – {interviews}"
                        )
                        em2 = self._make_embed(desc)
                        await thread.send(embed=em2)

                    except Exception as e:
                        logging.exception(f"Error thread activity: {e}")

            # — Допрос —
            elif guild and message.channel.id == CHANNELS['interrogation']:
                parsed = self.parse_interrogation_report(raw)
                logging.info(f"[Events] parsed interrogation: {parsed}")
                if parsed:
                    call_sign, d_date = parsed
                    member = await self.resolve_member_by_callsign(guild, call_sign) or message.author

                    db_user = db.query(User).filter_by(discord_id=member.id).first()
                    if not db_user:
                        db_user = User(discord_id=member.id, call_sign=call_sign)
                        db.add(db_user); db.commit()
                    elif db_user.call_sign != call_sign:
                        db_user.call_sign = call_sign; db.commit()

                    ir = InterrogationReport(user_id=db_user.id, date=d_date)
                    db.add(ir); db.commit()

                    # создаём тред допроса
                    try:
                        thr = await message.create_thread(
                            name=f"Допрос {call_sign}", auto_archive_duration=1440
                        )
                        self.thread_to_interrogation[thr.id] = ir.id

                        # embed 1: учли допрос с упоминанием
                        em3 = self._make_embed(f"✅ Учёл отчёт допроса для {member.mention}")
                        await thr.send(embed=em3)
                    except Exception as e:
                        logging.exception(f"Error thread interrogation: {e}")

                    # если был тред по активности — обновляем его
                    if call_sign in self.call_sign_to_thread:
                        act_thr, _ = self.call_sign_to_thread[call_sign]
                        ar_id = self.thread_to_activity.get(act_thr.id)
                        if ar_id:
                            ar = db.get(ActivityReport, ar_id)
                            if ar:
                                ar.interviews += 1
                                db.commit()
                                ok = (ar.duties >= 3 and ar.interviews >= 1)
                                emoji = "✅" if ok else "❌"

                                try:
                                    # embed 2: отметка в исходном треде с упоминанием
                                    em4 = self._make_embed(f"✅ Учёл отчёт допроса для {member.mention}")
                                    await act_thr.send(embed=em4)
                                    # embed 3: текущий статус с упоминанием
                                    status_desc = (
                                        f"{emoji} Текущий статус по норме для {member.mention}:\n"
                                        f"• Дежурств – {ar.duties}\n"
                                        f"• Допросов – {ar.interviews}"
                                    )
                                    em5 = self._make_embed(status_desc)
                                    await act_thr.send(embed=em5)
                                except Exception:
                                    pass

        finally:
            db.close()

async def setup(bot: commands.Bot):
    await bot.add_cog(Events(bot))
