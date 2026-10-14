from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(
    title="Chatbot API",
    description="Backend para processamento e orquestração do Chatbot",
    version="1.0.0"
)

# Modelo para validar os dados que chegam no POST
class MensagemUsuario(BaseModel):
    user_id: str
    mensagem: str

# Modelo da resposta que o backend vai devolver
class RespostaBot(BaseModel):
    user_id: str
    resposta: str
    status: str

@app.get("/")
def home():
    return {"status": "API do Chatbot rodando com sucesso!"}

@app.post("/chat", response_model=RespostaBot)
def processar_chat(dados: MensagemUsuario):
    # Aqui é onde entra a lógica: chamada de IA (LLM/LangChain), busca em banco, etc.
    texto_usuario = dados.mensagem.lower()
    
    # Exemplo simples de resposta processada no servidor
    resposta_gerada = f"Recebi sua mensagem: '{dados.mensagem}'. O backend está pronto para processar isso!"
    
    return {
        "user_id": dados.user_id,
        "resposta": resposta_gerada,
        "status": "sucesso"
    }