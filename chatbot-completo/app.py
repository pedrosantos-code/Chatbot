import streamlit as st
import requests

st.set_page_config(page_title="Chatbot Local", page_icon="🤖", layout="centered")

st.title("💬 Meu Chatbot Local")
st.write("Interface ligada ao backend em FastAPI sem chaves de API.")

if "messages" not in st.session_state:
    st.session_state.messages = []

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if prompt := st.chat_input("Escreve a tua mensagem..."):
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    payload = {
        "user_id": "pedro_santos",
        "mensagem": prompt,
        "historico": [{"role": m["role"], "content": m["content"]} for m in st.session_state.messages]
    }

    try:
        response = requests.post("http://127.0.0.1:8000/chat", json=payload)
        if response.status_code == 200:
            bot_resposta = response.json().get("resposta", "Sem resposta.")
        else:
            bot_resposta = "Erro ao comunicar com o servidor."
    except Exception:
        bot_resposta = "Não foi possível ligar ao FastAPI. Verifica se o servidor está ativo."

    st.session_state.messages.append({"role": "assistant", "content": bot_resposta})
    with st.chat_message("assistant"):
        st.markdown(bot_resposta)