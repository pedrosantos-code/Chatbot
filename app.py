import uuid
import unicodedata

import requests
import streamlit as st

# Configuração da página
st.set_page_config(
    page_title="Chatbot Local",
    page_icon="💬",
    layout="wide"
)

API_URL = "http://127.0.0.1:8000"


def iniciar_conversa_nova() -> None:
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.mensagens = []
    st.session_state.pergunta_pendente = None
    st.session_state.confirmacao_pendente = None
    st.session_state.desambiguacao_pendente = None


def normalizar_busca(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    return "".join(
        caractere for caractere in texto
        if not unicodedata.combining(caractere)
    )


def conversa_corresponde(dados: dict, consulta: str) -> bool:
    termos = normalizar_busca(consulta.strip()).split()
    if not termos:
        return True

    conteudo = [dados.get("titulo", "")]
    conteudo.extend(
        mensagem.get("content", "")
        for mensagem in dados.get("mensagens", [])
        if isinstance(mensagem, dict)
    )
    historico_normalizado = normalizar_busca(
        " ".join(texto for texto in conteudo if isinstance(texto, str))
    )
    return all(termo in historico_normalizado for termo in termos)


def formatar_conversa(titulo: str, mensagens: list[dict], formato: str) -> str:
    linhas = [f"# {titulo}"] if formato == "md" else [titulo, "=" * len(titulo)]
    rotulos = {"user": "Você", "assistant": "Assistente"}

    for mensagem in mensagens:
        autor = rotulos.get(mensagem.get("role"), mensagem.get("role", "Mensagem"))
        conteudo = mensagem.get("content", "")
        if formato == "md":
            linhas.extend((f"## {autor}", "", conteudo, ""))
        else:
            linhas.extend((f"{autor}:", conteudo, ""))

    return "\n".join(linhas).rstrip() + "\n"


@st.dialog("Confirmar exclusão")
def confirmar_exclusao_conversa(session_id: str) -> None:
    st.warning("Tem certeza de que deseja apagar esta conversa? Esta ação não pode ser desfeita.")
    coluna_confirmar, coluna_cancelar = st.columns(2)

    if coluna_confirmar.button(
        "Sim, apagar",
        type="primary",
        use_container_width=True,
    ):
        try:
            resposta = requests.delete(
                f"{API_URL}/historicos/{session_id}",
                timeout=5,
            )
            resposta.raise_for_status()
            if st.session_state.session_id == session_id:
                iniciar_conversa_nova()
            st.session_state.conversa_para_apagar = None
            st.rerun()
        except requests.RequestException as erro:
            st.error(f"Não foi possível apagar a conversa: {erro}")

    if coluna_cancelar.button("Cancelar", use_container_width=True):
        st.session_state.conversa_para_apagar = None
        st.rerun()


# --- CSS Avançado para Fundir as Colunas numa Única Caixa Contínua ---
st.markdown("""
<style>
    /* Estilo do Medidor de Desempenho no Canto Superior Direito */
    .medidor-box {
        padding: 8px 12px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
        float: right;
        margin-top: -10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        background-color: rgba(255, 255, 255, 0.03);
        min-width: 190px;
    }

    .medidor-legenda {
        display: flex;
        justify-content: space-between;
        gap: 12px;
        margin-bottom: 6px;
        white-space: nowrap;
    }

    .medidor-trilha {
        position: relative;
        height: 7px;
        border-radius: 999px;
        background: linear-gradient(90deg, #2ea043 0%, #d29922 45%, #f0883e 72%, #f85149 100%);
    }

    .medidor-indicador {
        position: absolute;
        top: 50%;
        width: 13px;
        height: 13px;
        border: 2px solid #fff;
        border-radius: 50%;
        background: var(--medidor-cor);
        box-shadow: 0 0 0 1px rgba(0, 0, 0, 0.4);
        transform: translate(-50%, -50%);
        transition: left 250ms ease, background-color 250ms ease;
    }

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] div.stButton) {
        gap: 0 !important;
        border: 1px solid rgba(255, 255, 255, 0.15);
        border-radius: 8px;
        overflow: hidden;
    }

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] div.stButton) > [data-testid="column"] {
        padding: 0 !important;
        margin: 0 !important;
        min-width: 0;
    }

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] div.stButton) div.stButton > button {
        border: 0 !important;
        border-radius: 0 !important;
        background-color: transparent !important;
        height: 40px !important;
        width: 100%;
    }

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] div.stButton) > [data-testid="column"]:first-child div.stButton > button p {
        text-align: left;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] div.stButton) > [data-testid="column"]:last-child div.stButton > button {
        color: #ff4b4b !important;
        font-weight: bold;
    }

    [data-testid="stSidebar"] [data-testid="stHorizontalBlock"]:has(> [data-testid="column"] div.stButton) div.stButton > button:hover {
        background-color: rgba(255, 255, 255, 0.05) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Inicialização do Estado da Sessão ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

st.session_state.setdefault("mensagens", [])
st.session_state.setdefault("pergunta_pendente", None)
st.session_state.setdefault("confirmacao_pendente", None)
st.session_state.setdefault("desambiguacao_pendente", None)
st.session_state.setdefault("conversa_para_apagar", None)

# --- BARRA LATERAL (Histórico e Gestão) ---
st.sidebar.title("💬 Histórico de Conversas")

if st.sidebar.button("➕ Nova Conversa", use_container_width=True):
    iniciar_conversa_nova()
    st.rerun()

st.sidebar.markdown("---")

try:
    res = requests.get(f"{API_URL}/historicos", timeout=5)
    res.raise_for_status()
    historicos = res.json()
except requests.RequestException as e:
    historicos = {}
    st.sidebar.warning(f"Não foi possível carregar o histórico: {e}")

st.sidebar.subheader("Conversas Guardadas")
consulta_historico = st.sidebar.text_input(
    "Pesquisar no histórico",
    placeholder="Busque por título ou mensagem",
)
conversas_filtradas = {
    sid: dados
    for sid, dados in historicos.items()
    if conversa_corresponde(dados, consulta_historico)
}

if conversas_filtradas:
    for sid, dados in conversas_filtradas.items():
        col_titulo, col_deletar = st.sidebar.columns([0.82, 0.18], gap=None)
        titulo_sessao = dados.get("titulo", "Conversa sem título")

        if col_titulo.button(
            f"📄 {titulo_sessao}",
            key=f"select_{sid}",
            help=titulo_sessao,
            use_container_width=True,
        ):
            st.session_state.session_id = sid
            st.session_state.mensagens = dados.get("mensagens", [])
            st.session_state.pergunta_pendente = dados.get("pergunta_pendente")
            st.session_state.confirmacao_pendente = dados.get("confirmacao_pendente")
            st.session_state.desambiguacao_pendente = dados.get("desambiguacao_pendente")
            st.rerun()

        if col_deletar.button(
            "✕",
            key=f"del_{sid}",
            help="Apagar conversa",
            use_container_width=True,
        ):
            st.session_state.conversa_para_apagar = sid
            st.rerun()
elif historicos:
    st.sidebar.info("Nenhuma conversa corresponde à pesquisa.")
else:
    st.sidebar.info("Nenhuma conversa guardada.")

if st.session_state.conversa_para_apagar:
    confirmar_exclusao_conversa(st.session_state.conversa_para_apagar)

with st.sidebar.expander("📥 Exportar conversa atual"):
    formato_exportacao = st.selectbox(
        "Formato",
        options=["md", "txt"],
        format_func=lambda formato: "Markdown (.md)" if formato == "md" else "Texto (.txt)",
    )
    titulo_exportacao = historicos.get(
        st.session_state.session_id, {}
    ).get("titulo", "Conversa atual")
    conteudo_exportacao = formatar_conversa(
        titulo_exportacao,
        st.session_state.mensagens,
        formato_exportacao,
    )
    st.download_button(
        f"Baixar conversa .{formato_exportacao}",
        data=conteudo_exportacao,
        file_name=f"conversa-atual.{formato_exportacao}",
        mime="text/markdown" if formato_exportacao == "md" else "text/plain",
        disabled=not st.session_state.mensagens,
        use_container_width=True,
    )

with st.sidebar.expander("🧠 Base de respostas e backup"):
    try:
        respostas_res = requests.get(f"{API_URL}/respostas", timeout=5)
        respostas_res.raise_for_status()
        respostas_salvas = respostas_res.json()
    except requests.RequestException as e:
        respostas_salvas = []
        st.error(f"Não foi possível carregar as respostas: {e}")

    if respostas_salvas:
        ids_respostas = [item["id"] for item in respostas_salvas]
        resposta_id = st.selectbox(
            "Resposta para revisar",
            options=ids_respostas,
            format_func=lambda item_id: ", ".join(
                next(item["perguntas"] for item in respostas_salvas if item["id"] == item_id)
            )[:50],
        )
        resposta_selecionada = next(
            item for item in respostas_salvas if item["id"] == resposta_id
        )

        with st.form(f"editar_resposta_{resposta_id}"):
            perguntas_editadas = st.text_area(
                "Perguntas (uma por linha)",
                value="\n".join(resposta_selecionada["perguntas"]),
            )
            texto_resposta = st.text_area(
                "Resposta",
                value=resposta_selecionada["resposta"],
            )
            salvar_edicao = st.form_submit_button(
                "Salvar alterações",
                use_container_width=True,
            )

        if salvar_edicao:
            try:
                edicao_res = requests.put(
                    f"{API_URL}/respostas/{resposta_id}",
                    json={
                        "perguntas": perguntas_editadas.splitlines(),
                        "resposta": texto_resposta,
                    },
                    timeout=5,
                )
                edicao_res.raise_for_status()
                st.success("Resposta atualizada.")
                st.rerun()
            except requests.RequestException as e:
                st.error(f"Não foi possível salvar a alteração: {e}")

        confirmar_remocao = st.checkbox("Confirmar remoção desta resposta")
        if st.button(
            "Apagar resposta",
            disabled=not confirmar_remocao,
            use_container_width=True,
        ):
            try:
                remocao_res = requests.delete(
                    f"{API_URL}/respostas/{resposta_id}",
                    timeout=5,
                )
                remocao_res.raise_for_status()
                st.success("Resposta removida.")
                st.rerun()
            except requests.RequestException as e:
                st.error(f"Não foi possível apagar a resposta: {e}")
    else:
        st.caption("Ainda não há respostas na base local para revisar.")

    st.link_button(
        "Baixar backup dos dados",
        url=f"{API_URL}/backup",
        help="Gera e baixa um ZIP com os dados e o histórico atuais.",
        use_container_width=True,
    )

# Restaura uma pergunta ainda não ensinada ao reabrir o app.
conversa_atual = historicos.get(st.session_state.session_id, {})
st.session_state.pergunta_pendente = conversa_atual.get("pergunta_pendente")
st.session_state.confirmacao_pendente = conversa_atual.get("confirmacao_pendente")
st.session_state.desambiguacao_pendente = conversa_atual.get("desambiguacao_pendente")

# --- ÁREA PRINCIPAL DO CHAT ---

# Estima o tamanho do histórico da conversa ativa.
total_mensagens = len(st.session_state.mensagens)
total_caracteres = sum(len(m["content"]) for m in st.session_state.mensagens)
carga = min(1.0, max(total_caracteres / 8000, total_mensagens / 30))
carga_percentual = round(carga * 100)
posicao_indicador = min(98, max(2, carga_percentual))

faixas_cor = [
    (0.0, (46, 160, 67)),
    (0.45, (210, 153, 34)),
    (0.72, (240, 136, 62)),
    (1.0, (248, 81, 73)),
]
for indice in range(len(faixas_cor) - 1):
    inicio, cor_inicio = faixas_cor[indice]
    fim, cor_fim = faixas_cor[indice + 1]
    if carga <= fim:
        proporcao = (carga - inicio) / (fim - inicio)
        rgb = tuple(
            round(a + (b - a) * proporcao)
            for a, b in zip(cor_inicio, cor_fim)
        )
        break
else:
    rgb = faixas_cor[-1][1]
status_cor = "#{:02x}{:02x}{:02x}".format(*rgb)

if carga < 0.35:
    status_texto = "Baixa"
elif carga < 0.7:
    status_texto = "Moderada"
elif carga < 0.9:
    status_texto = "Elevada"
else:
    status_texto = "Alta"

# Cabeçalho com o Medidor no Canto Superior Direito
col_header_esq, col_header_dir = st.columns([0.65, 0.35])

with col_header_esq:
    st.title("🤖 Assistente Local")
    st.caption("Sistema 100% offline com autoaprendizagem e histórico inteligente.")

with col_header_dir:
    st.markdown(
        f'<div class="medidor-box" title="Indicador do tamanho do histórico desta conversa; não mede a inteligência do chatbot." '
        f'style="border-color: {status_cor}; --medidor-cor: {status_cor};">'
        f'<div class="medidor-legenda" style="color: {status_cor};">'
        f'<span>Histórico: {status_texto}</span><span>{carga_percentual}%</span></div>'
        f'<div class="medidor-trilha"><span class="medidor-indicador" '
        f'style="left: {posicao_indicador}%;"></span></div>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.markdown("---")

# Exibe o histórico de mensagens da sessão ativa
for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

if st.session_state.desambiguacao_pendente:
    pendente = st.session_state.desambiguacao_pendente
    st.info(
        f"Encontrei respostas diferentes para: **{pendente['pergunta']}**. "
        "Qual delas você quis dizer?"
    )
    candidatas = pendente.get("candidatas", [])
    if candidatas:
        with st.form(f"desambiguar_{st.session_state.session_id}"):
            indice_escolhido = st.radio(
                "Escolha a resposta mais adequada",
                options=range(len(candidatas)),
                format_func=lambda indice: (
                    f"{candidatas[indice]['pergunta_base']}: "
                    f"{candidatas[indice]['resposta'][:180]}"
                ),
            )
            escolher_resposta = st.form_submit_button(
                "Usar esta resposta",
                use_container_width=True,
            )

        if escolher_resposta:
            try:
                selecao_res = requests.post(
                    f"{API_URL}/desambiguar-resposta",
                    json={
                        "session_id": st.session_state.session_id,
                        "indice": indice_escolhido,
                    },
                    timeout=5,
                )
                selecao_res.raise_for_status()
                dados_selecao = selecao_res.json()
                if (
                    st.session_state.mensagens
                    and st.session_state.mensagens[-1]["role"] == "assistant"
                ):
                    st.session_state.mensagens[-1]["content"] = dados_selecao["resposta"]
                st.session_state.desambiguacao_pendente = None
                st.toast("Obrigado! Vou lembrar que essa pergunta corresponde a esta resposta.")
                st.rerun()
            except requests.RequestException as e:
                st.error(f"Não foi possível registrar sua escolha: {e}")

if st.session_state.confirmacao_pendente:
    st.info("Encontrei essa resposta por semelhança. Ela responde à sua pergunta?")
    confirmar_coluna, negar_coluna = st.columns(2)
    confirmar_match = confirmar_coluna.button(
        "👍 Sim, serve",
        key=f"confirmar_{st.session_state.session_id}",
        use_container_width=True,
    )
    negar_match = negar_coluna.button(
        "👎 Não, ensinar outra",
        key=f"negar_{st.session_state.session_id}",
        use_container_width=True,
    )

    if confirmar_match or negar_match:
        try:
            avaliacao = requests.post(
                f"{API_URL}/confirmar-resposta",
                json={
                    "session_id": st.session_state.session_id,
                    "aceita": confirmar_match,
                },
                timeout=5,
            )
            avaliacao.raise_for_status()
            dados_avaliacao = avaliacao.json()
            if (
                st.session_state.mensagens
                and st.session_state.mensagens[-1]["role"] == "assistant"
            ):
                st.session_state.mensagens[-1]["content"] = dados_avaliacao["mensagem"]
            pergunta_confirmada = st.session_state.confirmacao_pendente["pergunta"]
            st.session_state.confirmacao_pendente = None
            st.session_state.pergunta_pendente = (
                pergunta_confirmada
                if dados_avaliacao["precisa_ensino"]
                else None
            )
            st.toast(dados_avaliacao["mensagem"])
            st.rerun()
        except requests.RequestException as e:
            st.error(f"Não foi possível registrar sua avaliação: {e}")

# Permite ensinar uma resposta sem adicionar conteúdo inventado à base de conhecimento.
if st.session_state.pergunta_pendente:
    st.info(f"Ainda não sei responder: **{st.session_state.pergunta_pendente}**")
    with st.form("ensinar_resposta"):
        nova_resposta = st.text_area("Qual seria a resposta correta?")
        ensinar = st.form_submit_button("Ensinar resposta")

    if ensinar:
        try:
            resposta_ensino = requests.post(
                f"{API_URL}/ensinar",
                json={
                    "session_id": st.session_state.session_id,
                    "pergunta": st.session_state.pergunta_pendente,
                    "resposta": nova_resposta,
                },
                timeout=5,
            )
            resposta_ensino.raise_for_status()
            dados_ensino = resposta_ensino.json()
            pergunta_ensinada = st.session_state.pergunta_pendente
            for indice in range(len(st.session_state.mensagens) - 2, -1, -1):
                if (
                    st.session_state.mensagens[indice]["role"] == "user"
                    and st.session_state.mensagens[indice]["content"] == pergunta_ensinada
                    and indice + 1 < len(st.session_state.mensagens)
                    and st.session_state.mensagens[indice + 1]["role"] == "assistant"
                ):
                    st.session_state.mensagens[indice + 1]["content"] = dados_ensino["mensagem"]
                    break
            st.session_state.pergunta_pendente = None
            st.toast(dados_ensino["mensagem"])
            st.rerun()
        except requests.RequestException as e:
            st.error(f"Não foi possível salvar o que você ensinou: {e}")

# Caixa de texto para envio de mensagens
if prompt := st.chat_input(
    "Escreve a tua mensagem...",
    disabled=bool(
        st.session_state.confirmacao_pendente
        or st.session_state.desambiguacao_pendente
        or st.session_state.pergunta_pendente
    ),
):
    payload = {
        "session_id": st.session_state.session_id,
        "mensagem": prompt,
    }

    try:
        with st.spinner("Pensando..."):
            response = requests.post(f"{API_URL}/chat", json=payload, timeout=15)
        response.raise_for_status()
        dados_resposta = response.json()
        resposta_bot = dados_resposta["resposta"]

        st.session_state.mensagens.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.write(prompt)
        with st.chat_message("assistant"):
            st.write(resposta_bot)

        st.session_state.mensagens.append({"role": "assistant", "content": resposta_bot})
        if dados_resposta["precisa_desambiguacao"]:
            st.session_state.desambiguacao_pendente = {
                "pergunta": prompt,
                "candidatas": dados_resposta["respostas_candidatas"],
            }
        elif dados_resposta["precisa_ensino"]:
            st.session_state.pergunta_pendente = prompt
        elif dados_resposta["precisa_confirmacao"]:
            st.session_state.confirmacao_pendente = {
                "pergunta": prompt,
            }
        st.rerun()
    except requests.RequestException as e:
        st.error(f"Não foi possível conectar ao servidor backend: {e}")