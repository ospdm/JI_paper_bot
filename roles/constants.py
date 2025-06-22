# ─────────────────── JI ───────────────────

CHANNELS = {
    'activity': 1384128582263111740,
    'interrogation': 1384128486268076032,
}

# ─────────────────── Звания ───────────────────
arc_id        = 1384838379279220887  # полковник
lrc_gimel_id  = 1384844327125254185  # полковник GIMEL
lrc_id        = 1384128791558750280  # подполковник
mjr_gimel_id  = 1384844497300623421  # майор GIMEL
mjr_id        = 1384128791474868326  # майор
cpt_id        = 1384205899224318082  # капитан
slt_id        = 1384206003985317898  # старший лейтенант
lt_id         = 1384206159036026943  # лейтенант
jlt_id        = 1384206140707180695  # младший лейтенант


NEEDS_AUTH_ROLE_ID = 1384833247850266715


# Словарь званий
RANKS_MAP = {
    'arc':        arc_id,
    'lrc_gimel':  lrc_gimel_id,
    'lrc':        lrc_id,
    'mjr_gimel':  mjr_gimel_id,
    'mjr':        mjr_id,
    'cpt':        cpt_id,
    'slt':        slt_id,
    'lt':         lt_id,
    'jlt':        jlt_id,
}

# ─────────────────── Штаты ───────────────────
main_corps_id = 1384128750790119424  # основной штат
gimel_id      = 1384206551262171216  # GIMEL
ji_id         = 1384899834301120543 # ОПЮ "Judgement Investigation"

# Словарь штатов
CORPS_MAP = {
    'main_corps': main_corps_id,
    'gimel':      gimel_id,
}
# ─────────────────── Отпуск ───────────────────
vacation_id = 1384128722613043212  # отпуск

VACATION_MAP = {
    'vacation': vacation_id,
}

# ─────────────────── WARN-роли и чёрная метка ───────────────────
f_warn_id      = 1384543038533275738  # WARN 1/3
s_warn_id      = 1384543092769554442  # WARN 2/3
t_warn_id      = 1384543134142431232  # WARN 3/3
black_mark_id  = 1384543181541998722  # «чёрная метка»

# Индексы WARN-уровней
WARN_ROLE_IDS = {
    1: f_warn_id,
    2: s_warn_id,
    3: t_warn_id,
}

# ─────────────────── Должности ───────────────────
head_ji_id                    = 1384836513270988911  # Глава JI
adjutant_ji_id                = 1384837107222183998  # Адъютант JI
leader_office_id              = 1384873807105363968  # Главный по бюрократической работе
leader_penal_battalion_id     = 1384874628849340487  # Главный по воспитательной работе
senate_id                     = 1384837573087592478  # Сенат GIMEL
head_curator_id               = 1384837749605007421  # Главный куратор
director_office_id            = 1384837961446854748  # Директор канцелярии
leader_main_corps_id          = 1384838217156530227  # Лидер основного корпуса
leader_gimel_id               = 1384872164158738526  # Лидер GIMEL
cmd_elite_id                  = 1384838662541414475  # CMD.ELITE
head_ovd_id                   = 1384839249085333554  # Глава ОВД
master_office_id              = 1384839793330094202  # Ведущий сотрудник канцелярии
worker_office_id              = 1384839960594481263  # Сотрудник канцелярии
curator_id                    = 1384840528360767488  # Куратор
trainee_curator_id            = 1384840571432206336  # Куратор-стажер
internship_id                 = 1385728779233656952  # -= Проходит стажировку =-
wl_inquisitor_id              = 1385728964714299493  # 1385728964714299493

POST_MAP = {
    'head_ji':                  head_ji_id,
    'adjutant_ji':              adjutant_ji_id,
    'leader_office':            leader_office_id,
    'leader_penal_battalion':   leader_penal_battalion_id,
    'senate':                   senate_id,
    'head_curator':             head_curator_id,
    'director_office':          director_office_id,
    'leader_main_corps':        leader_main_corps_id,
    'leader_gimel':             leader_gimel_id,
    'cmd_elite':                cmd_elite_id,
    'head_ovd':                 head_ovd_id,
    'master_office':            master_office_id,
    'worker_office':            worker_office_id,
    'curator':                  curator_id,
    'trainee_curator':          trainee_curator_id,
}

REPORT_ROLE_IDS = [mjr_id, cpt_id, slt_id, lt_id, main_corps_id]