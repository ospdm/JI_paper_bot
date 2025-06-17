import os
import re
import datetime
import logging
import asyncio
import discord
from discord.ext import commands
from discord.utils import get
from collections import defaultdict
from dotenv import load_dotenv
from typing import Optional, Tuple, Dict, List
from discord import app_commands

# ─────────────────── Настройка логирования ───────────────────
logging.basicConfig(level=logging.INFO)

# ─────────────────── Загрузка токена ───────────────────
load_dotenv(dotenv_path="token.env")
TOKEN = os.getenv('DISCORD_TOKEN')
if not TOKEN:
    raise RuntimeError("Не задан DISCORD_TOKEN в окружении")

# ─────────────────── Константы ───────────────────
CHANNELS = {
    'activity': 1384128582263111740,
    'interrogation': 1384128486268076032,
}

# Роли
lrc_id      = 1384128791558750280  # подполковник
mjr_id      = 1384128791474868326  # майор
cpt_id      = 1384205899224318082  # капитан
slt_id      = 1384206003985317898  # старший лейтенант
lt_id       = 1384206159036026943  # лейтенант
jlt_id      = 1384206140707180695  # младший лейтенант
ji_id       = 1384128750790119424  # основной штат
gimel_id    = 1384206551262171216  # гимель
vacation_id = 1384128722613043212  # отпуск



# В начало файла, после определения ID ролей:
ROLE_MAP = {
    'lrc':      lrc_id,      # подполковник
    'mjr':      mjr_id,      # майор
    'cpt':      cpt_id,      # капитан
    'slt':      slt_id,      # старший лейтенант
    'lt':       lt_id,       # лейтенант
    'jlt':      jlt_id,      # младший лейтенант
    'ji':       ji_id,       # основной штат
    'gimel':    gimel_id,    # гимель
    'vacation': vacation_id, # отпуск
}

# WARN-роли
f_warn_id = 1384543038533275738  # WARN 1/3
s_warn_id = 1384543092769554442  # WARN 2/3
t_warn_id = 1384543134142431232  # WARN 3/3
black_mark_id = 1384543181541998722  # черная метка

WARN_ROLE_IDS = {
    1: f_warn_id,
    2: s_warn_id,
    3: t_warn_id,
}

# Роли для подсчёта отчётности
REPORT_ROLE_IDS = [mjr_id, cpt_id, slt_id, lt_id, ji_id]

intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='/', intents=intents)

# ─────────────────── Глобальные эмодзи ───────────────────
EMOJI_OK: discord.Emoji = ":Odobreno:"
EMOJI_FAIL: discord.Emoji = ":Otkazano:"

# ─────────────────── Хранилище данных ───────────────────
activity_reports: list[Tuple[str, int, datetime.date]] = []
interrogation_reports: list[Tuple[str, datetime.date]] = []
call_sign_to_thread: Dict[str, Tuple[discord.Thread, datetime.date]] = {}
curator_map: Dict[int, int] = {}  # map user_id -> curator_id
steam_map: Dict[int, str] = {}  # discord_user_id -> steamid
thread_to_activity: Dict[int, Tuple[str, int, datetime.date]] = {}
thread_to_interrogation: Dict[int, Tuple[str, datetime.date]] = {}
# user_id → общее кол-во очков
rp_points: Dict[int, int] = defaultdict(int)
# user_id → список выданных записей: (issuer_id, amount, reason)
rp_reasons: Dict[int, List[Tuple[int, int, str]]] = defaultdict(list)
# ─────────────────── Парсеры ───────────────────
def parse_activity_report(text: str) -> Optional[Tuple[str,int,datetime.date]]:
    parts = text.split('[Ваш позывной]')
    if len(parts) < 2:
        return None
    call_sign = next(
        (line.strip() for line in parts[1].splitlines()
         if line.strip() and not line.strip().startswith('Идентификационный номер')),
        None
    )
    if not call_sign:
        return None

    parts = text.split('[Количество Активных Дежурств в течении Недели]')
    if len(parts) < 2:
        return None
    duties = next(
        (int(line.strip()) for line in parts[1].splitlines() if line.strip().isdigit()),
        0
    )

    date = None
    parts = text.split('[Дата заполнения]')
    if len(parts) > 1:
        for line in parts[1].splitlines():
            s = line.strip()
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
                date = datetime.datetime.strptime(s, '%Y-%m-%d').date()
                break
    if date is None:
        return None

    return call_sign, duties, date

