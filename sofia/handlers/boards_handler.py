"""
Module handlers.boards_handler: Lida com intents relacionadas ao Azure Boards.
"""

# 1. Standard library imports
from datetime import datetime
from typing import Optional

# 2. Third-party imports
import pandas as pd

# 3. Local application imports
from src.services.constants import (
    BOARD_PROJECTS, CLIENT_SEARCH_KEYWORDS, BOARDS_HELP_MESSAGE,
    BOARDS_SELECTION_MESSAGE, CLIENT_KEYWORDS, ACTIVITY_KEYWORDS,
    COLLABORATOR_REFERENCES, PROGRESS_KEYWORDS, TODO_KEYWORDS,
    COMPLETED_KEYWORDS, OVERVIEW_KEYWORDS, OVERDUE_KEYWORDS,
    TASK_COUNT_KEYWORDS, HIERARCHY_KEYWORDS, MAPA_TIPOS_ITENS
)
from src.services.module.boards.processing import (
    cliente_com_mais_atividades,
    cliente_com_mais_atividades_sonar_labs,
    processar_work_items_df,
    obter_responsavel_com_mais_tarefas,
    formatar_lista_tarefas, tarefas_em_andamento,
    tarefas_a_fazer, tarefas_em_atraso, formatar_visao_geral,
    extrair_tarefas_por_colaborador_e_estado,
    extrair_tarefas_por_colaborador
)
from src.services.module.boards.azure_boards_service import (
    AzureBoardsService
)


