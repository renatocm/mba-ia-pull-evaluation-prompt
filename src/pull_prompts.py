"""
Faz pull do prompt inicial do LangSmith Hub e salva no formato YAML do projeto.
Usa serialização nativa do LangChain, sem renderizar os placeholders do prompt.
"""

import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from langchain import hub
from langchain_core.load import dumpd
from utils import save_yaml, check_env_vars, print_section_header

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROMPT_NAME = "bug_to_user_story_v1"
HUB_PROMPT = f"leonanluppi/{PROMPT_NAME}"

load_dotenv(PROJECT_ROOT / ".env")


def _extract_prompts(prompt):
    """Extrai mensagens textuais; rejeita estruturas que o YAML não representa."""
    serialized = dumpd(prompt)
    if serialized.get("id", [None])[-1] != "ChatPromptTemplate":
        raise ValueError("O Hub deve retornar um ChatPromptTemplate.")

    kwargs = serialized.get("kwargs", {})
    if kwargs.get("partial_variables"):
        raise ValueError("O YAML não suporta variáveis parcialmente preenchidas.")

    roles = {
        "SystemMessagePromptTemplate": "system_prompt",
        "HumanMessagePromptTemplate": "user_prompt",
        "SystemMessage": "system_prompt",
        "HumanMessage": "user_prompt",
    }
    extracted = {}
    for message in kwargs.get("messages", []):
        message_type = message.get("id", [None])[-1]
        field = roles.get(message_type)
        if field is None or field in extracted:
            raise ValueError("Esperadas exatamente uma mensagem system e uma human.")

        content = message.get("kwargs", {})
        if message_type.endswith("PromptTemplate"):
            template = content.get("prompt", {})
            if not isinstance(template, dict):
                raise ValueError("Prompts multimodais não são suportados pelo YAML.")
            template_kwargs = template.get("kwargs", {})
            if template_kwargs.get("partial_variables"):
                raise ValueError("O YAML não suporta variáveis parcialmente preenchidas.")
            if template_kwargs.get("template_format", "f-string") != "f-string":
                raise ValueError("O projeto espera templates no formato f-string.")
            text = template_kwargs.get("template")
        else:
            text = content.get("content")
            # Mensagens literais precisam preservar chaves ao virar templates.
            if isinstance(text, str):
                text = text.replace("{", "{{").replace("}", "}}")

        if not isinstance(text, str) or not text.strip():
            raise ValueError(f"Mensagem {field} ausente, vazia ou não textual.")
        extracted[field] = text

    if list(extracted) != ["system_prompt", "user_prompt"]:
        raise ValueError("Esperadas mensagens system e human, nessa ordem.")
    return extracted


def pull_prompts_from_langsmith():
    """Valida credenciais, baixa o prompt e retorna True somente após salvá-lo."""
    if not check_env_vars(["LANGSMITH_API_KEY"]):
        return False

    try:
        print(f"Puxando prompt: {HUB_PROMPT}")
        prompt = hub.pull(HUB_PROMPT, api_key=os.getenv("LANGSMITH_API_KEY"))
        prompts = _extract_prompts(prompt)
        data = {
            PROMPT_NAME: {
                "description": "Prompt para converter relatos de bugs em User Stories",
                **prompts,
                "version": "v1",
                "tags": ["bug-analysis", "user-story", "product-management"],
            }
        }
        output_path = PROJECT_ROOT / "prompts" / f"{PROMPT_NAME}.yml"
        if not save_yaml(data, str(output_path)):
            return False
        print(f"✅ Prompt salvo em: {output_path}")
        return True
    except Exception as exc:
        # Não imprime detalhes da exceção, que podem conter credenciais HTTP.
        print(f"❌ Falha ao baixar ou salvar o prompt ({type(exc).__name__}).")
        return False


def main():
    """Retorna código de saída compatível com a execução no terminal."""
    print_section_header("Pull de prompts do LangSmith Hub")
    return 0 if pull_prompts_from_langsmith() else 1


if __name__ == "__main__":
    sys.exit(main())
