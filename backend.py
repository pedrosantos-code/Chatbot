import difflib
import io
import json
import re
import unicodedata
import zipfile
from pathlib import Path
from typing import TypedDict

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
LIMIAR_RESPOSTA_DIRETA = 0.86
LIMIAR_RESPOSTA_PARECIDA = 0.58
MARGEM_AMBIGUIDADE = 0.08


class Correspondencia(TypedDict):
    pergunta_base: str
    resposta: str
    pontuacao: float


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


def buscar_correspondencias(pergunta: str, respostas: list) -> list[Correspondencia]:
    pergunta_normalizada = normalizar_texto(pergunta)
    palavras_pergunta = set(pergunta_normalizada.split())
    por_resposta = {}

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
                pontuacao = 1.0
            else:
                palavras_salvas = set(salva_normalizada.split())
                uniao = palavras_pergunta | palavras_salvas
                similaridade_palavras = (
                    len(palavras_pergunta & palavras_salvas) / len(uniao) if uniao else 0.0
                )
                similaridade_texto = difflib.SequenceMatcher(
                    None, pergunta_normalizada, salva_normalizada, autojunk=False
                ).ratio()
                pontuacao = 0.7 * similaridade_texto + 0.3 * similaridade_palavras

            correspondencia = {
                "pergunta_base": pergunta_salva,
                "resposta": resposta,
                "pontuacao": pontuacao,
            }
            atual = por_resposta.get(resposta)
            if atual is None or pontuacao > atual["pontuacao"]:
                por_resposta[resposta] = correspondencia

    return sorted(por_resposta.values(), key=lambda item: item["pontuacao"], reverse=True)


def buscar_melhor_correspondencia(pergunta: str, respostas: list) -> dict | None:
    correspondencias = buscar_correspondencias(pergunta, respostas)
    return correspondencias[0] if correspondencias else None


def correspondencias_ambiguas(
    correspondencias: list[Correspondencia],
) -> list[Correspondencia]:
    if len(correspondencias) < 2:
        return []

    melhor_pontuacao = correspondencias[0]["pontuacao"]
    segunda_pontuacao = correspondencias[1]["pontuacao"]
    if (
        melhor_pontuacao < LIMIAR_RESPOSTA_PARECIDA
        or segunda_pontuacao < LIMIAR_RESPOSTA_PARECIDA
        or melhor_pontuacao - segunda_pontuacao > MARGEM_AMBIGUIDADE
    ):
        return []

    return [
        correspondencia
        for correspondencia in correspondencias
        if correspondencia["pontuacao"] >= LIMIAR_RESPOSTA_PARECIDA
        and melhor_pontuacao - correspondencia["pontuacao"] <= MARGEM_AMBIGUIDADE
    ][:3]


def encontrar_resposta_base(
    respostas: list,
    pergunta_base: str,
    resposta: str,
) -> dict | None:
    pergunta_base_normalizada = normalizar_texto(pergunta_base)
    for item in respostas:
        if not isinstance(item, dict) or item.get("resposta") != resposta:
            continue
        if any(
            isinstance(pergunta, str)
            and normalizar_texto(pergunta) == pergunta_base_normalizada
            for pergunta in item.get("perguntas", [])
        ):
            return item
    return None


def buscar_resposta(pergunta: str, respostas: list) -> str | None:
    correspondencias = buscar_correspondencias(pergunta, respostas)
    if correspondencias_ambiguas(correspondencias):
        return None
    correspondencia = correspondencias[0] if correspondencias else None
    if correspondencia and correspondencia["pontuacao"] >= LIMIAR_RESPOSTA_DIRETA:
        return correspondencia["resposta"]
    return None

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
    precisa_confirmacao: bool = False
    precisa_desambiguacao: bool = False
    respostas_candidatas: list[Correspondencia]

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

class ConfirmarRespostaRequest(BaseModel):
    session_id: str
    aceita: bool

class DesambiguarRespostaRequest(BaseModel):
    session_id: str
    indice: int

# --- Rotas da API ---
@app.get("/")
def home():
    return {"status": "Backend local funcionando."}

