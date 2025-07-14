"""
Module handlers.file_handler: Lida com busca e listagem de arquivos.
"""

# 1. Standard library imports
import re
import traceback
from datetime import datetime

# 3. Local application imports
from src.services.constants import (
    FILE_NOT_FOUND_MESSAGE, FILE_SEARCH_NO_RESULTS,
    SHAREPOINT_CONFIG_ERROR, SHAREPOINT_DRIVE_ERROR,
    NO_FILES_MESSAGE, FILE_LIST_INSTRUCTIONS,
    SINGLE_FILE_CLICK_INSTRUCTION, MULTIPLE_FILES_CLICK_INSTRUCTION,
    MAX_FILE_LIMIT, DEFAULT_FILE_LIMIT, MIN_WORD_LENGTH,
    URL_VALIDATION_PATTERNS, INVALID_URL_PATTERNS,
    REGEX_PATTERNS, GRAPH_ENDPOINTS, ENDPOINTS_TIMEOUT
)


class FileHandler:
    """Handler para intents de busca e listagem de arquivos."""

    def __init__(self, context):
        self.context = context
        self.sharepoint = context.sharepoint_service
        self.cache = context.boards_cache
        self.cache_duration = context.cache_duration
        self.file_extension_pattern = re.compile(
            REGEX_PATTERNS['file_extension'], re.IGNORECASE
        )

    async def listar_arquivos(self, user_id: str, user_message: str,
                              msg_lower: str, quantidade: int = 10
                              ) -> str:
        """Lista arquivos recentes do SharePoint.
        1. Valida configuração.
        2. Busca últimos N arquivos.
        3. Formata resposta."""

        try:
            if not self._validate_sharepoint_config():
                return self._get_sharepoint_config_error()

            print(f"[DEBUG] Solicitando {quantidade} arquivos...")
            arquivos = self.sharepoint.list_recent_files(limit=quantidade)
            if not arquivos:
                return NO_FILES_MESSAGE

            linhas = self._format_file_list(arquivos)
            return self._build_file_list_response(
                quantidade, len(arquivos), linhas
            )
        except Exception as e:
            return self._handle_file_listing_error(e)

    async def buscar_arquivos(self, user_id: str,
                              termo_busca: str) -> str:
        """Busca arquivos no SharePoint por termo e utiliza cache para otimização."""

        if not termo_busca.strip():
            return FILE_NOT_FOUND_MESSAGE

        key = f"search_{termo_busca.lower().replace(' ', '_')}"
        cached = self.cache.get(key)
        if (cached and
                (datetime.now() - cached['timestamp']).seconds
                < self.cache_duration):
            return cached['result']

        for strat in (
            self._search_direct,
            self._search_with_ai,
            self._search_with_variations,
            self._search_by_words
        ):
            try:
                arquivos = await strat(termo_busca) \
                    if strat.__name__ == '_search_with_ai' \
                    else strat(termo_busca)
                if arquivos:
                    res = self._formatar_resultados_busca(
                        termo_busca, arquivos
                    )
                    self.cache[key] = {
                        'result': res,
                        'timestamp': datetime.now()
                    }
                    return res
            except Exception:
                continue

        return FILE_SEARCH_NO_RESULTS.format(termo_busca)

    def _search_direct(self, termo: str) -> list:
        """Busca direta via API do SharePoint."""
        return self.sharepoint.search_files(termo)

    async def _search_with_ai(self, termo: str) -> list | None:
        """Interpreta termo com OpenAI antes de buscar."""

        termo_limpo = await self.context.openai_service.\
            interpretar_termo_busca(termo)
        if termo_limpo != termo:
            return self.sharepoint.search_files(termo_limpo)
        return None

    def _search_with_variations(self, termo: str) -> list | None:
        """Gera variações do termo e tenta cada uma."""

        vars_ = [
            termo.replace(' ', '_'),
            termo.replace(' ', '-'),
            termo.replace('_', ' '),
            termo.replace('-', ' '),
            termo.lower(),
            termo.title()
        ]
        for v in vars_:
            try:
                if v != termo:
                    arqs = self.sharepoint.search_files(v)
                    if arqs:
                        return arqs
            except Exception:
                continue
        return None

    def _search_by_words(self, termo: str) -> list | None:
        """Divide termo em palavras relevantes e busca por cada."""

        words = [w for w in termo.split()
                 if len(w) > MIN_WORD_LENGTH]
        found = []
        for w in words:
            try:
                arqs = self.sharepoint.search_files(w)
                if arqs:
                    found.extend(arqs)
            except Exception:
                continue
        uniq = {f.get("name"): f for f in found if f.get("name")}
        return list(uniq.values()) if uniq else None

    def _validate_sharepoint_config(self) -> bool:
        """Verifica se token e drive_id estão presentes."""
        return (getattr(self.sharepoint, 'token', None) and
                getattr(self.sharepoint, 'drive_id', None))

    def _get_sharepoint_config_error(self) -> str:
        """Retorna mensagem de erro de configuração."""
        return (SHAREPOINT_CONFIG_ERROR
                if not getattr(self.sharepoint, 'token', None)
                else SHAREPOINT_DRIVE_ERROR)

    def _build_file_list_response(self, qtd: int, total: int,
                                  resultados: list) -> str:
        """Monta a mensagem de resposta da listagem."""
        return (
            f"📂 **{qtd} arquivos solicitados** "
            f"({total} encontrados):\n\n"
            f"{chr(10).join(resultados)}\n\n"
            f"{FILE_LIST_INSTRUCTIONS}"
        )

    def _format_file_list(self, arquivos: list) -> list:
        """Formata cada arquivo com nome, link válido e data."""

        linhas = []
        for i, arq in enumerate(arquivos, 1):
            nome = arq.get("name", "Sem nome")
            url = self._obter_url_valida(arq)
            dt = self._formatar_data_com_hora(
                arq.get("modified_time")
                or arq.get("lastModifiedDateTime")
            )
            if url != "#":
                linhas.append(f"{i}. **[{nome}]({url})** 📄 {dt}")
            else:
                linhas.append(f"{i}. **{nome}** 📄 {dt} ⚠️ *Link indisponível*")
        return linhas

    def _formatar_resultados_busca(self, termo: str,
                                   arquivos: list) -> str:
        """Escolhe formatação para um ou vários arquivos."""
        if len(arquivos) == 1:
            return self._format_single_file_result(arquivos[0], termo)
        return self._format_multiple_files_result(arquivos, termo)

    def _format_single_file_result(self, arq: dict,
                                   termo: str) -> str:
        """Formata resposta para único arquivo."""

        nome = arq.get("name", "Sem nome")
        url = self._obter_url_valida(arq)
        dt = self._formatar_data_com_hora(
            arq.get("modified_time")
            or arq.get("lastModifiedDateTime")
        )
        return (
            f"📂 Encontrei **1 arquivo** para '**{termo}**':\n\n"
            f"1. **[{nome}]({url})** 📄 {dt}\n\n"
            f"{SINGLE_FILE_CLICK_INSTRUCTION}"
        )

    def _format_multiple_files_result(self, arquivos: list,
                                      termo: str) -> str:
        """Formata resposta quando há múltiplos arquivos."""

        lines = []
        for i, arq in enumerate(arquivos, 1):
            nome = arq.get("name", "Sem nome")
            url = self._obter_url_valida(arq)
            dt = self._formatar_data_com_hora(
                arq.get("modified_time")
                or arq.get("lastModifiedDateTime")
            )
            lines.append(f"{i}. **[{nome}]({url})** 📄 {dt}")
        return (
            f"📂 Encontrei **{len(arquivos)} arquivo(s)** "
            f"para '**{termo}**':\n\n"
            f"{chr(10).join(lines)}\n\n"
            f"{MULTIPLE_FILES_CLICK_INSTRUCTION}"
        )

    def _obter_url_valida(self, arq: dict) -> str:
        """Retorna primeira URL válida encontrada em campos web_url, url, 
        server_url ou id."""

        for f in ("web_url", "url", "server_url", "id"):
            url = arq.get(f)
            if isinstance(url, str) and url.strip() and \
               any(re.search(p, url.lower()) for p in URL_VALIDATION_PATTERNS)\
               and url.lower().strip() not in INVALID_URL_PATTERNS:
                return url
        return "#"

    def _formatar_data_com_hora(self, data_iso: str) -> str:
        """Converte ISO timestamp para 'dd/mm/YYYY às HH:MM'."""

        if not data_iso:
            return f"📅 Última modificação: "\
                   f"{datetime.now().strftime('%d/%m/%Y às %H:%M')}"
        try:
            if 'T' in data_iso:
                fmt = "%Y-%m-%dT%H:%M:%SZ" if data_iso.endswith("Z") else \
                      "%Y-%m-%dT%H:%M:%S"
                dt = datetime.strptime(data_iso[:19], fmt)
            else:
                dt = datetime.strptime(data_iso[:10], "%Y-%m-%d")
            return f"📅 Última modificação: {dt.strftime('%d/%m/%Y às %H:%M')}"
        except Exception:
            return f"📅 Última modificação: "\
                   f"{datetime.now().strftime('%d/%m/%Y às %H:%M')}"

    def _handle_file_listing_error(self, e: Exception) -> str:
        """Gera mensagem de erro de listagem, diferenciando 400 e 401."""

        print(f"❌ [ERRO] Falha na listagem: {e}")
        traceback.print_exc()
        msg = str(e)
        if "400" in msg:
            return "⚠️ Solicitação inválida (erro 400)."
        if "401" in msg:
            return "⚠️ Falha de autenticação (erro 401)."
        return "⚠️ Ocorreu um erro técnico ao acessar os arquivos."
