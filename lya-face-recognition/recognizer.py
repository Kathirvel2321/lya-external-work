"""Matching policy: turn embeddings into a decision about *who* is present.

Why this is separate from the model loader: the model answers "what does this
face look like", this file answers "may I believe it is the owner". Security
decisions should be readable in one place, and every rule here exists because
of a specific attack.

The four attacks this policy is built to stop:

1. **A photo of the owner.** Face matching alone says "yes". Fixed by requiring
   liveness (see ``liveness.py``) and *never* treating a match as sufficient -
   this module only reports identity, never permission.
2. **A similar-looking person.** Two people can score above the threshold by
   accident. Fixed by the runner-up margin: if the second-best match is within
   ``MARGIN_MIN`` of the best, the verdict is ``ambiguous`` and access is
   refused.
3. **One lucky frame.** A single blurred or badly-lit frame can match wrongly.
   Fixed by frame voting: an identity must win a majority of the recent
   judgements, and each frame must clear a quality gate before it counts.
4. **Assuming the owner from an unknown face.** Fixed by failing closed:
   unknown is ``known=False, owner=False``, never a fallback to the owner.
"""
from __future__ import annotations

import time

import numpy as np

import auth_wall
import config
import vault

UNKNOWN = "unknown"


def _best_over_templates(embedding, person: dict) -> tuple[float, dict | None]:
    """Best cosine similarity between one embedding and one person's samples."""
    best, best_template = -1.0, None
    for template in person.get("templates", []):
        score = auth_wall.similarity(embedding, vault.list_to_vector(template["vector"]))
        if score > best:
            best, best_template = score, template
    return best, best_template


def match(embedding, store: dict) -> dict:
    """Rank every enrolled person against one embedding.

    Returns a structured verdict - no exceptions, no side effects, so it can be
    unit-tested and logged as-is:

        {
          "status": "owner" | "known" | "ambiguous" | "unknown",
          "name": str | None, "role": str | None,
          "score": float, "runner_up": float, "margin": float,
          "template_bucket": str | None,
          "threshold": float,
        }
    """
    people = store.get("people", [])
    if not people:
        return {"status": UNKNOWN, "name": None, "role": None, "score": 0.0,
                "runner_up": 0.0, "margin": 0.0, "template_bucket": None,
                "threshold": config.OWNER_THRESHOLD, "reason": "nobody enrolled"}

    ranked = []
    for person in people:
        score, template = _best_over_templates(embedding, person)
        ranked.append((score, person, template))
    ranked.sort(key=lambda item: item[0], reverse=True)

    best_score, best_person, best_template = ranked[0]
    runner_up = ranked[1][0] if len(ranked) > 1 else -1.0
    margin = best_score - runner_up if runner_up > -1.0 else 1.0
    is_owner = best_person.get("role") == "owner"
    threshold = config.OWNER_THRESHOLD if is_owner else config.KNOWN_THRESHOLD

    verdict = {
        "score": round(float(best_score), 4),
        "runner_up": round(float(runner_up), 4),
        "margin": round(float(margin), 4),
        "template_bucket": (best_template or {}).get("bucket"),
        "threshold": threshold,
    }

    if best_score < threshold:
        verdict.update(status=UNKNOWN, name=None, role=None,
                       reason=f"best match {best_score:.2f} below {threshold:.2f}")
        return verdict

    if runner_up > -1.0 and margin < config.MARGIN_MIN:
        # Two people are almost equally good. Guessing here is exactly how a
        # lookalike, a twin or a sibling gets in. Refuse instead.
        verdict.update(status="ambiguous", name=None, role=None,
                       reason=f"two candidates within {config.MARGIN_MIN:.2f} "
                              f"(best {best_score:.2f}, runner-up {runner_up:.2f})")
        return verdict

    verdict.update(status="owner" if is_owner else "known",
                   name=best_person["name"], role=best_person.get("role"),
                   reason="clear best match")
    return verdict


class VoteWindow:
    """Frame voting - an identity must be consistent across recent frames.

    One frame is a weak signal; several agreeing frames are strong. The window
    also remembers *why* frames were skipped, so the UI can explain a timeout
    ("4 frames were too blurry") instead of showing a bare failure.
    """

    def __init__(self, window: int = config.CONFIRM_WINDOW,
                 votes: int = config.CONFIRM_VOTES):
        self.window = max(2, window)
        self.votes = max(1, votes)
        self._entries: list[dict] = []
        self.skipped: list[str] = []
        self.started = time.time()

    def add(self, verdict: dict, quality_score: float):
        self._entries.append({"name": verdict.get("name"),
                              "status": verdict.get("status"),
                              "score": verdict.get("score", 0.0),
                              "quality": quality_score,
                              "time": time.time()})
        if len(self._entries) > self.window:
            self._entries.pop(0)

    def skip(self, reason: str):
        self.skipped.append(reason)
        if len(self.skipped) > 20:
            self.skipped.pop(0)

    def decision(self) -> dict:
        """Current best guess from the votes cast so far."""
        names = [e["name"] for e in self._entries
                 if e["name"] and e["status"] in ("owner", "known")]
        if not names:
            return {"decided": False, "name": None, "status": UNKNOWN,
                    "votes": 0, "frames": len(self._entries)}
        tally: dict[str, int] = {}
        for name in names:
            tally[name] = tally.get(name, 0) + 1
        name, count = max(tally.items(), key=lambda kv: kv[1])
        agreed = [e for e in self._entries if e["name"] == name]
        status = agreed[-1]["status"] if agreed else UNKNOWN
        decided = count >= self.votes
        return {"decided": decided, "name": name if decided else None,
                "status": status if decided else UNKNOWN,
                "votes": count, "frames": len(self._entries),
                "mean_score": round(float(np.mean([e["score"] for e in agreed])), 4)
                if agreed else 0.0}

    def elapsed(self) -> float:
        return time.time() - self.started

    def timed_out(self) -> bool:
        return self.elapsed() > config.VERIFY_TIMEOUT


def evaluate_reading(reading: dict, store: dict) -> dict:
    """Quality-gate one face reading, then match it.

    Quality gating before matching is important: a blurred frame is more likely
    to produce a *wrong* high score than to produce no score at all.
    """
    if not reading:
        return {"status": "no_face", "name": None, "role": None, "score": 0.0,
                "quality": 0.0, "reason": "no face in frame"}

    quality = reading.get("quality", {})
    score = float(quality.get("score", 0.0))
    if score < config.ENROLL_QUALITY_MIN:
        return {"status": "low_quality", "name": None, "role": None,
                "score": 0.0, "quality": score,
                "reason": quality.get("reason", "quality too low")}

    if float(reading.get("det_score", 1.0)) < config.DETECT_SCORE_MIN:
        return {"status": "low_quality", "name": None, "role": None,
                "score": 0.0, "quality": score,
                "reason": "detector confidence too low"}

    verdict = match(reading["embedding"], store)
    verdict["quality"] = score
    verdict["bucket"] = reading.get("bucket")
    return verdict


def verify_frame(reading: dict, store: dict) -> dict:
    """Alias kept explicit for readers: one frame in, one labelled verdict out."""
    return evaluate_reading(reading, store)
