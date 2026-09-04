import asyncio
import tempfile
from pathlib import Path

from bot.knowledge_retrieval import KnowledgeRetriever
from bot.knowledge_writer import KnowledgeWriter
from bot.qwen_analyst import QwenAnalyst


def check_knowledge_writer() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory) / "learned"
        evidence = root / ".evidence.json"
        writer = KnowledgeWriter(str(root), str(evidence))

        first = {
            "type": "mechanic",
            "claim": "Исследование тратит 20 воды",
            "mechanic_key": "exploration_water_cost",
            "domain": "exploration",
            "confidence": 0.90,
            "evidence": ["Observed water decrease after exploration."],
        }
        second = {
            "type": "mechanic",
            "claim": "Исследование тратит 10 воды",
            "mechanic_key": "exploration_water_cost",
            "relation": "contradicts",
            "conflicts_with": [first["claim"]],
            "domain": "exploration",
            "confidence": 0.90,
            "evidence": ["Observed a different water decrease after exploration."],
        }

        writer.write_candidates([first], "self-check-1", "observation-1")
        writer.write_candidates([second], "self-check-2", "observation-2")

        records = writer.records
        statuses = {record.get("status") for record in records.values()}
        if statuses != {"conflicted"}:
            raise AssertionError(f"Contradiction check failed: statuses={statuses}
")


def check_retrieval() -> None:
    retriever = KnowledgeRetriever()
    if not retriever.documents:
        raise AssertionError("Knowledge retrieval loaded no documents")

    context = retriever.build_qwen_prompt_context("бой урон броня", top_k=2, max_chars=2000)
    if not context:
        raise AssertionError("Knowledge retrieval returned empty context")


def check_qwen_parser() -> None:
    response = QwenAnalyst._parse_response(
        '{"candidates":[{"claim":"test","mechanic_key":"test_mechanic"}]}'
    )
    if len(response) != 1 or response[0].get("mechanic_key") != "test_mechanic":
        raise AssertionError("Qwen JSON parser check failed")


def check_imports() -> None:
    from bot.agent import Agent
    from bot.learning import QLearning
    from bot.memory import ExperienceMemory
    from bot.perception import Perception
    from bot.reward import RewardEngine
    from bot.stats import LearningStats
    from bot.strategy import StrategyMemory
    from bot.telegram_client import GameClient
    from bot.transitions import TransitionMemory

    objects = [
        Agent,
        QLearning,
        ExperienceMemory,
        Perception,
        RewardEngine,
        LearningStats,
        StrategyMemory,
        GameClient,
        TransitionMemory,
    ]
    if len(objects) != 9:
        raise AssertionError("Core import check failed")


def main() -> None:
    print("[CHECK] core imports")
    check_imports()
    print("[OK] core imports")

    print("[CHECK] knowledge retrieval")
    check_retrieval()
    print("[OK] knowledge retrieval")

    print("[CHECK] knowledge contradiction handling")
    check_knowledge_writer()
    print("[OK] knowledge contradiction handling")

    print("[CHECK] Qwen JSON parser")
    check_qwen_parser()
    print("[OK] Qwen JSON parser")

    print("[OK] Preflight checks passed")
    print("[INFO] This check does not connect to Telegram or call Qwen API.")


if __name__ == "__main__":
    asyncio.run(asyncio.to_thread(main))
