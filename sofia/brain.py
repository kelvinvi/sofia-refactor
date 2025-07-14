"""
Módulo principal sofia.brain: Inicializa contexto e orquestra fluxo.
"""

# 1. Standard library imports
import re
from datetime import datetime

# 3. Local application imports
from .core.responder import ResponderCore
from .handlers.file_handler import FileHandler
from .handlers.boards_handler import BoardsHandler
from .handlers.general_handler import GeneralHandler
from src.services.api.openai.openai_service import OpenAIService
from src.services.module.sharepoint.sharepoint_service import (
    SharePointService
)
from src.services.history.conversation_history import ConversationHistory
from config.settings import CACHE_DURATION
from src.services.constants import REGEX_PATTERNS


class Sofia:
    def __init__(self):
        """Configura serviços, estados, cache e handlers."""
        self._initialize_core_services()
        self._initialize_user_states()
        self._initialize_cache_system()
        self._compile_regex_patterns()
        self._initialize_handlers()

    def _initialize_core_services(self):
        """Instancia serviços de OpenAI, histórico e SharePoint."""
        self.openai_service = OpenAIService()
        self.conversation_history = ConversationHistory()
        self.sharepoint_service = SharePointService()

    def _initialize_handlers(self):
        """Prepara core e handlers específicos por domínio."""
        self.responder_core = ResponderCore(self)
        self.file_handler = FileHandler(self)
        self.boards_handler = BoardsHandler(self)
        self.general_handler = GeneralHandler(self)

    def _initialize_user_states(self):
        """Inicializa dicionários de estado por usuário."""
        self.aprendizado_manual_ativo = {}
        self.etapa_aprendizado = {}
        self.modo_analise_boards = {}
        self.ultimo_colaborador_consultado = {}
        self.ultimo_board_por_usuario = {}

    def _initialize_cache_system(self):
        """Configura sistema de cache com timestamp e duração."""
        self.boards_cache = {}
        self.cache_duration = CACHE_DURATION
        self._last_cache_cleanup = datetime.now()

    def _compile_regex_patterns(self):
        """Pré-compila regex para arquivos e saudação."""
        self.file_extension_pattern = re.compile(
            REGEX_PATTERNS['file_extension'], re.IGNORECASE
        )
        self.file_naming_pattern = re.compile(
            REGEX_PATTERNS['file_naming']
        )
        self.greeting_pattern = re.compile(
            REGEX_PATTERNS['greeting'], re.IGNORECASE
        )

    async def responder(self, user_id: str, user_message: str,
                        nome_usuario: str = None) -> str:
        """Encaminha mensagem do usuário para o ResponderCore e retorna a resposta final
        ao usuário."""
        return await self.responder_core.responder(
            user_id, user_message, nome_usuario
        )

    def _cleanup_cache(self):
        """Remove entradas de cache expiradas com base em cache_duration."""
        now = datetime.now()
        expired = [
            key for key, data in self.boards_cache.items()
            if (now - data['timestamp']).seconds > self.cache_duration
        ]
        for key in expired:
            del self.boards_cache[key]
        self._last_cache_cleanup = now
