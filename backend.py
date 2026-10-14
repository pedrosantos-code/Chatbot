import json
import os
import re
import difflib
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional

app = FastAPI(
    title="Chatbot Local com Títulos Inteligentes e Gestão de Histórico",
    description="Backend offline com filtragem de aberturas, autoaprendizagem, histórico persistente e exclusão de sessões",
    version="3.0.0"
)

ARQUIVO_DADOS = "dados.json"
ARQUIVO_HISTORICOS = "historicos.json"

# --- Funções Auxiliares de Dados e Histórico ---
def carregar_dados():
    if os.path.exists(ARQUIVO_DADOS):
        with open(ARQUIVO_DADOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"respostas": []}

def salvar_dados(dados):
    with open(ARQUIVO_DADOS, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=4)

def carregar_historicos_salvos():
    if os.path.exists(ARQUIVO_HISTORICOS):
        with open(ARQUIVO_HISTORICOS, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}

def salvar_historicos_salvos(historicos):
    with open(ARQUIVO_HISTORICOS, "w", encoding="utf-8") as f:
        json.dump(historicos, f, ensure_ascii=False, indent=4)

# --- Função Inteligente de Títulos com Salto de Abertura ---
def gerar_titulo_inteligente(mensagem: str) -> str:
    msg = re.sub(r'[^\w\s]', '', mensagem).lower().strip()
    
    if not msg:
        return "Nova Conversa"

    palavras = msg.split()
    
    if len(palavras) <= 2:
        return " ".join([p.capitalize() for p in palavras])

    aberturas_para_ignorar = {"cara", "mano", "eu", "olha", "será", "tinha", "estás", "tu", "vc", "meu", "bem"}
    
    while palavras and palavras[0] in aberturas_para_ignorar:
        palavras.pop(0)

    if not palavras:
        palavras = msg.split()

    stopwords = {
        "a", "o", "e", "é", "de", "do", "da", "em", "um", "uma", "para", "com", 
        "não", "os", "as", "no", "na", "por", "mais", "dos", "das", "mas", 
        "foi", "ao", "ele", "ela", "seu", "sua", "ou", "quando", "muito", 
        "nos", "já", "também", "só", "pelo", "pela", "até", "esse", "isso", 
        "num", "numa", "qual", "onde", "meu", "minha", "teu", "tua", "vou", "que",
        "tava", "tá", "vi", "consegue", "me", "ver", "com", "ir", "dar", "uma", "hoje"
    }

    palavras_filtradas = [p for p in palavras if p not in stopwords and len(p) > 3]
    
    if not palavras_filtradas:
        palavras_finais = palavras[:3]
    else:
        palavras_unicas = []
        for p in palavras_filtradas:
            if p not in palavras_unicas:
                palavras_unicas.append(p)
        palavras_finais = palavras_unicas[:3]

    return " ".join([p.capitalize() for p in palavras_finais])

# --- Modelos Pydantic ---
class MensagemHistorico(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    session_id: str
    mensagem: str
    historico: Optional[List[MensagemHistorico]] = []

class ChatResponse(BaseModel):
    resposta: str
    titulo_sessao: str

# --- Rotas da API ---
@app.get("/")
def home():
    return {"status": "Backend com gestão de histórico a funcionar com sucesso!"}

@app.post("/chat", response_model=ChatResponse)
def processar_chat(req: ChatRequest):
    try:
        dados = carregar_dados()
        mensagem_usuario = req.mensagem.lower().strip()
        
        melhor_resposta = None
        maior_pontuacao = 0.0

        for item in dados.get("respostas", []):
            for p in item["perguntas"]:
                pontuacao = difflib.SequenceMatcher(None, mensagem_usuario, p.lower()).ratio()
                if pontuacao > maior_pontuacao:
                    maior_pontuacao = pontuacao
                    melhor_resposta = item["resposta"]

        if maior_pontuacao >= 0.4:
            resposta_final = melhor_resposta
        else:
            nova_entrada = {
                "perguntas": [mensagem_usuario],
                "resposta": f"Ainda estou a processar informações sobre '{req.mensagem}', mas registei este tema na minha base de dados local."
            }
            dados["respostas"].append(nova_entrada)
            salvar_dados(dados)
            
            resposta_final = f"Interessante! Adicionei a tua questão à minha base de dados local."

        historicos = carregar_historicos_salvos()
        
        if req.session_id not in historicos:
            titulo_sessao = gerar_titulo_inteligente(req.mensagem)
            historicos[req.session_id] = {
                "titulo": titulo_sessao,
                "mensagens": []
            }
        else:
            titulo_sessao = historicos[req.session_id]["titulo"]

        historicos[req.session_id]["mensagens"].append({"role": "user", "content": req.mensagem})
        historicos[req.session_id]["mensagens"].append({"role": "assistant", "content": resposta_final})
        salvar_historicos_salvos(historicos)

        return ChatResponse(
            resposta=resposta_final,
            titulo_sessao=titulo_sessao
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/historicos")
def obter_historicos():
    return carregar_historicos_salvos()

# --- NOVA ROTA: Deletar Sessão do Histórico ---
@app.delete("/historicos/{session_id}")
def deletar_historico(session_id: str):
    historicos = carregar_historicos_salvos()
    
    if session_id in historicos:
        del historicos[session_id]
        salvar_historicos_salvos(historicos)
        return {"status": "sucesso", "mensagem": f"Sessão {session_id} eliminada com sucesso."}
    
    raise HTTPException(status_code=404, detail="Sessão não encontrada.")