def parse_interrogation_report(text: str) -> Optional[Tuple[str,datetime.date]]:
    parts = text.split('[Ваш позывной]')
    if len(parts) < 2:
        return None
    call_sign = next(
        (line.strip() for line in parts[1].splitlines() if line.strip() and line.strip() != '*'),
        None
    )
    if not call_sign:
        return None

    date = None
    parts = text.split('[Дата]')
    if len(parts) > 1:
        for line in parts[1].splitlines():
            s = line.strip()
            if re.fullmatch(r'\d{4}-\d{2}-\d{2}', s):
                date = datetime.datetime.strptime(s, '%Y-%m-%d').date()
                break
    if date is None:
        return None

    return call_sign, date

# ─────────────────── UI для выбора периода в !results ───────────────────
class PeriodSelect(discord.ui.Select):
    def __init__(self):
        options = [
            discord.SelectOption(label="Текущая неделя", value="current"),
            discord.SelectOption(label="Прошлая неделя", value="last"),
        ]
        super().__init__(
            placeholder="Выберите период отчётов",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        today = datetime.date.today()
        monday = today - datetime.timedelta(days=today.weekday())
        if self.values[0] == "current":
            start, end = monday, monday + datetime.timedelta(days=6)
        else:
            start = monday - datetime.timedelta(days=7)
            end = monday - datetime.timedelta(days=1)

        stats = defaultdict(lambda: {'дежурства': 0, 'допросы': 0})
        for call, duties, date in activity_reports:
            if start <= date <= end:
                stats[call]['дежурства'] += duties
        for call, date in interrogation_reports:
            if start <= date <= end:
                stats[call]['допросы'] += 1

        lines = [f"**Результаты за период {start:%d.%m.%Y}–{end:%d.%m.%Y}:**"]
        if not stats:
            lines.append("Нет отчётов за этот период.")
        else:
            for call, s in stats.items():
                if s['допросы'] == 0:
                    lines.append(f"{call}: {EMOJI_FAIL} У тебя нет отчётов допросов.")
                else:
                    ok = s['дежурства'] >= 3 and s['допросы'] >= 1
                    lines.append(
                        f"{call}: дежурств {s['дежурства']}, допросов {s['допросы']} "
                        f"{EMOJI_OK if ok else EMOJI_FAIL}"
                    )

        await interaction.response.send_message("\n".join(lines))
        self.view.stop()

class PeriodView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)
        self.add_item(PeriodSelect())

# ─────────────────── Единый on_message ───────────────────

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    logging.info(f"Получено сообщение от {message.author} webhook_id={message.webhook_id} в канале {message.channel.id}")

    # Собираем «сырой» текст из content + первого Embed
    raw = message.content or ""
    if message.embeds:
        embed = message.embeds[0]
        if embed.description:
            raw += "\n" + embed.description
        for field in embed.fields:
            raw += f"\n{field.name}\n{field.value}"

    logging.info(f"Собранный текст для парсинга:\n{raw}")

    # Обработка отчёта активности
    if message.channel.id == CHANNELS['activity']:
        parsed = parse_activity_report(raw)
        logging.info(f"parse_activity_report -> {parsed!r}")
        if parsed:
            call, duties, date = parsed
            activity_reports.append((call, duties, date))

            week_start = date - datetime.timedelta(days=date.weekday())
            week_end   = week_start + datetime.timedelta(days=6)

            interviews = sum(
                1 for c, d in interrogation_reports
                if c == call and week_start <= d <= week_end
            )

            if interviews == 0:
                status_emoji = EMOJI_FAIL
                msg = f"{status_emoji} У тебя нет отчётов допросов."
            else:
                ok = (duties >= 3) and (interviews >= 1)
                status_emoji = EMOJI_OK if ok else EMOJI_FAIL
                msg = (
                    f"{status_emoji} Недельная норма {'выполнена' if ok else 'не выполнена'}.\n"
                    f"Дежурств – {duties}, Допросов – {interviews}"
                )

            try:
                thread = await message.create_thread(
                    name=f"Оценка {call}",
                    auto_archive_duration=1440
                )
                # сохраняем тред вместе с датой отчёта
                call_sign_to_thread[call] = (thread, date)
                # сохраняем данные отчёта для возможного отклонения
                thread_to_activity[thread.id] = (call, duties, date)
            except Exception as e:
                logging.exception(f"Не удалось создать тред для {call}")
                await message.channel.send(f"❗ Ошибка при создании треда: {e}")
            else:
                await thread.send(f"{call} {status_emoji}")
                await thread.send(msg)

    # Обработка отчёта допроса
    elif message.channel.id == CHANNELS['interrogation']:
        parsed = parse_interrogation_report(raw)
        logging.info(f"parse_interrogation_report -> {parsed!r}")
        if parsed:
            call, d_date = parsed
            interrogation_reports.append(parsed)

            try:
                thread = await message.create_thread(
                    name=f"Допрос {call}",
                    auto_archive_duration=1440
                )
                # сохраняем данные допроса для возможного отклонения
                thread_to_interrogation[thread.id] = (call, d_date)
            except Exception as e:
                logging.exception(f"Не удалось создать тред для допроса {call}")
                await message.channel.send(f"❗ Ошибка при создании треда допроса: {e}")
            else:
                await thread.send(f":white_check_mark: Учёл отчёт допроса для {call}")

    # Обработка команд
    await bot.process_commands(message)

