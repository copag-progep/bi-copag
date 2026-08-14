"""Testes da preservação de sessão do uploader SEI."""

import asyncio
import sys
import types

import pytest


playwright_module = types.ModuleType("playwright")
playwright_async_api = types.ModuleType("playwright.async_api")


class FakePlaywrightError(Exception):
    pass


class FakePlaywrightTimeout(FakePlaywrightError):
    pass


playwright_async_api.Error = FakePlaywrightError
playwright_async_api.TimeoutError = FakePlaywrightTimeout
playwright_async_api.async_playwright = object()
playwright_module.async_api = playwright_async_api
sys.modules.setdefault("playwright", playwright_module)
sys.modules.setdefault("playwright.async_api", playwright_async_api)

httpx_module = types.ModuleType("httpx")
httpx_module.HTTPError = type("FakeHttpxError", (Exception,), {})
httpx_module.AsyncClient = object
sys.modules.setdefault("httpx", httpx_module)

from scripts import sei_uploader  # noqa: E402


class FakeLocator:
    def __init__(self, count):
        self._count = count

    async def count(self):
        return self._count


class FakePage:
    def __init__(self, url, selectors=None):
        self.url = url
        self.selectors = set(selectors or [])

    def locator(self, selector):
        return FakeLocator(1 if selector in self.selectors else 0)

    async def wait_for_load_state(self, *args, **kwargs):
        return None


def test_authenticated_page_is_reused_without_forced_navigation(monkeypatch):
    page = FakePage(
        "https://sei.ufc.br/sei/controlador.php?acao=procedimento_controlar&infra_hash=abc",
        {"#lnkInfraUnidade", "#tblProcessosRecebidos"},
    )

    async def unexpected_navigation(*args, **kwargs):
        raise AssertionError("A sessão autenticada não deve ser navegada novamente.")

    monkeypatch.setattr(sei_uploader, "goto_tolerante", unexpected_navigation)

    base = asyncio.run(
        sei_uploader.garantir_painel_logado(
            page,
            "https://sei.ufc.br",
            "usuario",
            "senha",
            "https://sei.ufc.br/sei",
        )
    )

    assert base == "https://sei.ufc.br/sei"


def test_login_page_is_classified_as_expired_session():
    page = FakePage(
        "https://sei.ufc.br/sip/login.php",
        {"#txtUsuario"},
    )

    with pytest.raises(sei_uploader.SeiSessionExpired):
        asyncio.run(
            sei_uploader.aguardar_painel_processos(
                page,
            )
        )
