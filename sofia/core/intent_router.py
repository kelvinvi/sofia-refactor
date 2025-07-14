"""Module core.intent_router: Roteia intents para os handlers para execução."""

class IntentRouter:
    """Gerencia o roteamento de intents para os handlers correspondentes."""

    def __init__(self, context):
        """Inicializa o roteador com o contexto da aplicação.
        Args: 
        context: Instância da Sofia contendo handlers e serviços."""

        self.context = context

    async def handle(self, intent: str, user_id: str, user_message: str,
                     nome_usuario: str = None) -> str:
        """Dispara o handler apropriado com base na intent detectada.
        Returns: Resposta gerada pelo handler alvo."""

        if intent == "admin":
            return await self.context._handle_admin_commands(
                user_id, user_message
            )
        if intent == "boards":
            return await self.context._handle_boards_analysis(
                user_id, user_message
            )
        if intent == "learning":
            return self.context._handle_learning(user_id, user_message)
        if intent == "file_list":
            quantidade = self.context._extrair_quantidade_listagem(
                user_message
            )
            return await self.context.listar_arquivos(
                user_id,
                user_message,
                user_message.lower(),
                quantidade
            )
        if intent == "file":
            return await self.context._handle_file_requests(
                user_id, user_message
            )
        if intent == "greeting":
            return self.context._handle_greetings(user_message)

        # Fallback para perguntas gerais
        return await self.context._handle_general_questions(
            user_id, user_message, nome_usuario
        )
