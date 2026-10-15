import json
import unicodedata
import re
import difflib
import io
import zipfile
from pathlib import Path
from fastapi import FastAPI, HTTPException, Response
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

STOPWORDS_TITULO = {
    "a", "agora", "ai", "ainda", "algo", "algum", "alguma", "as", "ate", "bem",
    "boa", "bom", "cada", "cara", "coisa", "com", "como", "consegue", "da", "das",
    "de", "dela", "dele", "deles", "demais", "depois", "do", "dos", "e", "ela",
    "elas", "ele", "eles", "em", "entao", "essa", "essas", "esse", "esses", "esta",
    "estao", "estar", "estas", "estava", "este", "estes", "eu", "foi", "for",
    "fazer", "faz", "faco", "gostaria", "hoje", "isso", "isto", "ja", "la", "mais",
    "mas", "me", "mesmo", "meu", "meus", "minha", "minhas", "muito", "na", "nada",
    "nao", "nas", "nem", "nenhum", "nessa", "nesse", "no", "nos", "nossa", "nosso",
    "num", "numa", "o", "ola", "olha", "oi", "onde", "ontem", "os", "ou", "para", "pra",
    "pela", "pelas", "pelo", "pelos", "pode", "podem", "poderia", "por", "porque",
    "qual", "quando", "quanto", "quase", "quero", "queria", "saber", "se", "sem",
    "sera", "ser", "seu", "seus", "sim", "sobre", "so", "sou", "tambem", "te",
    "tem", "tenho", "ter", "teu", "tinha", "tive", "tudo", "tu", "tua", "tuas",
    "que", "ta", "tava",
    "um", "uma", "umas", "uns", "vai", "vamos", "vc", "ve", "ver", "vi", "voce",
    "voces", "vou", "quer", "preciso", "precisa", "ajuda", "ajudar", "diga", "diz",
    "conte", "explica", "explique", "meu", "minha", "dicas", "dica",
}


def gerar_titulo_inteligente(mensagem: str) -> str:
    palavras = re.findall(r"\w+", mensagem.casefold(), flags=re.UNICODE)
    palavras_finais = []
    palavras_vistas = set()

    for palavra in palavras:
        normalizada = normalizar_texto(palavra)
        if len(normalizada) < 3 or normalizada in STOPWORDS_TITULO or normalizada in palavras_vistas:
            continue
        palavras_finais.append(palavra.capitalize())
        palavras_vistas.add(normalizada)
        if len(palavras_finais) == 5:
            break

    return " ".join(palavras_finais) if palavras_finais else "Nova conversa"


def gerar_titulo_conversa(mensagens: list) -> str:
    mensagens_usuario = [
        mensagem.get("content", "")
        for mensagem in mensagens
        if mensagem.get("role") == "user" and isinstance(mensagem.get("content"), str)
    ]
    if not mensagens_usuario:
        return "Nova conversa"

    # Prefere a mensagem com mais palavras úteis, para um "oi" inicial não fixar o título.
    candidata = max(
        mensagens_usuario,
        key=lambda texto: sum(
            1 for palavra in re.findall(r"\w+", texto.casefold(), flags=re.UNICODE)
            if len(normalizar_texto(palavra)) >= 3
            and normalizar_texto(palavra) not in STOPWORDS_TITULO
        ),
    )
    return gerar_titulo_inteligente(candidata)

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

class AtualizarRespostaRequest(BaseModel):
    perguntas: list[str]
    resposta: str

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
    titulo_sessao = gerar_titulo_conversa(historicos[req.session_id]["mensagens"])
    historicos[req.session_id]["titulo"] = titulo_sessao
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


@app.get("/respostas")
def obter_respostas():
    respostas = carregar_dados().get("respostas", [])
    resultado = []
    for indice, item in enumerate(respostas):
        if not isinstance(item, dict) or not isinstance(item.get("perguntas"), list):
            continue
        perguntas = [
            pergunta.strip()
            for pergunta in item["perguntas"]
            if isinstance(pergunta, str) and pergunta.strip()
        ]
        resposta = item.get("resposta")
        if (
            perguntas
            and isinstance(resposta, str)
            and resposta.strip()
            and not resposta.startswith("Ainda estou a processar informações")
        ):
            resultado.append({
                "id": indice,
                "perguntas": perguntas,
                "resposta": resposta,
            })
    return resultado


@app.put("/respostas/{resposta_id}")
def atualizar_resposta(resposta_id: int, req: AtualizarRespostaRequest):
    dados = carregar_dados()
    respostas = dados.get("respostas", [])
    if resposta_id < 0 or resposta_id >= len(respostas):
        raise HTTPException(status_code=404, detail="Resposta não encontrada.")

    perguntas = list(dict.fromkeys(
        pergunta.strip() for pergunta in req.perguntas if pergunta.strip()
    ))
    resposta = req.resposta.strip()
    if not perguntas or not resposta:
        raise HTTPException(status_code=422, detail="Informe ao menos uma pergunta e uma resposta.")

    respostas[resposta_id] = {"perguntas": perguntas, "resposta": resposta}
    salvar_dados(dados)
    return {"status": "sucesso", "mensagem": "Resposta atualizada."}


@app.delete("/respostas/{resposta_id}")
def deletar_resposta(resposta_id: int):
    dados = carregar_dados()
    respostas = dados.get("respostas", [])
    if resposta_id < 0 or resposta_id >= len(respostas):
        raise HTTPException(status_code=404, detail="Resposta não encontrada.")

    del respostas[resposta_id]
    salvar_dados(dados)
    return {"status": "sucesso", "mensagem": "Resposta removida da base local."}


@app.get("/backup")
def baixar_backup():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as arquivo_zip:
        for caminho in (ARQUIVO_DADOS, ARQUIVO_HISTORICOS):
            conteudo = caminho.read_bytes() if caminho.exists() else b"{}\n"
            arquivo_zip.writestr(caminho.name, conteudo)

    return Response(
        content=buffer.getvalue(),
        media_type="application/zip",
        headers={"Content-Disposition": 'attachment; filename="chatbot-backup.zip"'},
    )


# --- NOVA ROTA: Deletar Sessão do Histórico ---
@app.delete("/historicos/{session_id}")
def deletar_historico(session_id: str):
    historicos = carregar_historicos_salvos()
    
    if session_id in historicos:
        del historicos[session_id]
        salvar_historicos_salvos(historicos)
        return {"status": "sucesso", "mensagem": f"Sessão {session_id} eliminada com sucesso."}
    
    raise HTTPException(status_code=404, detail="Sessão não encontrada.")