# ─────────────────── Команда !results ───────────────────
@bot.command(name='results')
async def results(ctx):

    # 1) Собираем статистику по позывным (строкам) в нижнем регистре
    raw_stats = defaultdict(lambda: {'дежурства': 0, 'допросы': 0})
    for call, duties, _ in activity_reports:
        raw_stats[call.strip().lower()]['дежурства'] += duties
    for call, _ in interrogation_reports:
        raw_stats[call.strip().lower()]['допросы'] += 1

    guild = ctx.guild
    lines = ["**Недельная отчетность следующих ролей:**"]

    # 2) Проходим по целевым ролям
    for role_id in REPORT_ROLE_IDS:
        role = guild.get_role(role_id)
        if not role:
            continue
        lines.append(f"\n__{role.name}__")
        for member in role.members:
            # подготавливаем ключи для поиска
            candidates = []
            if member.display_name:
                candidates.append(member.display_name.lower())
            candidates.append(member.name.lower())

            # пробуем найти статистику
            st = {'дежурства': 0, 'допросы': 0}
            for cand in candidates:
                if cand in raw_stats:
                    st = raw_stats[cand]
                    break

            ok = st['дежурства'] >= 3 and st['допросы'] >= 1
            emoji = EMOJI_OK if ok else EMOJI_FAIL
            lines.append(
                f"{member.mention}: дежурств {st['дежурства']}, "
                f"допросов {st['допросы']} {emoji}"
            )

    # 3) Список отпускников
    vac_role = guild.get_role(vacation_id)
    if vac_role:
        lines.append("\n**Пользователи в отпуске:**")
        for member in vac_role.members:
            lines.append(f"{member.mention}")

    await ctx.send("\n".join(lines))

# ─────────────────── Погрузка эмодзи и участников сервера ───────────────────
@bot.event
async def on_ready():
    # Подгружаем кастом-эмодзи из первого сервера
    guild0 = bot.guilds[0]  # или bot.get_guild(ВАШ_ID_СЕРВЕРА)
    global EMOJI_OK, EMOJI_FAIL
    EMOJI_OK   = get(guild0.emojis, name="Odobreno")
    EMOJI_FAIL = get(guild0.emojis, name="Otkazano")
    print(f"Бот запущен как {bot.user}. OK={EMOJI_OK}, FAIL={EMOJI_FAIL}")

    # Принудительно загружаем всех членов (Server Members Intent должен быть включён!)
    for guild in bot.guilds:
        count = 0
        async for member in guild.fetch_members(limit=None):
            count += 1
        print(f"Загружено {count} участников из гильдии «{guild.name}»")

    print("Участники загружены, теперь role.members будет непустым.")

# ─────────────────── Команда !addrole ───────────────────

@bot.command(name='addrole')
@commands.has_permissions(manage_roles=True)
async def addrole(ctx, role_key: str, member: discord.Member=None):
    """
    Выдаёт указанную роль пользователю.
    Использование: !addrole <ключ_роли> [@пользователь]
    Ключи: lrc, mjr, cpt, slt, lt, jlt, ji, gimel, vacation
    Если пользователь не указан — выдаётся роль вам.
    """
    role_key = role_key.lower()
    if role_key not in ROLE_MAP:
        await ctx.send(f"❗ Неизвестный ключ роли `{role_key}`. Доступные: {', '.join(ROLE_MAP.keys())}")
        return

    if member is None:
        member = ctx.author

    role = ctx.guild.get_role(ROLE_MAP[role_key])
    if role is None:
        await ctx.send(f"❗ Роль для `{role_key}` не найдена на сервере.")
        return

    try:
        await member.add_roles(role, reason=f"Выдана роль {role.name} командой {ctx.author}")
        await ctx.send(f"✅ Роль **{role.name}** выдана пользователю {member.mention}.")
    except discord.Forbidden:
        await ctx.send("❗ У меня нет прав на управление этой ролью.")
    except Exception as e:
        logging.exception("Ошибка при выдаче роли")
        await ctx.send(f"❗ Не удалось выдать роль: {e}")

