import os
import logging
from dotenv import load_dotenv

import discord
from discord.ext import commands

import config

# Загрузка токена
load_dotenv(dotenv_path="token.env")
TOKEN = os.getenv("DISCORD_TOKEN")
if not TOKEN:
    raise RuntimeError("Не найден DISCORD_TOKEN в token.env")

# Логирование
logging.basicConfig(level=logging.INFO)

# Интенты
intents = discord.Intents.default()
intents.guilds = True
intents.members = True
intents.message_content = True  # нужно, если вы используете on_message

# Список ваших Cog-ов
INITIAL_EXTENSIONS = [
    "commands.events",
    "commands.addrole",
    "commands.removerole",
    "commands.temprole",
    "commands.vacation",
    "commands.removevacation",
    "commands.warn",
    "commands.removewarn",
    "commands.addrp",
    "commands.auth",
    "commands.curator",
    "commands.denied",
    "commands.info",
    "commands.steam",
    "commands.results",
    "commands.fullclearroles",
    "commands.jltinfo",
    "commands.logs"
]

class JIBot(commands.Bot):
    def __init__(self):
        # Отключаем текстовый префикс — оставляем только слэш-команды
        super().__init__(command_prefix=lambda *_: [], intents=intents, help_command=None)
        self.logger = logging.getLogger("JIBot")
        self._synced = False  # чтобы синхронизировать только один раз

    async def setup_hook(self):
        # Загружаем все ваши Cog-ы
        for ext in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(ext)
                self.logger.info(f"✅ Загружено расширение {ext}")
            except Exception as e:
                self.logger.exception(f"❌ Не удалось загрузить {ext}: {e}")

    async def on_ready(self):
        # Синхронизируем команды в DEVELOPMENT-гильдии при первом on_ready
        if not self._synced:
            self.logger.info(f"Бот запущен как {self.user} (ID {self.user.id})")
            guild_id = config.DEVELOPMENT_GUILD_ID
            guild_obj = discord.Object(id=guild_id)

            try:
                # Регистрируем/обновляем все команды именно в этой гильдии
                await self.tree.sync(guild=guild_obj)
                self.logger.info(f"✅ Синхронизированы slash-команды в гильдии ID {guild_id}")
            except Exception as e:
                self.logger.exception(f"❌ Ошибка синхронизации slash-команд в гильдии ID {guild_id}: {e}")

            # Для отладки покажем, какие команды зарегистрированы
            cmds = [c.name for c in self.tree.walk_commands()]
            self.logger.info(f"Registered slash commands in tree: {cmds}")

            self._synced = True
        else:
            # Если on_ready вызывается повторно (например, после переподключения)
            self.logger.info(f"on_ready повторно для {self.user} (ID {self.user.id})")


if __name__ == "__main__":
    bot = JIBot()
    bot.run(TOKEN)
