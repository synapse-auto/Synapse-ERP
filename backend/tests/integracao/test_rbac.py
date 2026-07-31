"""`SC-010` — todo endpoint de gestor recusa token de operador.

**Este é o teste que a constituição pede duas vezes.** "Esconder o menu não é autorizar":
a tela esconde Configurações do operador, e isso não é garantia nenhuma — a garantia é o
`403` daqui, chamando a API direto.

O teste **descobre** os endpoints a partir do `/api/docs`, em vez de listá-los à mão.
Assim, endpoint novo de gestor entra na cobertura sozinho: quem esquecer o
`exige_papel("gestor")` numa rota nova vê o teste quebrar, não descobre em produção.

Roda **sem banco**: o `403` do RBAC acontece antes de qualquer consulta — é justamente o
que se quer provar. Por isso este arquivo não pula quando não há `DATABASE_URL`, e não
escreve nada em lugar nenhum.

Tarefa: T138
"""

from uuid import uuid4

import pytest

from app.seguranca.auth import UsuarioAutenticado, usuario_atual

# Rotas que **não** passam por `exige_papel` de propósito, e por quê.
FORA_DA_VARREDURA = {
    # Autenticação de máquina (`X-Segredo-Rotina`), não de pessoa — não há usuário.
    ("post", "/api/rotinas/diaria"),
    ("get", "/api/rotinas/diaria"),
    ("post", "/api/rotinas/semanal"),
    # Público por desenho: só diz se o serviço subiu.
    ("get", "/api/saude"),
}


def _operador() -> UsuarioAutenticado:
    return UsuarioAutenticado(
        id=uuid4(),
        nome="Contadora",
        email="operador@synapse.local",
        papel="operador",
        preferencias={},
    )


def _endpoints_de_gestor(openapi: dict) -> list[tuple[str, str]]:
    """Descobre pela descrição quem declara papel de gestor **sem** operador.

    A descrição é a fonte porque é ela que o contrato cobra ("todo endpoint declara o
    papel") e é o que aparece no `/api/docs`. Se a descrição disser gestor e o código
    aceitar operador, este teste pega a divergência — que é o caso perigoso.
    """
    achados = []
    for caminho, metodos in openapi["paths"].items():
        for metodo, operacao in metodos.items():
            if (metodo, caminho) in FORA_DA_VARREDURA:
                continue
            texto = (operacao.get("description") or "").lower()
            if "papel" not in texto:
                continue
            if "gestor" in texto and "operador" not in texto:
                achados.append((metodo, caminho))
    return sorted(achados)


def _url(caminho: str) -> str:
    """Troca `{id}` por um UUID qualquer: o `403` tem que vir antes de procurar o registro."""
    partes = []
    for pedaco in caminho.split("/"):
        partes.append(str(uuid4()) if pedaco.startswith("{") else pedaco)
    return "/".join(partes)


@pytest.fixture
def openapi(cliente) -> dict:
    return cliente.get("/api/openapi.json").json()


@pytest.fixture
def cliente_operador(cliente):
    """Cliente autenticado como **operador**, sem passar pelo Supabase Auth."""
    from app.main import app

    app.dependency_overrides[usuario_atual] = _operador
    yield cliente
    app.dependency_overrides.pop(usuario_atual, None)


def test_a_varredura_encontrou_endpoints_de_gestor(openapi):
    """Rede de proteção do próprio teste.

    Se a heurística parar de achar nada — por uma mudança no texto das descrições, por
    exemplo — os testes abaixo passariam vazios e ninguém notaria.
    """
    encontrados = _endpoints_de_gestor(openapi)
    assert len(encontrados) >= 15, (
        f"A varredura achou só {len(encontrados)} endpoints de gestor. A heurística de "
        "leitura da descrição provavelmente quebrou."
    )


def test_operador_recebe_403_em_todo_endpoint_de_gestor(cliente_operador, openapi):
    """`SC-010`, pela API direta — não pelo menu escondido."""
    falhas = []
    for metodo, caminho in _endpoints_de_gestor(openapi):
        resposta = cliente_operador.request(metodo, _url(caminho), json={})
        if resposta.status_code != 403:
            falhas.append(f"{metodo.upper()} {caminho} → {resposta.status_code}")

    assert (
        not falhas
    ), "Endpoints de gestor que NÃO recusaram um token de operador:\n  " + "\n  ".join(falhas)


def test_o_403_sai_no_formato_unico_de_erro(cliente_operador, openapi):
    metodo, caminho = _endpoints_de_gestor(openapi)[0]
    corpo = cliente_operador.request(metodo, _url(caminho), json={}).json()

    assert corpo["erro"]["codigo"] == "sem_permissao"
    assert corpo["erro"]["requisito"] == "RF-02"
    assert "gestor" in corpo["erro"]["mensagem"].lower()


def test_operador_continua_lendo_o_que_deve(cliente_operador):
    """Operador **lê tudo**; o que ele não faz é escrever cadastro estrutural.

    Sem este teste, "recusar tudo para operador" passaria nos demais e quebraria o
    sistema para quem mais o usa.
    """
    for caminho in ("/api/configuracoes", "/api/notificacoes", "/api/sessao"):
        resposta = cliente_operador.get(caminho)
        assert resposta.status_code != 403, f"{caminho} recusou o operador — ele lê tudo."


def test_sem_token_nenhum_endpoint_de_negocio_responde(cliente, openapi):
    """Antes do papel vem a autenticação: sem token, `401` em tudo."""
    amostra = [
        ("get", "/api/lancamentos"),
        ("get", "/api/dashboard"),
        ("get", "/api/clientes"),
        ("get", "/api/configuracoes"),
        ("get", "/api/auditoria"),
    ]
    for metodo, caminho in amostra:
        resposta = cliente.request(metodo, caminho)
        assert resposta.status_code == 401, f"{caminho} respondeu {resposta.status_code} sem token."
        assert resposta.json()["erro"]["codigo"] == "nao_autenticado"


def test_auditoria_geral_recusa_operador_e_explica_a_saida(cliente_operador):
    """`FR-103` tem dois modos com papéis diferentes.

    O **geral** é supervisão e recusa o operador — e a mensagem diz o caminho que ele
    tem: abrir o lançamento. Recusar sem dizer para onde ir faria o usuário concluir que
    o histórico não existe.

    O modo **por registro** (com `entidade` + `entidade_id`) é liberado ao operador; como
    ele consulta o banco, quem cobre é `tests/integracao/test_plataforma.py`.
    """
    geral = cliente_operador.get("/api/auditoria")
    assert geral.status_code == 403
    assert geral.json()["erro"]["requisito"] == "FR-103"
    assert "abra o lançamento" in geral.json()["erro"]["mensagem"].lower()