@bot.command(name='removerole')
@commands.has_permissions(manage_roles=True)
async def removerole(ctx, role_key: str, member: discord.Member=None):
    """
    Убирает указанную роль с пользователя.
    Использование: !removerole <ключ_роли> [@пользователь]
    """
    role_key = role_key.lower()
    if role_key not in ROLE_MAP:
        await ctx.send(f"❗ Неизвестный ключ роли `{role_key}`. Доступные: {', '.join(ROLE_MAP.keys())}")
        return

    if member is None:
        member = ctx.author

    role = ctx.guild.get_role(ROLE_MAP[role_key])
    if role is None:
        await ctx.send(f"❗ Роль для `{role_key}` не найдена на сервере.")
        return

    try:
        await member.remove_roles(role, reason=f"Убрана роль {role.name} командой {ctx.author}")
        await ctx.send(f"✅ Роль **{role.name}** убрана у пользователя {member.mention}.")
    except discord.Forbidden:
        await ctx.send("❗ У меня нет прав на управление этой ролью.")
    except Exception as e:
        logging.exception("Ошибка при удалении роли")
        await ctx.send(f"❗ Не удалось убрать роль: {e}")

import asyncio

# ─────────────────── Команда !temprole ───────────────────

@bot.command(name='tempaddrole')
@commands.has_permissions(manage_roles=True)
async def tempaddrole(ctx, role_key: str, duration: str, member: discord.Member = None):
    """
    Выдаёт роль на время.
    Использование: !tempaddrole <ключ_роли> <длительность> [@пользователь]
    Длительность: NdNhNm, например 1d2h30m или 45m
    """
    role_key = role_key.lower()
    if role_key not in ROLE_MAP:
        return await ctx.send(f"❗ Неизвестный ключ роли `{role_key}`. Доступные: {', '.join(ROLE_MAP.keys())}")

    if member is None:
        member = ctx.author

    # Парсим длительность
    m = re.fullmatch(r'(?:(?P<days>\d+)d)?(?:(?P<hours>\d+)h)?(?:(?P<minutes>\d+)m)?', duration)
    if not m:
        return await ctx.send("❗ Неверный формат длительности. Пример: `1d2h30m` или `45m`.")
    days    = int(m.group('days') or 0)
    hours   = int(m.group('hours') or 0)
    minutes = int(m.group('minutes') or 0)
    total_seconds = days*86400 + hours*3600 + minutes*60
    if total_seconds <= 0:
        return await ctx.send("❗ Длительность должна быть больше нуля.")

    role = ctx.guild.get_role(ROLE_MAP[role_key])
    if role is None:
        return await ctx.send(f"❗ Роль для `{role_key}` не найдена на сервере.")

    try:
        await member.add_roles(role, reason=f"Временная роль {duration} командой {ctx.author}")
        await ctx.send(f"✅ Роль **{role.name}** выдана {member.mention} на `{duration}`.")
    except discord.Forbidden:
        return await ctx.send("❗ У меня нет прав на управление этой ролью.")
    except Exception as e:
        logging.exception("Ошибка при выдаче временной роли")
        return await ctx.send(f"❗ Не удалось выдать роль: {e}")

    # Запускаем задачу для удаления роли после истечения срока
    async def remove_later():
        await asyncio.sleep(total_seconds)
        try:
            await member.remove_roles(role, reason=f"Истёк срок временной роли {duration}")
            await ctx.send(f"⌛ Время вышло: роль **{role.name}** снята с {member.mention}.")
        except Exception:
            logging.exception("Ошибка при снятии временной роли")

    bot.loop.create_task(remove_later())

# ─────────────────── Команда !warn ───────────────────

