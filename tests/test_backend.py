import json
import tempfile
import unittest
import zipfile
from io import BytesIO
from pathlib import Path

from fastapi import HTTPException

import backend


class BackendPersistenceTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.original_data_path = backend.ARQUIVO_DADOS
        self.original_history_path = backend.ARQUIVO_HISTORICOS
        root = Path(self.temp_dir.name)
        backend.ARQUIVO_DADOS = root / "dados.json"
        backend.ARQUIVO_HISTORICOS = root / "historicos.json"
        backend.salvar_dados({
            "respostas": [
                {"perguntas": ["qual seu nome?"], "resposta": "Sou um assistente local."},
                {
                    "perguntas": ["pergunta antiga"],
                    "resposta": "Ainda estou a processar informações sobre esse tema.",
                },
            ]
        })
        backend.salvar_historicos_salvos({})

    def tearDown(self):
        backend.ARQUIVO_DADOS = self.original_data_path
        backend.ARQUIVO_HISTORICOS = self.original_history_path
        self.temp_dir.cleanup()

    def test_list_answers_omits_unlearned_placeholders(self):
        self.assertEqual(
            backend.obter_respostas(),
            [{"id": 0, "perguntas": ["qual seu nome?"], "resposta": "Sou um assistente local."}],
        )

    def test_update_and_delete_answer(self):
        backend.atualizar_resposta(
            0,
            backend.AtualizarRespostaRequest(
                perguntas=["Como você se chama?", "Qual seu nome?", "  "],
                resposta="Sou o assistente deste computador.",
            ),
        )
        self.assertEqual(
            backend.carregar_dados()["respostas"][0],
            {
                "perguntas": ["Como você se chama?", "Qual seu nome?"],
                "resposta": "Sou o assistente deste computador.",
            },
        )

        backend.deletar_resposta(0)
        self.assertEqual(backend.carregar_dados()["respostas"], [
            {
                "perguntas": ["pergunta antiga"],
                "resposta": "Ainda estou a processar informações sobre esse tema.",
            }
        ])

    def test_update_rejects_empty_question_or_answer(self):
        with self.assertRaises(HTTPException) as context:
            backend.atualizar_resposta(
                0,
                backend.AtualizarRespostaRequest(perguntas=["  "], resposta=""),
            )
        self.assertEqual(context.exception.status_code, 422)

    def test_unknown_answer_can_be_taught_and_reused(self):
        unknown = backend.processar_chat(
            backend.ChatRequest(session_id="session-1", mensagem="Como cuidar de uma planta?")
        )
        self.assertTrue(unknown.precisa_ensino)

        backend.ensinar_resposta(
            backend.EnsinoRequest(
                session_id="session-1",
                pergunta="Como cuidar de uma planta?",
                resposta="Regue conforme a espécie e a luz disponível.",
            )
        )
        known = backend.processar_chat(
            backend.ChatRequest(session_id="session-2", mensagem="Como cuidar de uma planta?")
        )
        self.assertFalse(known.precisa_ensino)
        self.assertEqual(known.resposta, "Regue conforme a espécie e a luz disponível.")

    def test_uncertain_match_asks_for_confirmation_and_learns_alias(self):
        backend.salvar_dados({
            "respostas": [
                {
                    "perguntas": ["como trocar a senha do wifi"],
                    "resposta": "Abra as configurações do roteador e altere a senha.",
                }
            ]
        })

        candidate = backend.processar_chat(
            backend.ChatRequest(session_id="session-1", mensagem="como posso trocar senha wifi")
        )
        self.assertTrue(candidate.precisa_confirmacao)
        self.assertFalse(candidate.precisa_ensino)
        self.assertEqual(
            candidate.resposta,
            "Abra as configurações do roteador e altere a senha.",
        )

        result = backend.confirmar_resposta(
            backend.ConfirmarRespostaRequest(session_id="session-1", aceita=True)
        )
        self.assertFalse(result["precisa_ensino"])
        self.assertIn(
            "como posso trocar senha wifi",
            backend.carregar_dados()["respostas"][0]["perguntas"],
        )
        self.assertNotIn(
            "confirmacao_pendente",
            backend.carregar_historicos_salvos()["session-1"],
        )

        repeat = backend.processar_chat(
            backend.ChatRequest(session_id="session-2", mensagem="como posso trocar senha wifi")
        )
        self.assertFalse(repeat.precisa_confirmacao)
        self.assertEqual(repeat.resposta, candidate.resposta)

    def test_rejecting_uncertain_match_opens_teaching_flow(self):
        backend.salvar_dados({
            "respostas": [
                {
                    "perguntas": ["como trocar a senha do wifi"],
                    "resposta": "Abra as configurações do roteador e altere a senha.",
                }
            ]
        })
        backend.processar_chat(
            backend.ChatRequest(session_id="session-1", mensagem="como posso trocar senha wifi")
        )

        result = backend.confirmar_resposta(
            backend.ConfirmarRespostaRequest(session_id="session-1", aceita=False)
        )
        self.assertTrue(result["precisa_ensino"])
        self.assertEqual(
            backend.carregar_historicos_salvos()["session-1"]["pergunta_pendente"],
            "como posso trocar senha wifi",
        )
        self.assertNotIn(
            "confirmacao_pendente",
            backend.carregar_historicos_salvos()["session-1"],
        )

    def test_high_confidence_match_is_returned_without_confirmation(self):
        response = backend.processar_chat(
            backend.ChatRequest(session_id="session-1", mensagem="qual seu nome")
        )
        self.assertFalse(response.precisa_confirmacao)
        self.assertFalse(response.precisa_ensino)

    def test_backup_contains_data_and_history_files(self):
        response = backend.baixar_backup()
        with zipfile.ZipFile(BytesIO(response.body)) as archive:
            self.assertEqual(set(archive.namelist()), {"dados.json", "historicos.json"})
            self.assertEqual(
                json.loads(archive.read("dados.json")),
                backend.carregar_dados(),
            )
            self.assertEqual(
                json.loads(archive.read("historicos.json")),
                backend.carregar_historicos_salvos(),
            )

    def test_delete_history(self):
        backend.salvar_historicos_salvos({"session-1": {"titulo": "Teste", "mensagens": []}})
        backend.deletar_historico("session-1")
        self.assertEqual(backend.carregar_historicos_salvos(), {})


if __name__ == "__main__":
    unittest.main()
