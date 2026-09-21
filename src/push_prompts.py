"""Valida e publica o prompt v2 no LangSmith Hub, com acesso público."""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain import hub
from langchain_core.prompts import ChatPromptTemplate
from utils import (
    load_yaml, check_env_vars, print_section_header, validate_prompt_structure,
)

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_NAME = "bug_to_user_story_v2"
load_dotenv(PROJECT_ROOT / ".env")


def validate_prompt(prompt_data: dict) -> tuple[bool, list]:
    """Valida metadados e a montagem do template antes de publicar."""
    if not isinstance(prompt_data, dict):
        return False, ["O prompt deve ser um dicionário."]
    errors = []
    for field in ("description", "system_prompt", "user_prompt", "version"):
        value = prompt_data.get(field)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{field} deve ser um texto não vazio.")
    for field in ("tags", "techniques_applied"):
        value = prompt_data.get(field)
        if not isinstance(value, list) or not all(
            isinstance(item, str) and item.strip() for item in value
        ):
            errors.append(f"{field} deve ser uma lista de textos não vazios.")
    if errors:
        return False, errors

    _, structure_errors = validate_prompt_structure(prompt_data)
    errors.extend(structure_errors)
    techniques = set(prompt_data["techniques_applied"])
    if len(techniques) < 2 or "Few-shot Learning" not in techniques:
        errors.append("Use Few-shot Learning e pelo menos mais uma técnica distinta.")
    if prompt_data["version"] != "v2":
        errors.append("Este script publica somente a versão v2.")
    if "{bug_report}" in prompt_data["system_prompt"]:
        errors.append("O relato deve aparecer somente na mensagem human.")
    if prompt_data["user_prompt"].count("{bug_report}") != 1:
        errors.append("user_prompt deve conter {bug_report} exatamente uma vez.")
    try:
        template = ChatPromptTemplate.from_messages([
            ("system", prompt_data["system_prompt"]),
            ("human", prompt_data["user_prompt"]),
        ])
        if template.input_variables != ["bug_report"]:
            errors.append("A única variável esperada é bug_report.")
        template.format_messages(bug_report="Relato de validação local.")
    except (ValueError, KeyError, TypeError) as exc:
        errors.append(f"Template inválido ({type(exc).__name__}).")
    return not errors, errors


def push_prompt_to_langsmith(prompt_name: str, prompt_data: dict) -> bool:
    """Publica o template e seus metadados; retorna False em caso de falha."""
    valid, errors = validate_prompt(prompt_data)
    if not valid:
        for error in errors:
            print(f"❌ {error}")
        return False
    if not check_env_vars(["LANGSMITH_API_KEY", "USERNAME_LANGSMITH_HUB"]):
        return False
    username = os.getenv("USERNAME_LANGSMITH_HUB", "").strip()
    if not username or "/" in username or ":" in username or prompt_name != PROMPT_NAME:
        print("❌ Username ou nome do prompt inválido.")
        return False
    try:
        template = ChatPromptTemplate.from_messages([
            ("system", prompt_data["system_prompt"]),
            ("human", prompt_data["user_prompt"]),
        ])
        template.metadata = {
            "version": prompt_data["version"],
            "techniques_applied": prompt_data["techniques_applied"],
        }
        identifier = f"{username}/{prompt_name}"
        url = hub.push(
            identifier,
            template,
            api_key=os.getenv("LANGSMITH_API_KEY"),
            new_repo_is_public=True,
            new_repo_description=prompt_data["description"],
            tags=list(dict.fromkeys(prompt_data["tags"] + prompt_data["techniques_applied"])),
            readme=(f"# {prompt_name}\n\n{prompt_data['description']}\n\n"
                    "Técnicas aplicadas: " + ", ".join(prompt_data["techniques_applied"])),
        )
        print(f"✅ Prompt público publicado: {url}")
        return True
    except Exception as exc:
        print(f"❌ Falha ao publicar no LangSmith ({type(exc).__name__}).")
        return False


def main():
    """Lê apenas o artefato v2 e retorna código de saída de sucesso ou erro."""
    print_section_header("Push do prompt v2 para o LangSmith Hub")
    data = load_yaml(str(PROJECT_ROOT / "prompts" / f"{PROMPT_NAME}.yml"))
    if not isinstance(data, dict) or set(data) != {PROMPT_NAME}:
        print(f"❌ O YAML deve conter somente a chave {PROMPT_NAME}.")
        return 1
    return 0 if push_prompt_to_langsmith(PROMPT_NAME, data[PROMPT_NAME]) else 1


if __name__ == "__main__":
    sys.exit(main())