class BoardsHandler:
    """Handler para análise e consulta de Azure Boards."""

    def __init__(self, context):
        self.context = context

    async def responder_com_boards(self, pergunta: str,
                                   user_id: str = "global") -> str:
        """Processa perguntas do usuário sobre Azure Boards.

        1. Checa comandos de ajuda.
        2. Escolhe projeto.
        3. Busca dados.
        4. Encaminha para análise detalhada."""

        pt = pergunta.lower()

        # Se for pedido de ajuda, retorna mensagem padrão
        if pt in ["ajuda", "help", "comandos"]:
            return BOARDS_HELP_MESSAGE

        projeto = self._detect_board_project(pt, user_id)
        if not projeto:
            return BOARDS_SELECTION_MESSAGE

        # Atualiza último projeto consultado pelo usuário
        self.context.ultimo_board_por_usuario[user_id] = projeto
        nome = "Operações" if projeto == "Sonar" else projeto

        df = await self._get_boards_data_cached(projeto, pt)
        if df is None:
            return f"Erro ao consultar o Azure Boards de '{nome}'"

        return self._process_boards_query(user_id, pt, df, nome)

    async def _get_boards_data_cached(self, projeto: str,
                                      pt: str
                                      ) -> Optional[pd.DataFrame]:
        """Retorna DataFrame de work items."""

        buscar_epicos = any(x in pt for x in CLIENT_SEARCH_KEYWORDS)
        chave = (f"{projeto}_"
                 f"{datetime.now().strftime('%Y%m%d_%H_%M')[:12]}")
        if buscar_epicos:
            chave += "_epicos"

        cached = self.context.boards_cache.get(chave)
        if (cached and
                (datetime.now() - cached['timestamp']).seconds
                < self.context.cache_duration):
            return cached['dataframe']

        try:
            svc = AzureBoardsService(projeto)
            items = svc.buscar_work_items(batch_size=100)
            if not items:
                return None

            df = await processar_work_items_df(items, projeto,
                                               buscar_epicos)
            # Armazena no cache para próxima consulta
            self.context.boards_cache[chave] = {
                'dataframe': df,
                'timestamp': datetime.now()
            }
            return df
        except Exception as e:
            print(f"❌ Erro ao buscar dados do board: {e}")
            return None

    def _process_boards_query(self, user_id: str, pt: str,
                              df: pd.DataFrame, nome: str) -> str:
        """Encaminha query para atividade de cliente, colaborador específico ou geral.
        """

        if self._is_client_activity_query(pt):
            if "sonar labs" in nome.lower():
                return cliente_com_mais_atividades_sonar_labs(df)
            return cliente_com_mais_atividades(df, projeto=nome)

        colaborador = self._detect_collaborator_in_query(pt, user_id, df)
        if colaborador:
            return self._process_collaborator_specific_query(
                pt, df, colaborador
            )

        return self._process_general_boards_query(pt, df, nome)

    def _is_client_activity_query(self, pt: str) -> bool:
        """Detecta queries sobre atividade de cliente."""
        return (any(k in pt for k in CLIENT_KEYWORDS) and
                any(a in pt for a in ACTIVITY_KEYWORDS))

    def _detect_collaborator_in_query(self, pt: str, user_id: str,
                                      df: pd.DataFrame) -> Optional[str]:
        """Identifica colaborador em consultas usando tokens e histórico de último 
        colaborador."""

        if any(ref in pt for ref in COLLABORATOR_REFERENCES):
            return self.context.ultimo_colaborador_consultado.get(user_id)

        tokens = set(pt.split())
        for nome in df['responsavel'].dropna().unique():
            if tokens & set(nome.lower().split()):
                self.context.ultimo_colaborador_consultado[user_id] = nome
                return nome
        return None

    def _process_collaborator_specific_query(self, pt: str,
                                             df: pd.DataFrame,
                                             nome: str) -> str:
        """Processa queries específicas para um colaborador."""

        if any(t in pt for t in PROGRESS_KEYWORDS):
            tasks = extrair_tarefas_por_colaborador_e_estado(
                df, nome, "em andamento"
            )
            return formatar_lista_tarefas(
                tasks, f"Tarefas em andamento de {nome}"
            )
        if any(t in pt for t in TODO_KEYWORDS):
            tasks = extrair_tarefas_por_colaborador_e_estado(
                df, nome, "a fazer"
            )
            return formatar_lista_tarefas(
                tasks, f"Tarefas a fazer de {nome}"
            )
        if any(t in pt for t in COMPLETED_KEYWORDS):
            tasks = extrair_tarefas_por_colaborador_e_estado(
                df, nome, "concluído"
            )
            return formatar_lista_tarefas(
                tasks, f"Tarefas concluídas de {nome}"
            )
        # Default: todas as tarefas
        tasks = extrair_tarefas_por_colaborador(df, nome)
        return formatar_lista_tarefas(tasks, f"Tarefas de {nome}")

    def _process_general_boards_query(self, pt: str,
                                      df: pd.DataFrame,
                                      nome: str) -> str:
        """Processa contagens, overviews, hierarquia e demais queries gerais."""

        for chave, tipo in MAPA_TIPOS_ITENS.items():
            if f"quantos {chave}" in pt or f"quantas {chave}" in pt:
                total = len(df[df["tipo"].str.lower() == tipo])
                return (
                    f"🔢 Existem **{total}** item(ns) do tipo "
                    f"**{tipo.title()}** no board {nome}."
                )

        for chave, tipo in MAPA_TIPOS_ITENS.items():
            if chave in pt:
                tasks = df[df["tipo"].str.lower() == tipo]
                return formatar_lista_tarefas(
                    tasks, f"{tipo.title()}s do board {nome}"
                )

        if any(k in pt for k in OVERVIEW_KEYWORDS):
            return formatar_visao_geral(df)
        if any(k in pt for k in TODO_KEYWORDS):
            return formatar_lista_tarefas(
                tarefas_a_fazer(df),
                f"Tarefas a fazer do board {nome}"
            )
        if any(k in pt for k in PROGRESS_KEYWORDS):
            return formatar_lista_tarefas(
                tarefas_em_andamento(df),
                f"Tarefas em andamento do board {nome}"
            )
        if any(k in pt for k in OVERDUE_KEYWORDS):
            return formatar_lista_tarefas(
                tarefas_em_atraso(df),
                f"Tarefas atrasadas do board {nome}"
            )
        if any(k in pt for k in TASK_COUNT_KEYWORDS):
            resp, qtd = obter_responsavel_com_mais_tarefas(df)
            return (
                f"O colaborador com mais tarefas no total é {resp}, "
                f"com {qtd} tarefas."
            )
        if any(k in pt for k in HIERARCHY_KEYWORDS):
            return self._formatar_hierarquia_user_story(df)

        return formatar_visao_geral(df)

    def _formatar_hierarquia_user_story(self, df: pd.DataFrame) -> str:
        """Formata hierarquia de User Stories e suas Tasks."""

        us = df[df["tipo"].str.lower() == "user story"]
        ts = df[df["tipo"].str.lower() == "task"]
        if us.empty:
            return "❌ Nenhuma User Story encontrada no board."

        linhas = []
        for _, row in us.iterrows():
            linhas.append(f"🔹 **{row['titulo']}** (#{row['id']})")
            sub = ts[ts["area"] == row["area"]]
            if sub.empty:
                linhas.append("   • _(sem tasks registradas)_")
            else:
                for _, t in sub.iterrows():
                    linhas.append(f"   • {t['titulo']} (#{t['id']})")
        return "\n".join(linhas)
