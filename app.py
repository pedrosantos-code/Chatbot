import streamlit as st
import requests
import uuid

# Configuração da página
st.set_page_config(
    page_title="Chatbot Local",
    page_icon="💬",
    layout="wide"
)

API_URL = "http://localhost:8000"

# --- Inicialização do Estado da Sessão ---
if "session_id" not in st.session_state:
    st.session_state.session_id = str(uuid.uuid4())

if "mensagens" not in st.session_state:
    st.session_state.mensagens = []

# --- BARRA LATERAL (Histórico e Gestão) ---
st.sidebar.title("💬 Histórico de Conversas")

# Botão para criar uma nova conversa
if st.sidebar.button("➕ Nova Conversa", use_container_width=True):
    st.session_state.session_id = str(uuid.uuid4())
    st.session_state.mensagens = []
    st.rerun()

st.sidebar.markdown("---")

# Procura o histórico guardado no backend
try:
    res = requests.get(f"{API_URL}/historicos")
    if res.status_code == 200:
        historicos = res.json()
    else:
        historicos = {}
except Exception:
    historicos = {}
    st.sidebar.warning("⚠️ Não foi possível ligar ao backend.")

# Lista de Históricos na Sidebar com Popover de Opções (⋮)
if historicos:
    st.sidebar.subheader("Conversas Guardadas")
    
    for sid, dados in list(historicos.items()):
        # Layout de 2 colunas: o chat principal ocupa o espaço maior e o popover fica alinhado à direita
        col_titulo, col_menu = st.sidebar.columns([0.82, 0.18])
        
        titulo_sessao = dados.get("titulo", "Conversa sem título")
        
        # Botão para carregar a conversa selecionada
        if col_titulo.button(f"📄 {titulo_sessao}", key=f"select_{sid}", use_container_width=True):
            st.session_state.session_id = sid
            st.session_state.mensagens = dados.get("mensagens", [])
            st.rerun()
            
        # Popover com os três pontos (⋮) idêntico ao da imagem
        with col_menu:
            with st.popover("⋮", help="Opções da conversa"):
                st.caption(f"ID: {sid[:6]}...")
                
                # Botão interno para apagar a conversa dentro do popover
                if st.button("🗑️ Apagar Conversa", key=f"del_{sid}", use_container_width=True):
                    try:
                        del_res = requests.delete(f"{API_URL}/historicos/{sid}")
                        
                        if del_res.status_code == 200:
                            if st.session_state.session_id == sid:
                                st.session_state.session_id = str(uuid.uuid4())
                                st.session_state.mensagens = []
                            st.rerun()
                        else:
                            st.error("Erro ao apagar.")
                    except Exception as e:
                        st.error(f"Erro: {e}")
else:
    st.sidebar.info("Nenhuma conversa guardada.")

# --- ÁREA PRINCIPAL DO CHAT ---
st.title("🤖 Assistente Local")
st.caption("Sistema 100% offline com autoaprendizagem e histórico inteligente.")

# Exibe o histórico de mensagens da sessão ativa
for msg in st.session_state.mensagens:
    with st.chat_message(msg["role"]):
        st.write(msg["content"])

# Caixa de texto para envio de mensagens
if prompt := st.chat_input("Escreve a tua mensagem..."):
    st.session_state.mensagens.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.write(prompt)

    payload = {
        "session_id": st.session_state.session_id,
        "mensagem": prompt,
        "historico": st.session_state.mensagens
    }

    try:
        response = requests.post(f"{API_URL}/chat", json=payload)
        
        if response.status_code == 200:
            dados_resposta = response.json()
            resposta_bot = dados_resposta["resposta"]
            
            with st.chat_message("assistant"):
                st.write(resposta_bot)
                
            st.session_state.mensagens.append({"role": "assistant", "content": resposta_bot})
            st.rerun()
        else:
            st.error("Ocorreu um erro ao processar a resposta no backend.")
            
    except Exception as e:
        st.error(f"Não foi possível conectar ao servidor backend: {e}")