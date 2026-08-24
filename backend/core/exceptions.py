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


class ModeloIndisponivel(SafeFieldError):
    status_code = 503
    mensagem = "Modelo preditivo indisponivel. Verifique os artefatos em models/."


class BancoIndisponivel(SafeFieldError):
    status_code = 503
    mensagem = "Banco de dados indisponivel."


class CredenciaisInvalidas(SafeFieldError):
    status_code = 401
    mensagem = "Usuario ou senha invalidos."
