# ─────────────────── JI ───────────────────

CHANNELS = {
    'activity': 1111772928086904862,
    'interrogation': 1099790754068574229,
}

# ─────────────────── Звания ───────────────────
arc_id        = 1303430148728815657  # полковник
lrc_gimel_id  = 1312829578582036561  # подполковник GIMEL
lrc_id        = 1144563810426945556  # подполковник
mjr_gimel_id  = 1312834380309200986  # майор GIMEL
mjr_id        = 1144556996343898132  # майор
cpt_id        = 1144556821210730526  # капитан
slt_id        = 1310248993741340703  # старший лейтенант
lt_id         = 1144556650141851698  # лейтенант
jlt_id        = 1303681047954718741  # младший лейтенант


NEEDS_AUTH_ROLE_ID = 1338620060046069844


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
main_corps_id = 1341150411498717284  # основной штат
gimel_id      = 1303437044982485044  # GIMEL
ji_id         = 1151606209552580790 # ОПЮ "Judgement Investigation"

# Словарь штатов
CORPS_MAP = {
    'main_corps': main_corps_id,
    'gimel':      gimel_id,
}
# ─────────────────── Отпуск ───────────────────
vacation_id = 1102951461001887864  # отпуск

VACATION_MAP = {
    'vacation': vacation_id,
}

# ─────────────────── WARN-роли и чёрная метка ───────────────────
f_warn_id      = 1347316687829073981  # WARN 1/3
s_warn_id      = 1347316908919095318  # WARN 2/3
t_warn_id      = 1347316951847927899  # WARN 3/3


# Индексы WARN-уровней
WARN_ROLE_IDS = {
    1: f_warn_id,
    2: s_warn_id,
    3: t_warn_id,
}

# ─────────────────── Должности ───────────────────
head_ji_id                    = 1106724721657135164  # Глава JI
adjutant_ji_id                = 1106727175035568168  # Адъютант JI
leader_office_id              = 1373276451029258270  # Главный по бюрократической работе
leader_penal_battalion_id     = 1373276036745134181  # Главный по воспитательной работе
senate_id                     = 1346213641808121906  # Сенат GIMEL
head_curator_id               = 1312394577596121128  # Главный куратор
director_office_id            = 1378043321372512417  # Директор канцелярии
leader_main_corps_id          = 1303427706125287494  # Лидер основного корпуса
leader_gimel_id               = 1322929663911137280  # Лидер GIMEL
cmd_elite_id                  = 1124006367745802280  # CMD.ELITE
head_ovd_id                   = 1331559878963105822  # Глава ОВД
master_office_id              = 1373276414136291398  # Ведущий сотрудник канцелярии
worker_office_id              = 1315764503211802696  # Сотрудник канцелярии
curator_id                    = 1304579271540473897  # Куратор
trainee_curator_id            = 1360916655068282900  # Куратор-стажер
internship_id                 = 1353721120867487784  # -= Проходит стажировку =-
wl_inquisitor_id              = 1097947047522484244  # [▽] WL-INQUISITOR
black_mark_id                 = 1319761108172800122  # «чёрная метка»

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