@bot.command(name='warn')
@commands.has_permissions(manage_roles=True)
async def warn(ctx, count: int, member: discord.Member):
    """
    Выдаёт WARN-роль пользователю.
    Использование: !warn <1|2|3> @пользователь
    """
    # Проверяем валидность
    if count < 1 or count > 3:
        return await ctx.send("❗ Неверное количество WARN'ов. Допустимые значения — 1, 2 или 3.")

    # Определяем нужную роль
    role_id = WARN_ROLE_IDS[count]
    role = ctx.guild.get_role(role_id)
    if role is None:
        return await ctx.send(f"❗ Роль WARN {count}/3 не найдена на сервере.")

    # Собираем все WARN-роли, которые есть у пользователя
    to_remove = []
    for rid in WARN_ROLE_IDS.values():
        r = ctx.guild.get_role(rid)
        if r and r in member.roles:
            to_remove.append(r)

    try:
        # Снимаем предыдущие WARN-роли
        if to_remove:
            await member.remove_roles(*to_remove, reason=f"Обновление WARN до {count}/3")
        # Выдаём новую
        await member.add_roles(role, reason=f"Выдан WARN {count}/3 командой {ctx.author}")
        await ctx.send(f"✅ {member.mention} теперь имеет роль **{role.name}**.")
    except discord.Forbidden:
        await ctx.send("❗ У меня нет прав на управление этими ролями.")
    except Exception as e:
        logging.exception("Ошибка при назначении WARN-ролей")
        await ctx.send(f"❗ Не удалось выдать WARN: {e}")

# ─────────────────── Команда !removewarn ───────────────────

@bot.command(name='removewarn')
@commands.has_permissions(manage_roles=True)
async def removewarn(ctx, count: int, member: discord.Member = None):
    """
    Снимает указанную WARN-роль у пользователя.
    Использование: !removewarn <1|2|3> [@пользователь]
    Если пользователь не указан — снимается у вас.
    """
    if count < 1 or count > 3:
        return await ctx.send("❗ Неверное количество WARN'ов. Допустимые значения — 1, 2 или 3.")
    if member is None:
        member = ctx.author

    role_id = WARN_ROLE_IDS[count]
    role = ctx.guild.get_role(role_id)
    if role is None:
        return await ctx.send(f"❗ Роль WARN {count}/3 не найдена на сервере.")

    if role not in member.roles:
        return await ctx.send(f"ℹ️ У {member.mention} нет роли **{role.name}**.")

    try:
        await member.remove_roles(role, reason=f"Снят WARN {count}/3 командой {ctx.author}")
        await ctx.send(f"✅ У {member.mention} снята роль **{role.name}**.")
    except discord.Forbidden:
        await ctx.send("❗ У меня нет прав на управление этой ролью.")
    except Exception as e:
        logging.exception("Ошибка при снятии WARN-ролей")
        await ctx.send(f"❗ Не удалось снять WARN: {e}")

# ─────────────────── Команда !vacation ───────────────────

@bot.command(name='vacation')
@commands.has_permissions(manage_roles=True)
async def vacation(ctx, member: discord.Member, duration: str):
    """
    Выдаёт отпускную роль на указанное время.
    Использование: !vacation @пользователь <XdYhZm>
    Где X – дни (д), Y – часы (ч), Z – минуты (м).
    Пример: !vacation @User 2д5ч или !vacation @User 3д или !vacation @User 4ч30м
    """
    # Парсим длительность в формате русских суффиксов
    m = re.fullmatch(
        r'(?:(?P<days>\d+)д)?(?:(?P<hours>\d+)ч)?(?:(?P<minutes>\d+)м)?',
        duration
    )
    if not m:
        return await ctx.send("❗ Неверный формат длительности. Пример: `2д5ч30м`, `3д`, `4ч` или `45м`.")

    days    = int(m.group('days') or 0)
    hours   = int(m.group('hours') or 0)
    minutes = int(m.group('minutes') or 0)
    total_seconds = days*86400 + hours*3600 + minutes*60

    if total_seconds <= 0:
        return await ctx.send("❗ Длительность должна быть больше нуля.")

    role = ctx.guild.get_role(vacation_id)
    if not role:
        return await ctx.send("❗ Роль отпуска не найдена на сервере.")

    try:
        await member.add_roles(role, reason=f"Отпуск на {duration} выдан командой {ctx.author}")
        await ctx.send(f"✅ Роль **{role.name}** выдана {member.mention} на `{duration}`.")
    except discord.Forbidden:
        return await ctx.send("❗ У меня нет прав на управление этой ролью.")
    except Exception as e:
        logging.exception("Ошибка выдачи роли отпуска")
        return await ctx.send(f"❗ Не удалось выдать роль отпуска: {e}")

    async def remove_vac():
        await asyncio.sleep(total_seconds)
        try:
            await member.remove_roles(role, reason="Истёк срок отпуска")
            await ctx.send(f"⌛ Время отпуска закончилось: роль **{role.name}** снята с {member.mention}.")
        except Exception:
            logging.exception("Ошибка снятия роли отпуска")

    bot.loop.create_task(remove_vac())

