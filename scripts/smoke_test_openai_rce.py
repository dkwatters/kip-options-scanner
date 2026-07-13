from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.research_conversation import ResearchConversationRequest
from src.research_conversation.openai_provider import (
    DEFAULT_RCE_OPENAI_MODEL,
    LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER,
    OPENAI_API_KEY_ENV,
    OpenAIResearchConversationProvider,
    RCE_OPENAI_MODEL_ENV,
)


SMOKE_TEST_QUESTION = (
    "I'm researching publicly traded companies that manufacture superconducting "
    "magnets for fusion reactors in Japan. Do not include cloud computing companies."
)


def _candidate_label(candidate: dict) -> str:
    ticker = candidate.get("ticker")
    company_name = candidate.get("company_name") or ""
    if ticker and company_name:
        return f"{ticker} - {company_name}"
    return str(ticker or company_name or candidate)


def _print_response_summary(response) -> None:
    metadata = response.metadata
    structured_response = response.structured_response or {}
    candidates = structured_response.get("candidate_securities") or []
    marker = structured_response.get("provider_verification_marker")

    print(f"provider name: {metadata.provider_name}")
    print(f"model name: {metadata.model_name}")
    print(f"prompt version: {metadata.prompt_version}")
    print(f"latency seconds: {metadata.latency_seconds}")
    print(f"provider verification marker: {marker}")
    print(f"raw candidate count: {metadata.raw_candidate_count}")
    print("first 5 candidate companies:")
    for candidate in candidates[:5]:
        if isinstance(candidate, dict):
            print(f"- {_candidate_label(candidate)}")
        else:
            print(f"- {candidate}")
    if not candidates:
        print("- none")
    print(f"warnings: {response.warnings or structured_response.get('warnings') or []}")
    print(f"errors: {response.errors or []}")


def _print_failure(response) -> None:
    metadata = response.metadata
    print(
        "exception type: "
        f"{metadata.provider_error_type or 'RCEProviderResponseError'}"
    )
    print(
        "exception message: "
        f"{metadata.provider_error_message or '; '.join(response.errors)}"
    )
    print(f"http status: {metadata.provider_http_status}")


def main() -> int:
    env_path = REPO_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)

    api_key = os.getenv(OPENAI_API_KEY_ENV)
    if not api_key:
        print(f"Missing required environment variable: {OPENAI_API_KEY_ENV}")
        return 2

    model_name = os.getenv(RCE_OPENAI_MODEL_ENV) or DEFAULT_RCE_OPENAI_MODEL
    provider = OpenAIResearchConversationProvider(
        api_key=api_key,
        model_name=model_name,
    )
    response = provider.interpret(
        ResearchConversationRequest(original_question=SMOKE_TEST_QUESTION)
    )

    _print_response_summary(response)

    marker = (response.structured_response or {}).get("provider_verification_marker")
    if response.has_errors:
        _print_failure(response)
        return 1
    if marker != LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER:
        print("exception type: RCEProviderVerificationError")
        print(
            "exception message: provider verification marker did not match "
            f"{LIVE_OPENAI_PROVIDER_VERIFICATION_MARKER}"
        )
        print("http status: None")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
