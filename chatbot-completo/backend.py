import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import difflib

app = FastAPI(
    title="Chatbot Local Inteligente",
    description="Backend offline baseado em JSON e similaridade de texto",
    version="1.0.0"
)

# Carrega a base de dados do JSON
def carregar_dados():
    if os.path.exists("dados.json"):
        with open("dados.json", "r", encoding="utf-8") as f:
            return json.load(f)
    return {"respostas": []}

class MensagemHistorico(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    user_id: str
    mensagem: str
    historico: Optional[List[MensagemHistorico]] = []

class ChatResponse(BaseModel):
    user_id: str
    resposta: str
    status: str

@app.get("/")
def home():
    return {"status": "Backend local a rodar com sucesso!"}

@app.post("/chat", response_model=ChatResponse)
def processar_chat(req: ChatRequest):
    try:
        dados = carregar_dados()
        mensagem_usuario = req.mensagem.lower().strip()
        
        melhor_resposta = "Não tenho a certeza sobre isso, mas podes adicionar essa pergunta ao meu arquivo JSON de dados!"
        maior_pontuacao = 0.0

        # Procura a melhor correspondência nas perguntas cadastradas
        for item in dados.get("respostas", []):
            for p in item["perguntas"]:
                # Calcula a similaridade entre o texto do usuário e as perguntas conhecidas
                pontuacao = difflib.SequenceMatcher(None, mensagem_usuario, p.lower()).ratio()
                if pontuacao > maior_pontuacao:
                    maior_pontuacao = pontuacao
                    melhor_resposta = item["resposta"]

        # Se a similaridade for muito baixa, dá uma resposta genérica amigável
        if maior_pontuacao < 0.3:
            melhor_resposta = f"Entendi a tua mensagem sobre '{req.mensagem}'. Como posso ajudar-te mais em relação a isso?"

        return ChatResponse(
            user_id=req.user_id,
            resposta=melhor_resposta,
            status="sucesso"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))