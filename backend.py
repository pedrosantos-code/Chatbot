import json
import unicodedata
import re
import difflib
from pathlib import Path
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

app = FastAPI(
    title="Chatbot Local com Títulos Inteligentes e Gestão de Histórico",
    description="Backend offline com filtragem de aberturas, autoaprendizagem, histórico persistente e exclusão de sessões",
    version="3.0.0"
)

PASTA_DADOS = Path(__file__).resolve().parent
ARQUIVO_DADOS = PASTA_DADOS / "dados.json"
ARQUIVO_HISTORICOS = PASTA_DADOS / "historicos.json"
RESPOSTA_DESCONHECIDA = "Ainda não sei responder isso. Você pode me ensinar uma resposta abaixo."


def carregar_json(caminho: Path, padrao):
    if not caminho.exists():
        return padrao
    with caminho.open("r", encoding="utf-8") as arquivo:
        return json.load(arquivo)


def salvar_json(caminho: Path, dados):
    temporario = caminho.with_suffix(caminho.suffix + ".tmp")
    with temporario.open("w", encoding="utf-8") as arquivo:
        json.dump(dados, arquivo, ensure_ascii=False, indent=4)
    temporario.replace(caminho)


def carregar_dados():
    return carregar_json(ARQUIVO_DADOS, {"respostas": []})


def salvar_dados(dados):
    salvar_json(ARQUIVO_DADOS, dados)


def carregar_historicos_salvos():
    return carregar_json(ARQUIVO_HISTORICOS, {})


def salvar_historicos_salvos(historicos):
    salvar_json(ARQUIVO_HISTORICOS, historicos)


def normalizar_texto(texto: str) -> str:
    texto = unicodedata.normalize("NFKD", texto.casefold())
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return re.sub(r"[^\w\s]", " ", texto).strip()


def buscar_resposta(pergunta: str, respostas: list) -> str | None:
    pergunta_normalizada = normalizar_texto(pergunta)
    melhor_resposta = None
    maior_pontuacao = 0.0

    for item in respostas:
        if not isinstance(item, dict):
            continue
        resposta = item.get("resposta", "")
        if not isinstance(resposta, str) or resposta.startswith("Ainda estou a processar informações"):
            continue

        for pergunta_salva in item.get("perguntas", []):
            if not isinstance(pergunta_salva, str):
                continue
            salva_normalizada = normalizar_texto(pergunta_salva)
            if not salva_normalizada:
                continue
            if pergunta_normalizada == salva_normalizada:
                return resposta

            palavras_pergunta = set(pergunta_normalizada.split())
            palavras_salvas = set(salva_normalizada.split())
            uniao = palavras_pergunta | palavras_salvas
            similaridade_palavras = len(palavras_pergunta & palavras_salvas) / len(uniao) if uniao else 0.0
            similaridade_texto = difflib.SequenceMatcher(
                None, pergunta_normalizada, salva_normalizada, autojunk=False
            ).ratio()
            pontuacao = 0.7 * similaridade_texto + 0.3 * similaridade_palavras
            if pontuacao > maior_pontuacao:
                maior_pontuacao = pontuacao
                melhor_resposta = resposta

    return melhor_resposta if maior_pontuacao >= 0.72 else None

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
class ChatRequest(BaseModel):
    session_id: str
    mensagem: str

class ChatResponse(BaseModel):
    resposta: str
    titulo_sessao: str
    precisa_ensino: bool

class EnsinoRequest(BaseModel):
    session_id: str
    pergunta: str
    resposta: str

class EnsinoResponse(BaseModel):
    status: str
    mensagem: str

# --- Rotas da API ---
@app.get("/")
def home():
    return {"status": "Backend local funcionando."}

@app.post("/chat", response_model=ChatResponse)
def processar_chat(req: ChatRequest):
    mensagem_usuario = req.mensagem.strip()
    if not mensagem_usuario:
        raise HTTPException(status_code=422, detail="A mensagem não pode ficar vazia.")

    resposta_final = buscar_resposta(mensagem_usuario, carregar_dados().get("respostas", []))
    precisa_ensino = resposta_final is None
    if precisa_ensino:
        resposta_final = RESPOSTA_DESCONHECIDA

    historicos = carregar_historicos_salvos()
    if req.session_id not in historicos:
        titulo_sessao = gerar_titulo_inteligente(mensagem_usuario)
        historicos[req.session_id] = {"titulo": titulo_sessao, "mensagens": []}
    else:
        titulo_sessao = historicos[req.session_id]["titulo"]

    if precisa_ensino:
        historicos[req.session_id]["pergunta_pendente"] = mensagem_usuario

    historicos[req.session_id]["mensagens"].extend([
        {"role": "user", "content": mensagem_usuario},
        {"role": "assistant", "content": resposta_final},
    ])
    salvar_historicos_salvos(historicos)

    return ChatResponse(
        resposta=resposta_final,
        titulo_sessao=titulo_sessao,
        precisa_ensino=precisa_ensino,
    )


@app.post("/ensinar", response_model=EnsinoResponse)
def ensinar_resposta(req: EnsinoRequest):
    pergunta = req.pergunta.strip()
    resposta = req.resposta.strip()
    if not pergunta or not resposta:
        raise HTTPException(status_code=422, detail="Pergunta e resposta são obrigatórias.")

    dados = carregar_dados()
    itens = dados.setdefault("respostas", [])
    pergunta_normalizada = normalizar_texto(pergunta)
    item_existente = next(
        (
            item for item in itens
            if isinstance(item, dict)
            and any(
                isinstance(salva, str) and normalizar_texto(salva) == pergunta_normalizada
                for salva in item.get("perguntas", [])
            )
        ),
        None,
    )
    if item_existente:
        item_existente["resposta"] = resposta
    else:
        itens.append({"perguntas": [pergunta], "resposta": resposta})
    salvar_dados(dados)

    historicos = carregar_historicos_salvos()
    conversa = historicos.get(req.session_id)
    if conversa:
        historico_alterado = False
        if conversa.get("pergunta_pendente") == pergunta:
            conversa.pop("pergunta_pendente")
            historico_alterado = True
        mensagens = conversa.get("mensagens", [])
        for indice in range(len(mensagens) - 2, -1, -1):
            if (
                mensagens[indice].get("role") == "user"
                and mensagens[indice].get("content") == pergunta
                and indice + 1 < len(mensagens)
                and mensagens[indice + 1].get("role") == "assistant"
                and mensagens[indice + 1].get("content") == RESPOSTA_DESCONHECIDA
            ):
                mensagens[indice + 1]["content"] = "Aprendi essa resposta e vou usá-la nas próximas conversas."
                historico_alterado = True
                break
        if historico_alterado:
            salvar_historicos_salvos(historicos)

    return EnsinoResponse(status="sucesso", mensagem="Aprendi! Vou usar essa resposta nas próximas conversas.")

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