# ─────────────────── Команда !removevacation ───────────────────

@bot.command(name='removevacation')
@commands.has_permissions(manage_roles=True)
async def removevacation(ctx, member: discord.Member = None):
    """
    Снимает отпускную роль у пользователя.
    Использование: !removevacation [@пользователь]
    Если пользователь не указан — снимается у вас.
    """
    if member is None:
        member = ctx.author

    role = ctx.guild.get_role(vacation_id)
    if not role:
        return await ctx.send("❗ Роль отпуска не найдена на сервере.")

    if role not in member.roles:
        return await ctx.send(f"ℹ️ У {member.mention} нет роли **{role.name}**.")

    try:
        await member.remove_roles(role, reason=f"Снят отпуск командой {ctx.author}")
        await ctx.send(f"✅ Роль **{role.name}** снята у {member.mention}.")
    except discord.Forbidden:
        await ctx.send("❗ У меня нет прав на управление этой ролью.")
    except Exception as e:
        logging.exception("Ошибка при снятии роли отпуска")
        await ctx.send(f"❗ Не удалось снять роль отпуска: {e}")

# ─────────────────── Команда !assigncurator ───────────────────

@bot.command(name='assigncurator')
@commands.has_permissions(manage_roles=True)
async def assigncurator(ctx, member: discord.Member, curator: discord.Member):
    """
    Назначает куратора пользователю.
    Использование: !assigncurator @пользователь @куратор
    """
    curator_map[member.id] = curator.id
    await ctx.send(f"✅ {curator.mention} теперь куратор для {member.mention}.")

@bot.command(name='removecurator')
@commands.has_permissions(manage_roles=True)
async def removecurator(ctx, member: discord.Member):
    """
    Убирает назначенного куратора у пользователя.
    Использование: !removecurator @пользователь
    """
    if member.id in curator_map:
        del curator_map[member.id]
        await ctx.send(f"✅ Куратор для {member.mention} удалён.")
    else:
        await ctx.send(f"ℹ️ Для {member.mention} куратор не назначен.")

@bot.command(name='whoiscurator')
async def whoiscurator(ctx, member: discord.Member = None):
    """
    Показывает, кто куратор для указанного пользователя.
    Если пользователь не указан — показывает для вас.
    """
    if member is None:
        member = ctx.author
    curator_id = curator_map.get(member.id)
    if curator_id:
        curator = ctx.guild.get_member(curator_id)
        if curator:
            await ctx.send(f"🔹 Куратор для {member.mention}: {curator.mention}")
            return
    await ctx.send(f"ℹ️ Для {member.mention} куратор не назначен.")

# ─────────────────── Команда !bindsteam ───────────────────

@bot.command(name='bindsteam')
@commands.has_permissions(manage_roles=True)
async def bindsteam(ctx, steamid: str, member: discord.Member = None):
    """
    Привязывает SteamID к пользователю.
    Использование: !bindsteam <SteamID> [@пользователь]
    Формат SteamID: STEAM_X:Y:Z (например, STEAM_0:0:535566059)
    """
    if member is None:
        member = ctx.author

    # Проверяем формат SteamID
    if not re.fullmatch(r'STEAM_[0-5]:[01]:\d+', steamid):
        return await ctx.send("❗ Неверный формат SteamID. Ожидается STEAM_X:Y:Z, где X—0–5, Y—0 или 1, Z—число.")

    # Сохраняем привязку
    steam_map[member.id] = steamid
    await ctx.send(f"✅ SteamID `{steamid}` привязан к {member.mention}.")

# ─────────────────── Команда !steam ───────────────────

@bot.command(name='steamid')
async def steamid(ctx, member: discord.Member = None):
    """
    Показывает привязанный SteamID пользователя.
    Использование: !steamid [@пользователь]
    """
    if member is None:
        member = ctx.author

    sid = steam_map.get(member.id)
    if sid:
        await ctx.send(f"🔗 {member.mention} привязан SteamID: `{sid}`")
    else:
        await ctx.send(f"ℹ️ У {member.mention} нет привязанного SteamID.")

# ─────────────────── Команда !unbindsteam ───────────────────

@bot.command(name='unbindsteam')
@commands.has_permissions(manage_roles=True)
async def unbindsteam(ctx, member: discord.Member = None):
    """
    Убирает привязанный SteamID с пользователя.
    Использование: !unbindsteam [@пользователь]
    """
    if member is None:
        member = ctx.author

    if member.id in steam_map:
        del steam_map[member.id]
        await ctx.send(f"✅ SteamID отвязан от {member.mention}.")
    else:
        await ctx.send(f"ℹ️ У {member.mention} нет привязанного SteamID.")

