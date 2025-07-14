"""
Module handlers.general_handler: Trate perguntas gerais e aprendizado.
"""

# 1. Standard library imports
import re
from datetime import datetime
from functools import lru_cache

# 3. Local application imports
from src.services.constants import (
    POSITIVE_WORDS, FILE_CONTEXT_WORDS, CASUAL_INDICATORS,
    FILE_INTENT_INDICATORS, LEARNING_TRIGGERS, LEARNING_STEPS,
    LEARNING_QUESTION_PROMPT, LEARNING_ERROR_MESSAGE,
    LEARNING_ERROR_RETRY, COURTESY_RESPONSE,
    OPENAI_FALLBACK_MESSAGE
)
from src.services.knowledge.knowledge_manager import (
    listar_conhecimentos_manuais, salvar_aprendizado_manual
)
from config.settings import SessionLocal
from database.fragments import (
    gerar_fragmento_empresa, gerar_fragmento_setores,
    gerar_fragmento_funcionarios, gerar_fragmento_gerentes,
    gerar_fragmento_persona, gerar_fragmento_conhecimentos,
    gerar_fragmento_cerimonias
)
from database.fragments.projeto_fragment import gerar_fragmento_projetos
from database.fragments.participacao_fragment import \
    gerar_fragmento_participacoes


class GeneralHandler:
    """Handler para perguntas gerais e fluxo de aprendizado manual."""

    def __init__(self, context):
        self.context = context

    async def handle_general_questions(self, user_id: str,
                                       user_message: str,
                                       nome_usuario: str = None) -> str:
        """Processa dúvidas gerais, aprendizado e fallback de AI."""

        ml = user_message.lower()

        if self._is_courtesy_message(ml):
            return COURTESY_RESPONSE

        if nome_usuario and "meu nome" in ml:
            return f"Claro! Você é {nome_usuario}, certo? 😄"

        resp_manual = self.responder_com_aprendizados_manuais(user_message)
        if resp_manual:
            return resp_manual

        is_casual = self._is_casual_conversation(ml)
        has_file = self._has_file_intent(ml)
        if not is_casual and has_file:
            termo = self.context._extract_search_term(user_message)
            if termo:
                return await self.context.file_handler.buscar_arquivos(
                    user_id, termo
                )

        return await self._process_with_openai(user_id, user_message)

    def _is_courtesy_message(self, ml: str) -> bool:
        """Detecta mensagens positivas sem contexto de arquivo."""
        return (any(w in ml for w in POSITIVE_WORDS) and
                not any(w in ml for w in FILE_CONTEXT_WORDS))

    def _is_casual_conversation(self, ml: str) -> bool:
        """Detecta conversas casuais."""
        return any(p in ml for p in CASUAL_INDICATORS)

    def _has_file_intent(self, ml: str) -> bool:
        """Detecta quando o usuário quer buscar arquivo."""
        return any(p in ml for p in FILE_INTENT_INDICATORS)

    def responder_com_aprendizados_manuais(self, pergunta: str) -> \
            str | None:
        """Retorna resposta se a pergunta já existe em aprendizados manuais."""
        txt = pergunta.strip().lower()
        for conhec in listar_conhecimentos_manuais(limit=50):
            if conhec.get("pergunta", "").strip().lower() in txt:
                return conhec.get("resposta")
        return None

    def verificar_aprendizado_manual(self, user_id: str,
                                     user_message: str) -> bool:
        """Inicia o fluxo de aprendizado manual quando trigger é detectado."""
        msg = user_message.strip().lower()
        if any(p in msg for p in LEARNING_TRIGGERS):
            self.context.aprendizado_manual_ativo[user_id] = True
            self.context.etapa_aprendizado[user_id] = \
                LEARNING_STEPS['pergunta']
            return True
        return user_id in self.context.aprendizado_manual_ativo

    def processar_aprendizado_manual(self, user_id: str,
                                    user_message: str) -> str:
        """Continua o fluxo de aprendizado manual conforme etapa atual."""

        etapa = self.context.etapa_aprendizado.get(user_id)
        if etapa == LEARNING_STEPS['pergunta']:
            self.context.aprendizado_manual_ativo[user_id] = {
                "pergunta": user_message
            }
            self.context.etapa_aprendizado[user_id] = \
                LEARNING_STEPS['resposta']
            return LEARNING_QUESTION_PROMPT

        if etapa == LEARNING_STEPS['resposta']:
            perg = self.context.aprendizado_manual_ativo[user_id][
                "pergunta"
            ]
            msg = salvar_aprendizado_manual(perg, user_message)
            del self.context.aprendizado_manual_ativo[user_id]
            del self.context.etapa_aprendizado[user_id]
            return msg

        return LEARNING_ERROR_RETRY

    async def _process_with_openai(self, user_id: str,
                                   user_message: str) -> str:
        """Fallback que chama o OpenAIService para gerar a resposta geral."""

        try:
            tom = await self.context.openai_service.\
                classificar_tom_mensagem(user_message)
            print(f"🎨 [DEBUG] Tom detectado: {tom}")

            prompt = self.gerar_system_prompt(tom=tom)
            hist = self.context.conversation_history.\
                format_for_prompt(user_id)

            resposta = await self.context.openai_service.\
                gerar_resposta_geral(
                    user_message=user_message,
                    system_prompt=prompt,
                    historico_formatado=hist,
                    tom=tom
                )
            return resposta or OPENAI_FALLBACK_MESSAGE
        except Exception as e:
            print(f"❌ Erro OpenAI: {e}")
            return OPENAI_FALLBACK_MESSAGE

    @lru_cache(maxsize=32)
    def gerar_system_prompt(self, historico_conversa: str = "",
                            tom: str = "neutro") -> str:
        """Gera o prompt de sistema concatenando fragmentos de conhecimento."""
        
        with SessionLocal() as db:
            frags = [
                gerar_fragmento_persona(db),
                gerar_fragmento_empresa(db),
                gerar_fragmento_setores(db),
                gerar_fragmento_funcionarios(db),
                gerar_fragmento_gerentes(db),
                gerar_fragmento_projetos(db),
                gerar_fragmento_participacoes(db),
                gerar_fragmento_conhecimentos(db),
                gerar_fragmento_cerimonias(db),
            ]

        hoje = datetime.now().strftime("%d de %B de %Y")
        frags.append(
            f"A data de hoje é {hoje}. Use para responder "
            "perguntas como 'qual é o dia de hoje?'."
        )

        if tom == "animado":
            frags.append(
                "Adote um tom leve, simpático e entusiasmado, com emoticons. 😊"
            )
        elif tom == "sério":
            frags.append("Adote um tom mais formal, direto e profissional.")

        if historico_conversa:
            frags.append(historico_conversa)

        return "\n\n".join(p for p in frags if p.strip())
