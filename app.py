import streamlit as st
import requests
import uuid

# Configuração da página
st.set_page_config(
    page_title="Chatbot Local",
    page_icon="💬",
    layout="wide"
)

API_URL = "http://127.0.0.1:8000"

# --- CSS Avançado para Fundir as Colunas numa Única Caixa Contínua ---
st.markdown("""
<style>
    /* Estilo do Medidor de Desempenho no Canto Superior Direito */
    .medidor-box {
        padding: 8px 14px;
        border-radius: 8px;
        font-size: 13px;
        font-weight: 500;
        display: inline-block;
        float: right;
        margin-top: -10px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        background-color: rgba(255, 255, 255, 0.03);
    }

    /* Remove espaçamentos e margens das colunas na sidebar para colá-las */
    [data-testid="stSidebar"] [data-testid="column"] {
        padding: 0px !important;
        margin: 0px !important;
    }
    
    /* Define larguras exatas para as colunas ficarem juntas */
    [data-testid="stSidebar"] [data-testid="column"]:nth-of-type(1) {
        width: 82% !important;
        flex: 82% !important;
    }

    [data-testid="stSidebar"] [data-testid="column"]:nth-of-type(2) {
        width: 18% !important;
        flex: 18% !important;
    }

    /* Altura e aspeto unificado para os botões */
    [data-testid="stSidebar"] div.stButton > button {
        border-radius: 0px !important;
        border: 1px solid rgba(255, 255, 255, 0.15) !important;
        background-color: transparent !important;
        height: 40px !important;
        margin: 0px !important;
    }

    /* Arredonda a ponta esquerda e remove a borda direita do título */
    [data-testid="stSidebar"] div[data-testid="column"]:nth-of-type(1) div.stButton > button {
        border-top-left-radius: 8px !important;
        border-bottom-left-radius: 8px !important;
        border-right: none !important;
        text-align: left !important;
        width: 100%;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }

    /* Arredonda a ponta direita e remove a borda esquerda do botão "X" */
    [data-testid="stSidebar"] div[data-testid="column"]:nth-of-type(2) div.stButton > button {
        border-top-right-radius: 8px !important;
        border-bottom-right-radius: 8px !important;
        border-left: none !important;
        color: #ff4b4b !important;
        font-weight: bold;
        width: 100%;
    }

    /* Efeito hover unificado para parecer uma caixa só */
    [data-testid="stSidebar"] div.stButton > button:hover {
        background-color: rgba(255, 255, 255, 0.05) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
    }
</style>
""", unsafe_allow_html=True)

# --- Inicialização do Estado da Sessão ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

if "pergunta_pendente" not in st.session_state:
    st.session_state.pergunta_pendente = None

# --- BARRA LATERAL (Histórico e Gestão) ---
st.sidebar.title("💬 Histórico de Conversas")

if st.sidebar.button("➕ Nova Conversa", use_container_width=True):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.mensagens = []
    st.session_state.pergunta_pendente = None
    st.rerun()

st.sidebar.markdown("---")

try:
    res = requests.get(f"{API_URL}/historicos", timeout=5)
    res.raise_for_status()
    historicos = res.json()
except requests.RequestException as e:
    historicos = {}
    st.sidebar.warning(f"Não foi possível carregar o histórico: {e}")

if historicos:
    st.sidebar.subheader("Conversas Guardadas")
    
    for sid, dados in list(historicos.items()):
        # Colunas com gap zero para colar os componentes
        col_titulo, col_deletar = st.sidebar.columns([0.82, 0.18], gap="small")
        titulo_sessao = dados.get("titulo", "Conversa sem título")
        
        # Botão esquerdo: Título
        if col_titulo.button(f"📄 {titulo_sessao}", key=f"select_{sid}"):
            st.session_state.session_id = sid
            st.session_state.mensagens = dados.get("mensagens", [])
            st.session_state.pergunta_pendente = dados.get("pergunta_pendente")
            st.rerun()
            
        # Botão direito: "X" colado na mesma moldura
        if col_deletar.button("✕", key=f"del_{sid}", help="Apagar conversa"):
            try:
                del_res = requests.delete(f"{API_URL}/historicos/{sid}", timeout=5)
                
                if del_res.status_code == 200:
                    if st.session_state.session_id == sid:
                        st.session_state.session_id = str(uuid.uuid4())
                        st.session_state.mensagens = []
                        st.session_state.pergunta_pendente = None
                    st.rerun()
                else:
                    st.sidebar.error(f"Erro ao apagar: {del_res.text}")
            except requests.RequestException as e:
                st.sidebar.error(f"Erro ao apagar: {e}")
else:
    st.sidebar.info("Nenhuma conversa guardada.")

# Restaura uma pergunta ainda não ensinada ao reabrir o app.
conversa_atual = historicos.get(st.session_state.session_id, {})
if conversa_atual.get("pergunta_pendente"):
    st.session_state.pergunta_pendente = conversa_atual["pergunta_pendente"]

# --- ÁREA PRINCIPAL DO CHAT ---

# Cálculo do Medidor de Sobrecarga
total_mensagens = len(st.session_state.mensagens)
total_caracteres = sum(len(m["content"]) for m in st.session_state.mensagens)

if total_caracteres < 3000 and total_mensagens < 15:
    status_cor = "#2ea043"
    status_texto = "🟢 Fluidez: Excelente (Rápido)"
elif total_caracteres < 8000 and total_mensagens < 30:
    status_cor = "#d29922"
    status_texto = "🟡 Carga: Moderada"
else:
    status_cor = "#f85149"
    status_texto = "🔴 Carga: Alta (Pode ficar lento)"

# Cabeçalho com o Medidor no Canto Superior Direito
col_header_esq, col_header_dir = st.columns([0.65, 0.35])

with col_header_esq:
    st.title("🤖 Assistente Local")
    st.caption("Sistema 100% offline com autoaprendizagem e histórico inteligente.")

with col_header_dir:
    st.markdown(
        f'<div class="medidor-box" style="border-color: {status_cor}; color: {status_cor};">'
        f'{status_texto}'
        f'</div>',
        unsafe_allow_html=True
    )

st.markdown("---")

# Exibe o histórico de mensagens da sessão ativa
for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

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
if prompt := st.chat_input("Escreve a tua mensagem..."):
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
        if dados_resposta["precisa_ensino"]:
            st.session_state.pergunta_pendente = prompt
        st.rerun()
    except requests.RequestException as e:
        st.error(f"Não foi possível conectar ao servidor backend: {e}")