# ─────────────────── Команда !denied ───────────────────

@bot.command(name='denied')
@commands.has_permissions(manage_messages=True)
async def denied(ctx, member: discord.Member):
    """
    Аннулирует отчёт, соответствующий текущему треду.
    Использование: !denied @пользователь
    """
    thread = ctx.channel
    # Только внутри треда
    if not isinstance(thread, discord.Thread):
        return await ctx.send("❗ Команду можно использовать только внутри треда отчёта.")

    # Проверяем, это тред активности?
    if thread.id in thread_to_activity:
        call, duties, date = thread_to_activity.pop(thread.id)
        # Удаляем конкретный отчёт из списка
        try:
            activity_reports.remove((call, duties, date))
        except ValueError:
            pass
        await thread.send(f"🚫 Отчёт активности для **{member.mention}** ({call}, {date}) аннулирован.")
        return

    # Или тред допроса?
    if thread.id in thread_to_interrogation:
        call, date = thread_to_interrogation.pop(thread.id)
        try:
            interrogation_reports.remove((call, date))
        except ValueError:
            pass
        await thread.send(f"🚫 Отчёт допроса для **{member.mention}** ({call}, {date}) аннулирован.")
        return

    # Иначе
    await ctx.send("❗ Это не тред отчёта, нечего аннулировать.")

# ─────────────────── Команда выдачи RP-очков ───────────────────
@bot.command(name='addrp')
@commands.has_role(lrc_id)
async def addrp(ctx, member: discord.Member, amount: int, *, reason: str):
    """
    Выдаёт RP-очки пользователю.
    Доступно только для роли подполковника (lrc).
    Использование: !addrp @пользователь <кол-во> <причина>
    """
    # Добавляем очки и сохраняем запись с причиной
    rp_points[member.id] += amount
    rp_reasons[member.id].append((ctx.author.id, amount, reason))

    total = rp_points[member.id]
    await ctx.send(
        f"✅ {ctx.author.mention} выдал {amount} RP {member.mention} за «{reason}».\n"
        f"💠 Всего RP-очков у {member.mention}: **{total}**"
    )

# ─────────────────── Команда /myinfo ───────────────────

@bot.command(name='myinfo')
async def myinfo(ctx):
    """
    Показывает информацию о вас.
    """
    member = ctx.author
    now = datetime.date.today()
    week_start = now - datetime.timedelta(days=now.weekday())
    week_end = week_start + datetime.timedelta(days=6)

    # Заголовок и ник
    header = "JI"
    nick = member.display_name

    # Баллы
    points = rp_points.get(member.id, 0)

    # Отпуск
    on_vacation = member.get_role(vacation_id) is not None
    vacation_status = "В отпуске" if on_vacation else "Не в отпуске"

    # Варны
    warn_count = 0
    for num, rid in WARN_ROLE_IDS.items():
        role = ctx.guild.get_role(rid)
        if role in member.roles:
            warn_count = num
    # Черная метка
    has_black = ctx.guild.get_role(black_mark_id) in member.roles
    black_status = "Да" if has_black else "Нет"

    # Звание (приоритетное)
    rank = None
    for rid, title in [
        (lrc_id, "Подполковник"),
        (mjr_id, "Майор"),
        (cpt_id, "Капитан"),
        (slt_id, "Ст. Лейт."),
        (lt_id, "Лейтенант"),
        (jlt_id, "Мл. Лейт."),
        (ji_id, "Основной штат"),
    ]:
        role = ctx.guild.get_role(rid)
        if role in member.roles:
            rank = title
            break
    rank = rank or "Нет"

    # ID и SteamID
    discord_id = member.id
    steamid = steam_map.get(member.id, "Не привязан")

    # Куратор
    curator_id = curator_map.get(member.id)
    curator = ctx.guild.get_member(curator_id).mention if curator_id else "Не назначен"

    # Отчетность за всё время
    call_key = member.display_name.strip().lower()
    total_duties = sum(d for c, d, _ in activity_reports if c.strip().lower() == call_key)
    total_interrogations = sum(1 for c, _ in interrogation_reports if c.strip().lower() == call_key)

    # Отчетность за текущую неделю
    weekly_duties = sum(
        d for c, d, dt in activity_reports
        if c.strip().lower() == call_key and week_start <= dt <= week_end
    )
    weekly_interrogations = sum(
        1 for c, dt in interrogation_reports
        if c.strip().lower() == call_key and week_start <= dt <= week_end
    )

    # Формируем сообщение
    msg = (
        f"**{header}**\n"
        f"**Статистика пользователя:** {nick}\n\n"
        f"**Баллы:** {points}\n"
        f"**Отпуск:** {vacation_status}\n"
        f"**Варны:** {warn_count}/3\n"
        f"**Черная метка:** {black_status}\n"
        f"**Звание:** {rank}\n"
        f"**ID:** {discord_id}\n"
        f"**SteamID:** {steamid}\n"
        f"**Куратор:** {curator}\n\n"
        f"**Отчетность за всё время:**\n"
        f"• Дежурств — {total_duties}\n"
        f"• Допросов — {total_interrogations}\n\n"
        f"**Отчетность за {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}:**\n"
        f"• Дежурств — {weekly_duties}\n"
        f"• Допросов — {weekly_interrogations}"
    )

    await ctx.send(msg)

