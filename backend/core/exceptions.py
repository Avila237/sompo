"""
Excecoes de dominio. Traduzidas em respostas HTTP pelos handlers em api/main.py.

Nenhuma delas expoe detalhe interno ao cliente — o rastreamento fica no log.
"""


class SafeFieldError(Exception):
    """Base. Toda excecao de dominio carrega status HTTP e mensagem legivel."""

    status_code = 500
    mensagem = "Erro interno."


class EquipamentoNaoEncontrado(SafeFieldError):
    status_code = 404

    def __init__(self, equipamento_id: str):
        self.mensagem = f"Equipamento '{equipamento_id}' nao encontrado."
        super().__init__(self.mensagem)


class OperadorNaoEncontrado(SafeFieldError):
    status_code = 404

    def __init__(self, operador_id: str):
        self.mensagem = f"Operador '{operador_id}' nao encontrado."
        super().__init__(self.mensagem)


class LeituraInconsistente(SafeFieldError):
    """Leitura que contradiz o cadastro do equipamento (ex.: sensor que ele nao tem)."""

    status_code = 422

    def __init__(self, mensagem: str):
        self.mensagem = mensagem
        super().__init__(self.mensagem)


class LeituraReutilizada(SafeFieldError):
    """Mesmo leitura_id reenviado com outro payload: nao e retry, e conflito."""

    status_code = 409

    def __init__(self, leitura_id: str | None):
        self.mensagem = f"leitura_id {leitura_id} ja foi usado com outro payload."
        super().__init__(self.mensagem)


class ModeloIndisponivel(SafeFieldError):
    status_code = 503
    mensagem = "Modelo preditivo indisponivel. Verifique os artefatos em models/."


class BancoIndisponivel(SafeFieldError):
    status_code = 503
    mensagem = "Banco de dados indisponivel."


class CredenciaisInvalidas(SafeFieldError):
    status_code = 401
    mensagem = "Usuario ou senha invalidos."


class ClimaIndisponivel(SafeFieldError):
    status_code = 502

    def __init__(self, campos: list[str]):
        self.mensagem = (
            "Open-Meteo indisponivel e o payload nao traz o clima completo. "
            "Campos ausentes: " + ", ".join(campos) + "."
        )
        super().__init__(self.mensagem)
