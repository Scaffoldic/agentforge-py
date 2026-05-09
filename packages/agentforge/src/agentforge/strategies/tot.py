"""`TreeOfThoughts` — beam-search reasoning with scored branches.

Per feat-002 §4.3:

  GENERATE:  one LLM call returns `branch_factor` candidate thoughts
             at the current depth.
  SCORE:     each thought is scored 0..1 by the LLM ("self") or by
             a cheap judge model ("judge").
  PRUNE:     keep thoughts above `score_threshold`. If `beam_width`
             is set, additionally keep only the top-K.
  EXPAND:    recurse on survivors to depth=`depth`.
  SYNTHESIZE: best leaf → final answer.

Modern: structured Pydantic schemas for branch generation and
scoring (no free-form parsing); budget-aware graceful degradation
(if the next level's estimated cost would exceed the remaining
budget, the strategy synthesises with what it has rather than
crashing).

`scorer="judge"` in v0.1 falls back to "self" — a separate cheap
judge model is introduced in feat-006 (`agentforge-eval-geval`).
The constructor accepts the value so the API surface is locked at
v0.1; the implementation upgrades transparently when feat-006 lands.
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from typing import Literal
from uuid import uuid4

from agentforge_core.values.messages import Message
from agentforge_core.values.state import AgentState
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from agentforge.resolver_register import register_strategy
from agentforge.runtime import RuntimeContext
from agentforge.strategies._base import StrategyBase, get_runtime

log = logging.getLogger(__name__)

ScorerKind = Literal["self", "judge"]

GENERATE_SYSTEM_PROMPT = (
    "You are exploring multiple plausible reasoning paths for a task. "
    "Generate {branch_factor} distinct candidate thoughts. Each thought "
    "should be a different angle, approach, or partial solution. Return "
    "ONLY a JSON object matching this schema (no other text):\n\n"
    '  {{"thoughts": [{{"id": "<unique id>", "content": "<thought text>"}}, ...]}}\n\n'
    "Provide exactly {branch_factor} thoughts."
)

SCORE_SYSTEM_PROMPT = (
    "Score each of the candidate thoughts below from 0.0 (irrelevant / "
    "wrong) to 1.0 (excellent / correct) for how well it advances the "
    "user's task. Return ONLY a JSON object matching this schema (no "
    "other text):\n\n"
    '  {"scores": [{"branch_id": "<id>", "score": <0..1>, "reasoning": "<why>"}, ...]}'
)

SYNTHESIZE_SYSTEM_PROMPT = (
    "You have explored multiple reasoning paths and selected the best "
    "one. Produce the final answer based on the path's content; do not "
    "introduce new claims unsupported by the path."
)


# ----------------------------------------------------------------------
# LLM I/O schemas
# ----------------------------------------------------------------------


class _Thought(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    id: str = Field(min_length=1)
    content: str = Field(min_length=1)


class _ThoughtList(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    thoughts: list[_Thought] = Field(min_length=1)


class _BranchScore(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    branch_id: str
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = ""


class _BranchScoreList(BaseModel):
    model_config = ConfigDict(frozen=True, strict=True)
    scores: list[_BranchScore]


# ----------------------------------------------------------------------
# Internal node + tree
# ----------------------------------------------------------------------


@dataclass(slots=True)
class _Node:
    """One thought in the search tree."""

    id: str
    parent_id: str | None
    depth: int
    content: str
    score: float = 0.0
    children: list[_Node] = field(default_factory=list)


def _path_to_root(leaf: _Node, by_id: dict[str, _Node]) -> list[_Node]:
    path: list[_Node] = []
    cursor: _Node | None = leaf
    while cursor is not None:
        path.append(cursor)
        cursor = by_id.get(cursor.parent_id) if cursor.parent_id else None
    return list(reversed(path))


# ----------------------------------------------------------------------
# Strategy
# ----------------------------------------------------------------------


@register_strategy("tot")
class TreeOfThoughts(StrategyBase):
    """Beam-search reasoning over scored branches.

    Per feat-002 §4.2 the constructor surface is locked at v0.1:

    Args:
        branch_factor: Number of candidate thoughts generated per
            level. Default 3.
        depth: Number of expansion levels (root + depth-1 expansions).
            Default 2.
        score_threshold: Minimum score for a branch to survive
            pruning. Range [0, 1]. Default 0.5.
        scorer: "self" uses the agent's primary LLM to score; "judge"
            (deferred to feat-006) will use a cheap-judge model. Both
            values currently behave identically.
        beam_width: If set, keep at most this many of the highest-
            scoring survivors per level. None = no top-K cap (only
            score_threshold applies). Default None.
    """

    def __init__(
        self,
        *,
        branch_factor: int = 3,
        depth: int = 2,
        score_threshold: float = 0.5,
        scorer: ScorerKind = "self",
        beam_width: int | None = None,
    ) -> None:
        if branch_factor < 1:
            raise ValueError("branch_factor must be >= 1")
        if depth < 1:
            raise ValueError("depth must be >= 1")
        if not 0.0 <= score_threshold <= 1.0:
            raise ValueError("score_threshold must be in [0, 1]")
        if scorer not in ("self", "judge"):
            raise ValueError(f"scorer must be 'self' or 'judge', got {scorer!r}")
        if beam_width is not None and beam_width < 1:
            raise ValueError("beam_width must be >= 1 when set")
        self._branch_factor = branch_factor
        self._depth = depth
        self._score_threshold = score_threshold
        self._scorer: ScorerKind = scorer
        self._beam_width = beam_width

    async def run(self, state: AgentState) -> AgentState:
        runtime = get_runtime(state)
        by_id: dict[str, _Node] = {}

        # Root — start from the task itself; no LLM call yet.
        root = _Node(id=str(uuid4()), parent_id=None, depth=0, content=state.task, score=1.0)
        by_id[root.id] = root

        survivors: list[_Node] = [root]
        current_depth = 0

        while current_depth < self._depth and survivors:
            self._check_guardrails(state)

            # Budget-aware graceful degradation: estimate the cost of
            # the next level (branch + score per survivor); if it would
            # exceed remaining budget, stop expanding and synthesise.
            if not self._can_afford_next_level(runtime, len(survivors)):
                log.warning(
                    "TreeOfThoughts: estimated next-level cost exceeds "
                    "remaining budget; synthesising with current best."
                )
                break

            new_survivors: list[_Node] = []
            for parent in survivors:
                self._check_guardrails(state)

                # GENERATE candidates for this parent
                candidates = await self._generate(state, parent, current_depth)
                if not candidates:
                    continue

                # SCORE candidates
                scored = await self._score(state, candidates, current_depth)

                # Build child nodes + record branch step
                for thought, score in scored:
                    child = _Node(
                        id=thought.id,
                        parent_id=parent.id,
                        depth=current_depth + 1,
                        content=thought.content,
                        score=score,
                    )
                    parent.children.append(child)
                    by_id[child.id] = child
                    self._record_step(
                        state,
                        iteration=current_depth + 1,
                        kind="branch",
                        content={
                            "branch_id": child.id,
                            "parent_id": parent.id,
                            "score": score,
                            "thought": thought.content,
                        },
                    )

                # PRUNE: above threshold; optionally top-K (beam_width)
                kept = [by_id[t.id] for (t, s) in scored if s >= self._score_threshold]
                kept.sort(key=lambda n: n.score, reverse=True)
                if self._beam_width is not None:
                    kept = kept[: self._beam_width]
                new_survivors.extend(kept)

            # Across all parents at this level, also bound the global
            # beam if set.
            new_survivors.sort(key=lambda n: n.score, reverse=True)
            if self._beam_width is not None:
                new_survivors = new_survivors[: self._beam_width]

            survivors = new_survivors
            current_depth += 1

        # Pick the best leaf overall — the best surviving node, or the
        # root if no level survived pruning.
        best = max(by_id.values(), key=lambda n: n.score) if by_id else root
        path = _path_to_root(best, by_id)
        path_text = "\n".join(f"  depth={n.depth} score={n.score:.2f}: {n.content}" for n in path)

        # SYNTHESIZE the final answer from the best path.
        await self._call_llm(
            state,
            iteration=current_depth + 1,
            system=SYNTHESIZE_SYSTEM_PROMPT,
            messages=[
                Message(role="user", content=state.task),
                Message(
                    role="assistant",
                    content=f"Best path explored:\n{path_text}",
                ),
            ],
            kind="synthesize",
        )

        return state

    # ------------------------------------------------------------------
    # Phase helpers
    # ------------------------------------------------------------------

    async def _generate(
        self, state: AgentState, parent: _Node, current_depth: int
    ) -> list[_Thought]:
        """Generate `branch_factor` candidate thoughts as children of `parent`."""
        prompt = GENERATE_SYSTEM_PROMPT.format(branch_factor=self._branch_factor)
        messages: list[Message] = [
            Message(role="user", content=state.task),
        ]
        if parent.depth > 0:
            messages.append(
                Message(
                    role="assistant",
                    content=(
                        f"Building on prior thought (score {parent.score:.2f}): {parent.content}"
                    ),
                )
            )
        response = await self._call_llm(
            state,
            iteration=current_depth + 1,
            system=prompt,
            messages=messages,
            kind="think",
        )
        try:
            thought_list = _ThoughtList.model_validate_json(_strip_code_fences(response.content))
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            log.warning(
                "TreeOfThoughts: candidate generation parse failed at depth %d: %s",
                current_depth,
                exc,
            )
            return []
        return list(thought_list.thoughts)

    async def _score(
        self,
        state: AgentState,
        candidates: list[_Thought],
        current_depth: int,
    ) -> list[tuple[_Thought, float]]:
        """Score each candidate; returns list of (thought, score)."""
        # scorer="judge" deferred to feat-006; falls back to "self" for now.
        candidate_text = "\n".join(f"- {t.id}: {t.content}" for t in candidates)
        messages: list[Message] = [
            Message(role="user", content=state.task),
            Message(role="assistant", content=f"Candidate thoughts:\n{candidate_text}"),
        ]
        response = await self._call_llm(
            state,
            iteration=current_depth + 1,
            system=SCORE_SYSTEM_PROMPT,
            messages=messages,
            kind="think",
        )
        try:
            score_list = _BranchScoreList.model_validate_json(_strip_code_fences(response.content))
        except (ValidationError, json.JSONDecodeError, ValueError) as exc:
            log.warning(
                "TreeOfThoughts: scoring parse failed at depth %d: %s. "
                "Defaulting all candidates to neutral score 0.5.",
                current_depth,
                exc,
            )
            return [(t, 0.5) for t in candidates]

        score_by_id = {s.branch_id: s.score for s in score_list.scores}
        # Any candidate the LLM didn't score gets the threshold-1 default
        # so it's pruned unless explicitly above-threshold.
        return [(t, score_by_id.get(t.id, 0.0)) for t in candidates]

    def _can_afford_next_level(self, runtime: RuntimeContext, n_survivors: int) -> bool:
        """Estimate next-level cost; return True if it fits in remaining budget.

        Estimate: each survivor needs (1 generate call + 1 score call).
        Average cost is `spent_usd / iteration` so far, with a safety
        floor; if no LLM calls have happened yet, assume a small
        nonzero cost.
        """
        budget = runtime.budget
        avg = budget.spent_usd / max(1, budget.iteration) if budget.iteration else 0.001
        estimated = n_survivors * 2 * avg
        return bool(estimated <= budget.remaining_usd())


def _strip_code_fences(content: str) -> str:
    """Strip ```json ... ``` fences if the LLM wrapped the JSON in them."""
    text = content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline == -1:
            return text
        body = text[first_newline + 1 :]
        if body.endswith("```"):
            body = body[: -len("```")]
        return body.strip()
    return text


__all__ = ["TreeOfThoughts"]