# ─────────────────── Slash-команда /info ───────────────────
# ─────────────────── Команда /info ───────────────────
@bot.command(name='info')
async def info(ctx, member: discord.Member):
    """
    Показывает информацию о указанном пользователе.
    Использование: !info @пользователь
    """
    now = datetime.date.today()
    week_start = now - datetime.timedelta(days=now.weekday())
    week_end   = week_start + datetime.timedelta(days=6)

    # Заголовок и ник
    header = "JI"
    nick = member.display_name

    # Баллы
    points = rp_points.get(member.id, 0)

    # Отпуск
    on_vacation = ctx.guild.get_role(vacation_id) in member.roles
    vacation_status = "В отпуске" if on_vacation else "Не в отпуске"

    # Варны
    warn_count = 0
    for num, rid in WARN_ROLE_IDS.items():
        role = ctx.guild.get_role(rid)
        if role in member.roles:
            warn_count = num

    # Черная метка
    has_black = ctx.guild.get_role(black_mark_id) in member.roles
    black_status = "Да" if has_black else "Нет"

    # Звание (приоритетное)
    rank = "Нет"
    for rid, title in [
        (lrc_id, "Подполковник"),
        (mjr_id, "Майор"),
        (cpt_id, "Капитан"),
        (slt_id, "Ст. Лейт."),
        (lt_id, "Лейтенант"),
        (jlt_id, "Мл. Лейт."),
        (ji_id, "Основной штат"),
    ]:
        role = ctx.guild.get_role(rid)
        if role in member.roles:
            rank = title
            break

    # ID и SteamID
    discord_id = member.id
    steamid = steam_map.get(member.id, "Не привязан")

    # Куратор
    curator_id = curator_map.get(member.id)
    curator = ctx.guild.get_member(curator_id).mention if curator_id else "Не назначен"

    # Отчетность за всё время
    call_key = member.display_name.strip().lower()
    total_duties = sum(d for c, d, _ in activity_reports if c.strip().lower() == call_key)
    total_interrogations = sum(1 for c, _ in interrogation_reports if c.strip().lower() == call_key)

    # Отчетность за текущую неделю
    weekly_duties = sum(
        d for c, d, dt in activity_reports
        if c.strip().lower() == call_key and week_start <= dt <= week_end
    )
    weekly_interrogations = sum(
        1 for c, dt in interrogation_reports
        if c.strip().lower() == call_key and week_start <= dt <= week_end
    )

    # Формируем сообщение
    msg = (
        f"**{header}**\n"
        f"**Статистика пользователя:** {nick}\n\n"
        f"**Баллы:** {points}\n"
        f"**Отпуск:** {vacation_status}\n"
        f"**Варны:** {warn_count}/3\n"
        f"**Черная метка:** {black_status}\n"
        f"**Звание:** {rank}\n"
        f"**ID:** {discord_id}\n"
        f"**SteamID:** {steamid}\n"
        f"**Куратор:** {curator}\n\n"
        f"**Отчетность за всё время:**\n"
        f"• Дежурств — {total_duties}\n"
        f"• Допросов — {total_interrogations}\n\n"
        f"**Отчетность за {week_start:%d.%m.%Y}–{week_end:%d.%m.%Y}:**\n"
        f"• Дежурств — {weekly_duties}\n"
        f"• Допросов — {weekly_interrogations}"
    )

    await ctx.send(msg)
# ─────────────────── Запуск бота ───────────────────
bot.run(TOKEN)
