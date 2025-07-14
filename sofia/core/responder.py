"""Module core.responder: Inicializa serviços centrais e detecta intents."""

# 1. Standard library imports
import re
import traceback
from functools import lru_cache
from datetime import datetime

# 3. Local application imports
from .intent_router import IntentRouter
from src.services.constants import (
    ADMIN_COMMANDS, BOARDS_COMMANDS, LEARNING_TRIGGERS, LIST_PATTERNS,
    GREETING_WORDS, FILE_KEYWORDS, ACTION_KEYWORDS, CASUAL_WORDS,
    FILE_INTENT_INDICATORS, CASUAL_INDICATORS, REGEX_PATTERNS
)


class ResponderCore:
    """Orquestra a detecção de intent e roteamento via IntentRouter."""

    def __init__(self, context):
        self.context = context
        self.router = IntentRouter(context)
        # Regex pré-compilados para detecção rápida de padrões
        self.greeting_pattern = re.compile(
            REGEX_PATTERNS['greeting'], re.IGNORECASE
        )
        self.file_extension_pattern = re.compile(
            REGEX_PATTERNS['file_extension'], re.IGNORECASE
        )
        self.file_naming_pattern = re.compile(
            REGEX_PATTERNS['file_naming']
        )

    async def responder(self, user_id: str, user_message: str,
                        nome_usuario: str = None) -> str:
        """Ponto de entrada para processar mensagem do usuário.
        1. Limpa cache expirado.
        2. Detecta intent.
        3. Roteia para handler.
        4. Loga a interação no histórico.
        Returns: Resposta do handler."""
        
        print(f"\n🔍 [DEBUG] Usuário: {user_id}, Mensagem: {user_message}")

        self.context._cleanup_cache()
        intent = self._detect_intent(user_message, user_id)

        try:
            resposta = await self.router.handle(
                intent, user_id, user_message, nome_usuario
            )
        except Exception as e:
            resposta = self._handle_error_response(e, intent, user_id)

        return self._logar_interacao(user_id, user_message, resposta)

    def _detect_intent(self, message: str, user_id: str) -> str:
        """Identifica a intenção da mensagem.
        Verifica comandos admin, boards, learning, listagem, saudação, 
        critério de detecção de arquivo ou geral."""

        message_lower = message.lower().strip()

        if any(cmd in message_lower for cmd in ADMIN_COMMANDS.keys()):
            return "admin"
        if (any(cmd in message_lower for cmd in BOARDS_COMMANDS) or
                user_id in self.context.modo_analise_boards):
            return "boards"
        if (any(trig in message_lower for trig in LEARNING_TRIGGERS) or
                user_id in self.context.aprendizado_manual_ativo):
            return "learning"
        if any(pat in message_lower for pat in LIST_PATTERNS):
            return "file_list"
        if (len(message_lower.split()) <= 6 and
                self.greeting_pattern.search(message_lower)):
            return "greeting"
        if self._calculate_file_score(message) > 0.7:
            return "file"
        return "general"

    @lru_cache(maxsize=256)
    def _calculate_file_score(self, message: str) -> float:
        """Método para identificar queries de arquivos, combinando extensão, keywords e 
        nomeação."""

        m = message.lower()
        score = 0.0

        if self.file_extension_pattern.search(m):
            score += 0.5
        score += sum(0.2 for kw in FILE_KEYWORDS if kw in m)
        score += sum(0.15 for kw in ACTION_KEYWORDS if kw in m)
        if self.file_naming_pattern.search(m):
            score += 0.2
        score -= sum(0.2 for w in CASUAL_WORDS if w in m)

        return max(min(score, 1.0), 0.0)

    def _handle_error_response(self, e: Exception, intent: str,
                               user_id: str) -> str:
        """Gera mensagem de erro padrão e exibe stack trace para debug."""

        erro_id = f"ERR-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        log = (
            f"❌ [{erro_id}] Erro na intent '{intent}' do usuário "
            f"'{user_id}': {type(e).__name__}: {e}"
        )
        print(log)
        traceback.print_exc()
        return (
            "⚠️ Algo deu errado ao processar sua solicitação.\n"
            f"Código do erro: `{erro_id}`\n"
            "Tente novamente em instantes ou avise o time técnico."
        )

    def _logar_interacao(self, user_id: str, user_message: str,
                         resposta: str) -> str:
        """Registra interação no histórico de conversas."""
        self.context.conversation_history.add_interaction(
            user_id, user_message, resposta
        )
        return resposta
