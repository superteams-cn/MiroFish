"""剧本推演的「问角色」采访（P3/Step5）。

与 OASIS 的 InterviewService（依赖运行中的模拟环境 + IPC）解耦：叙事采访无需环境，
直接以角色人设 + 其可见的 beats 记忆做一次 LLM 应答，让用户在推演结束后仍能追问任一角色。
"""

from __future__ import annotations

import logging
from pathlib import Path

from ...domain.narrative import fold
from ...utils.llm_client import LLMClient
from ...utils.locale import get_language_instruction
from .engine import BeatLog, _fmt_beat, recent_beats_for
from .runner import BEATS_FILENAME, load_seed

logger = logging.getLogger(__name__)


def list_characters(sim_dir: str | Path) -> list[dict[str, str]]:
    """该推演的角色清单（供前端采访选人）。"""
    seed = load_seed(sim_dir)
    if not seed:
        return []
    return [{"char_id": c.char_id, "name": c.name, "role": c.role} for c in seed.characters]


def _resolve_character(seed, agent_ref):
    """agent_ref 可为 char_id、角色名，或整型索引。"""
    if seed is None:
        return None
    ref = str(agent_ref)
    for c in seed.characters:
        if c.char_id == ref or c.name == ref:
            return c
    # 整型索引兜底
    try:
        idx = int(agent_ref)
        if 0 <= idx < len(seed.characters):
            return seed.characters[idx]
    except (ValueError, TypeError):
        pass
    return None


def interview_character(
    sim_dir: str | Path,
    agent_ref,
    prompt: str,
    llm_client: LLMClient | None = None,
) -> dict:
    """以某角色身份回答提问。返回 {success, agent_id, agent_name, response}。"""
    seed = load_seed(sim_dir)
    char = _resolve_character(seed, agent_ref)
    if char is None:
        return {"success": False, "error": "角色不存在", "response": ""}

    beats = BeatLog(Path(sim_dir) / BEATS_FILENAME).read_all()
    world = fold(seed, beats)
    memory = recent_beats_for(world.transcript, char.char_id, limit=20)
    mem_txt = "\n".join(_fmt_beat(world, b) for b in memory) or "（推演中你尚未开口）"
    name_by_id = {c.char_id: c.name for c in seed.characters}
    rel = (
        "；".join(
            f"对{name_by_id.get(cid, cid)}：{desc}" for cid, desc in char.relationships.items()
        )
        if char.relationships
        else ""
    )

    llm = llm_client or LLMClient()
    system = (
        f"你就是「{char.name}」（{char.role}）。始终以第一人称、用这个角色的口吻、立场与情绪回答，"
        f"不要跳出角色，不要以 AI 身份说话。\n"
        f"你的人设：{char.persona}\n核心动机：{char.motivation}\n目标：{char.goal}\n"
        f"当前心理状态：{char.mental_state or '（按剧情推断）'}\n"
        f"你对他人的态度：{rel or '（按剧情推断）'}\n"
        f"{get_language_instruction()}"
    )
    user = (
        f"## 你在这场推演里的经历（只含你能感知到的）\n{mem_txt}\n\n"
        f"## 有人问你\n{prompt}\n\n请以你本人的身份回答。"
    )
    try:
        response = llm.chat(
            [{"role": "system", "content": system}, {"role": "user", "content": user}],
            temperature=0.8,
            max_tokens=800,
        )
    except Exception as e:  # noqa: BLE001
        logger.warning("narrative interview failed: %s", e)
        return {"success": False, "error": str(e), "response": ""}

    return {
        "success": True,
        "agent_id": char.char_id,
        "agent_name": char.name,
        "response": (response or "").strip(),
    }