@app.post("/chat", response_model=ChatResponse)
def processar_chat(req: ChatRequest):
    mensagem_usuario = req.mensagem.strip()
    if not mensagem_usuario:
        raise HTTPException(status_code=422, detail="A mensagem não pode ficar vazia.")

    correspondencias = buscar_correspondencias(
        mensagem_usuario, carregar_dados().get("respostas", [])
    )
    correspondencia = correspondencias[0] if correspondencias else None
    candidatas_ambiguas = correspondencias_ambiguas(correspondencias)
    precisa_desambiguacao = bool(candidatas_ambiguas)
    precisa_confirmacao = bool(
        not precisa_desambiguacao
        and correspondencia
        and LIMIAR_RESPOSTA_PARECIDA <= correspondencia["pontuacao"] < LIMIAR_RESPOSTA_DIRETA
    )
    precisa_ensino = (
        not precisa_desambiguacao
        and (not correspondencia or correspondencia["pontuacao"] < LIMIAR_RESPOSTA_PARECIDA)
    )
    if precisa_desambiguacao:
        resposta_final = "Encontrei mais de uma resposta parecida. Escolha a que melhor responde à sua pergunta."
    elif precisa_confirmacao:
        resposta_final = correspondencia["resposta"]
    elif precisa_ensino:
        resposta_final = RESPOSTA_DESCONHECIDA
    else:
        resposta_final = correspondencia["resposta"]

    historicos = carregar_historicos_salvos()
    if req.session_id not in historicos:
        titulo_sessao = gerar_titulo_inteligente(mensagem_usuario)
        historicos[req.session_id] = {"titulo": titulo_sessao, "mensagens": []}
    else:
        titulo_sessao = historicos[req.session_id]["titulo"]

    if precisa_ensino:
        historicos[req.session_id]["pergunta_pendente"] = mensagem_usuario
        historicos[req.session_id].pop("confirmacao_pendente", None)
        historicos[req.session_id].pop("desambiguacao_pendente", None)
    elif precisa_desambiguacao:
        historicos[req.session_id]["desambiguacao_pendente"] = {
            "pergunta": mensagem_usuario,
            "candidatas": candidatas_ambiguas,
        }
        historicos[req.session_id].pop("pergunta_pendente", None)
        historicos[req.session_id].pop("confirmacao_pendente", None)
    elif precisa_confirmacao:
        historicos[req.session_id]["confirmacao_pendente"] = {
            "pergunta": mensagem_usuario,
            "pergunta_base": correspondencia["pergunta_base"],
            "resposta": correspondencia["resposta"],
        }
        historicos[req.session_id].pop("pergunta_pendente", None)
        historicos[req.session_id].pop("desambiguacao_pendente", None)
    else:
        historicos[req.session_id].pop("pergunta_pendente", None)
        historicos[req.session_id].pop("confirmacao_pendente", None)
        historicos[req.session_id].pop("desambiguacao_pendente", None)

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
        precisa_confirmacao=precisa_confirmacao,
        precisa_desambiguacao=precisa_desambiguacao,
        respostas_candidatas=candidatas_ambiguas,
    )


@app.post("/desambiguar-resposta")
def desambiguar_resposta(req: DesambiguarRespostaRequest):
    historicos = carregar_historicos_salvos()
    conversa = historicos.get(req.session_id)
    pendente = conversa.get("desambiguacao_pendente") if conversa else None
    if not pendente:
        raise HTTPException(status_code=404, detail="Não há respostas aguardando escolha.")

    candidatas = pendente.get("candidatas", [])
    if req.indice < 0 or req.indice >= len(candidatas):
        raise HTTPException(status_code=422, detail="A opção selecionada não existe.")

    escolhida = candidatas[req.indice]
    dados = carregar_dados()
    entrada = encontrar_resposta_base(
        dados.get("respostas", []),
        escolhida["pergunta_base"],
        escolhida["resposta"],
    )
    if not entrada:
        raise HTTPException(
            status_code=409,
            detail="A resposta selecionada mudou na base. Faça uma nova pergunta.",
        )

    pergunta = pendente["pergunta"]
    if not any(
        isinstance(pergunta_salva, str)
        and normalizar_texto(pergunta_salva) == normalizar_texto(pergunta)
        for pergunta_salva in entrada.get("perguntas", [])
    ):
        entrada.setdefault("perguntas", []).append(pergunta)
        salvar_dados(dados)

    conversa.pop("desambiguacao_pendente", None)
    mensagens = conversa.get("mensagens", [])
    if mensagens and mensagens[-1].get("role") == "assistant":
        mensagens[-1]["content"] = escolhida["resposta"]
    salvar_historicos_salvos(historicos)
    return {"status": "sucesso", "resposta": escolhida["resposta"]}


@app.post("/confirmar-resposta")
def confirmar_resposta(req: ConfirmarRespostaRequest):
    historicos = carregar_historicos_salvos()
    conversa = historicos.get(req.session_id)
    pendente = conversa.get("confirmacao_pendente") if conversa else None
    if not pendente:
        raise HTTPException(status_code=404, detail="Não há resposta aguardando confirmação.")

    if req.aceita:
        dados = carregar_dados()
        entrada = encontrar_resposta_base(
            dados.get("respostas", []),
            pendente["pergunta_base"],
            pendente["resposta"],
        )
        if not entrada:
            raise HTTPException(
                status_code=409,
                detail="A resposta sugerida mudou na base. Revise ou ensine uma resposta nova.",
            )

        pergunta_normalizada = normalizar_texto(pendente["pergunta"])
        if not any(
            isinstance(pergunta, str) and normalizar_texto(pergunta) == pergunta_normalizada
            for pergunta in entrada.get("perguntas", [])
        ):
            entrada.setdefault("perguntas", []).append(pendente["pergunta"])
            salvar_dados(dados)

        mensagem_final = "Entendi! Vou reconhecer essa forma de perguntar também."
    else:
        conversa["pergunta_pendente"] = pendente["pergunta"]
        mensagem_final = RESPOSTA_DESCONHECIDA

    conversa.pop("confirmacao_pendente", None)
    mensagens = conversa.get("mensagens", [])
    if mensagens and mensagens[-1].get("role") == "assistant":
        mensagens[-1]["content"] = mensagem_final
    salvar_historicos_salvos(historicos)

    return {
        "status": "sucesso",
        "mensagem": mensagem_final,
        "precisa_ensino": not req.aceita,
    }


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