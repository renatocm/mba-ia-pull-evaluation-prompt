"""Valida o artefato v2 e sua compatibilidade com o LangChain, sem chamar APIs."""
import sys
import re
from pathlib import Path

import pytest
import yaml
from langchain_core.prompts import ChatPromptTemplate

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))
from utils import validate_prompt_structure


@pytest.fixture(scope="module")
def prompt_data():
    path = PROJECT_ROOT / "prompts" / "bug_to_user_story_v2.yml"
    with path.open(encoding="utf-8") as file:
        prompts = yaml.safe_load(file)
    assert set(prompts) == {"bug_to_user_story_v2"}
    return prompts["bug_to_user_story_v2"]


class TestPrompts:
    def test_prompt_has_system_prompt(self, prompt_data):
        assert isinstance(prompt_data["system_prompt"], str)
        assert prompt_data["system_prompt"].strip()
        valid, errors = validate_prompt_structure(prompt_data)
        assert valid, errors

    def test_prompt_has_role_definition(self, prompt_data):
        assert "Você é um Product Manager" in prompt_data["system_prompt"]

    def test_prompt_mentions_format(self, prompt_data):
        system = prompt_data["system_prompt"]
        for required in ("MARKDOWN", "## User Story", "## Critérios de Aceitação", "Como", "eu quero", "para que"):
            assert required in system

    def test_prompt_has_few_shot_examples(self, prompt_data):
        examples = prompt_data["system_prompt"].split("EXEMPLO ")[1:]
        assert len(examples) >= 2
        for example in examples:
            entry, output = example.split("Saída:", 1)
            assert entry.split("Entrada:", 1)[1].strip()
            assert output.strip()

    def test_prompt_no_todos(self, prompt_data):
        assert not re.search(r"\bTODO\b|\[TODOs?\]", yaml.safe_dump(prompt_data), re.IGNORECASE)

    def test_minimum_techniques(self, prompt_data):
        techniques = prompt_data["techniques_applied"]
        assert isinstance(techniques, list)
        assert len(set(techniques)) >= 2
        assert "Few-shot Learning" in techniques
        assert "Role Prompting" in techniques

    @pytest.mark.parametrize("report", ["", "   ", 'Falha ao abrir: {"id": 42}', "Erro com acentuação: ação indisponível."])
    def test_template_preserves_input(self, prompt_data, report):
        template = ChatPromptTemplate.from_messages([
            ("system", prompt_data["system_prompt"]),
            ("human", prompt_data["user_prompt"]),
        ])
        assert template.input_variables == ["bug_report"]
        assert "{bug_report}" not in prompt_data["system_prompt"]
        assert prompt_data["user_prompt"].count("{bug_report}") == 1
        messages = template.format_messages(bug_report=report)
        assert messages[0].content == prompt_data["system_prompt"]
        assert messages[1].content == prompt_data["user_prompt"].replace("{bug_report}", report)
