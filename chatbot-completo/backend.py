import os
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
from dotenv import load_dotenv
from google import genai
from google.genai import types

# Carrega variáveis do arquivo .env
load_dotenv()

api_key = os.getenv("GEMINI_API_KEY")
if not api_key:
    raise RuntimeError("A variável GEMINI_API_KEY não foi configurada no arquivo .env!")

# Inicializa o cliente oficial do Gemini
client = genai.Client(api_key=api_key)

app = FastAPI(
    title="Chatbot AI API",
    description="Backend de Chatbot com FastAPI e Google Gemini 2.5",
    version="1.0.0"
)

# Estrutura das requisições
class MensagemHistorico(BaseModel):
    role: str  # 'user' ou 'model'
    parts: List[str]

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
    return {"status": "Backend rodando com sucesso!"}

@app.post("/chat", response_model=ChatResponse)
def processar_chat(req: ChatRequest):
    try:
        # Instrução do sistema para definir o tom do assistente
        system_instruction = (
            "Você é um assistente virtual inteligente, prestativo e profissional. "
            "Responda sempre de forma clara e objetiva em Português do Brasil."
        )

        # Monta o histórico de conversas no formato do Gemini SDK
        contents = []
        for item in req.historico:
            contents.append(
                types.Content(
                    role=item.role,
                    parts=[types.Part.from_text(text=p) for p in item.parts]
                )
            )

        # Adiciona a mensagem atual do usuário
        contents.append(
            types.Content(
                role="user",
                parts=[types.Part.from_text(text=req.mensagem)]
            )
        )

        # Executa a geração usando Gemini 2.5 Flash
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=system_instruction,
                temperature=0.7
            )
        )

        return ChatResponse(
            user_id=req.user_id,
            resposta=response.text,
            status="sucesso"
        )

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Erro no processamento da IA: {str(e)}")