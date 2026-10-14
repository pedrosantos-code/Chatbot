import json
import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import difflib

app = FastAPI(
    title="Chatbot com Autoaprendizagem Local",
    description="Backend offline que aprende e atualiza o JSON sozinho",
    version="2.0.0"
)

ARQUIVO_DADOS = "dados.json"

def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"respostas": []}

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

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
    return {"status": "Backend com autoaprendizagem ativo!"}

@app.post("/chat", response_model=ChatResponse)
def processar_chat(req: ChatRequest):
    try:
        dados = carregar_dados()
        mensagem_usuario = req.mensagem.lower().strip()
        
        melhor_resposta = None
        maior_pontuacao = 0.0

        # Procura correspondência no JSON existente
        for item in dados.get("respostas", []):
            for p in item["perguntas"]:
                pontuacao = difflib.SequenceMatcher(None, mensagem_usuario, p.lower()).ratio()
                if pontuacao > maior_pontuacao:
                    maior_pontuacao = pontuacao
                    melhor_resposta = item["resposta"]

        # Se encontrou com boa precisão, retorna
        if maior_pontuacao >= 0.4:
            return ChatResponse(user_id=req.user_id, resposta=melhor_resposta, status="sucesso")

        # SE NÃO ENCONTROU: O chatbot "aprende" e guarda a nova pergunta no JSON automaticamente!
        nova_entrada = {
            "perguntas": [mensagem_usuario],
            "resposta": f"Ainda não tenho uma resposta perfeita para '{req.mensagem}', mas já registei esta pergunta na minha base de dados local para aprender!"
        }
        
        dados["respostas"].append(nova_entrada)
        salvar_dados(dados)  # Atualiza o arquivo físico .json na hora!

        resposta_aprendido = f"Interessante! Não sabia disso. Anotei a tua pergunta ('{req.mensagem}') no meu arquivo JSON. Da próxima vez já saberei responder!"

        return ChatResponse(
            user_id=req.user_id,
            resposta=resposta_aprendido,
            status="aprendido"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))