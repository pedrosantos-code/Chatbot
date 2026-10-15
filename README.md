# Chatbot local

Chatbot pessoal feito com Streamlit e FastAPI. As conversas e respostas ensinadas ficam nos arquivos `historicos.json` e `dados.json`; o projeto não usa serviços de IA externos.

## Executar no Windows

Instale as dependências uma vez, com internet:

```powershell
.\venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Depois, em dois terminais, inicie o backend e a interface:

```powershell
uvicorn backend:app --host 127.0.0.1 --port 8000
```

```powershell
.\venv\Scripts\Activate.ps1
streamlit run app.py
```

O aplicativo se comunica apenas com o backend local em `127.0.0.1`. Depois de instalar Python e as dependências, pode ser usado sem internet.

## Como o aprendizado funciona

O chatbot procura perguntas semelhantes na base local. Quando não encontra uma resposta confiável, ele pede que você ensine a resposta correta; perguntas desconhecidas não são salvas como respostas falsas. O aprendizado é uma base local de perguntas e respostas, não treinamento autônomo de um modelo de linguagem.

Quando uma pergunta fica parecida, mas não suficientemente próxima de uma pergunta aprendida, o chatbot mostra a resposta candidata e pede confirmação. Ao confirmar, salva a nova forma da pergunta como alternativa; se não servir, você pode ensinar a resposta certa. A similaridade é uma heurística textual local, não uma garantia de que a resposta está correta.

Se duas respostas diferentes tiverem pontuações de similaridade próximas, o chatbot pede que você escolha uma opção em vez de decidir sozinho. Sua escolha também ensina essa nova forma de perguntar.

## Histórico, exportação e backup

Na barra lateral, pesquise conversas por palavras do título ou das mensagens. A lixeira abre uma confirmação antes de apagar. Em **Exportar conversa atual**, baixe a conversa aberta em Markdown (`.md`) ou texto (`.txt`).

Abra **Base de respostas e backup** para selecionar uma resposta, editar as perguntas associadas e o texto da resposta, ou apagar uma resposta (a remoção pede confirmação). O botão **Baixar backup dos dados** gera um ZIP com `dados.json` e `historicos.json`. Guarde esse arquivo em outro local. Para restaurar, pare o backend, extraia o ZIP e copie os dois arquivos para a pasta do projeto, substituindo os atuais; depois inicie o backend novamente.

## Testes

Com as dependências instaladas, execute na pasta do projeto:

```powershell
.\venv\Scripts\python.exe -m unittest discover -s tests -v
```

Os testes usam arquivos temporários; não alteram os dados reais do projeto.
