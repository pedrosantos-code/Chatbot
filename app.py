import streamlit as st
import requests

# Configuração da página Streamlit
st.set_page_config(page_title="Chatbot AI Assistant", page_icon="🤖", layout="centered")

BACKEND_URL = "http://127.0.0.1:8000/chat"

st.title("🤖 Chatbot AI Assistant")
st.caption("Interface Streamlit + Backend FastAPI + Gemini 2.5 Flash")

# Inicialização do histórico na sessão
if "messages" not in st.session_state:
    st.session_state["messages"] = []

# Exibe mensagens anteriores
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Entrada de texto do usuário
if user_input := st.chat_input("Digite sua mensagem..."):
    # Exibe a mensagem do usuário na tela
    st.session_state["messages"].append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # Formata o histórico anterior para enviar à API
    historico_api = []
    for m in st.session_state["messages"][:-1]:
        role_api = "user" if m["role"] == "user" else "model"
        historico_api.append({"role": role_api, "parts": [m["content"]]})

    # Chamada ao Backend FastAPI
    with st.chat_message("assistant"):
        with st.spinner("Pensando..."):
            try:
                payload = {
                    "user_id": "pedro_dev",
                    "mensagem": user_input,
                    "historico": historico_api
                }
                res = requests.post(BACKEND_URL, json=payload)

                if res.status_code == 200:
                    resposta_bot = res.json()["resposta"]
                    st.markdown(resposta_bot)
                    st.session_state["messages"].append({"role": "assistant", "content": resposta_bot})
                else:
                    st.error(f"Erro no servidor ({res.status_code}): {res.text}")
            except Exception as e:
                st.error(f"Não foi possível conectar ao Backend. Verifique se o FastAPI está ativo na porta 8000. Erro: {e}")