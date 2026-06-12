"""Testes de regressão do escopo setorial (controle de acesso por divisão).

Garante que setores_permitidos nunca é perdido em reconstruções internas
de AnalyticsFilters — a causa raiz do vazamento de dados entre divisões.

Executar: python backend/tests/test_access_scope.py
"""
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from backend.analytics import AnalyticsFilters, _effective_filters  # noqa: E402

SCOPE = ("DIAPE", "DICAT")


def test_effective_filters_preserva_setores_permitidos():
    """_effective_filters aplica lookback sem perder o escopo setorial."""
    original = AnalyticsFilters(setores_permitidos=SCOPE)
    effective = _effective_filters(original)
    assert effective.setores_permitidos == SCOPE, (
        f"VAZAMENTO: _effective_filters perdeu setores_permitidos "
        f"(esperado {SCOPE}, obtido {effective.setores_permitidos})"
    )
    # lookback foi aplicado (objetivo da função)
    assert effective.data_inicial is not None


def test_effective_filters_preserva_escopo_vazio():
    """Escopo vazio () = sem acesso — também não pode virar None."""
    original = AnalyticsFilters(setores_permitidos=())
    effective = _effective_filters(original)
    assert effective.setores_permitidos == (), (
        "VAZAMENTO: escopo vazio () virou None (acesso total)"
    )


def test_effective_filters_passthrough_com_data_inicial():
    """Com data_inicial definida, retorna o objeto original intacto."""
    original = AnalyticsFilters(data_inicial=date(2026, 1, 1), setores_permitidos=SCOPE)
    effective = _effective_filters(original)
    assert effective.setores_permitidos == SCOPE


def test_cache_key_inclui_setores_permitidos():
    """Chaves de cache distintas para escopos distintos — sem colisão admin/restrito."""
    irrestrito = AnalyticsFilters()
    restrito = AnalyticsFilters(setores_permitidos=SCOPE)
    vazio = AnalyticsFilters(setores_permitidos=())
    keys = {irrestrito.cache_key(), restrito.cache_key(), vazio.cache_key()}
    assert len(keys) == 3, "Colisão de chave de cache entre escopos diferentes"


def test_replace_preserva_todos_os_campos():
    """dataclasses.replace mantém o escopo ao trocar qualquer outro campo."""
    from dataclasses import replace
    original = AnalyticsFilters(setor="DIAPE", setores_permitidos=SCOPE)
    sem_setor = replace(original, setor=None)
    assert sem_setor.setores_permitidos == SCOPE
    assert sem_setor.setor is None


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_")]
    for test in tests:
        test()
        print(f"✓ {test.__name__}")
    print(f"\n{len(tests)} testes de escopo passaram.")
