"""The scene eye — "do you see a pen on my desk?"

This is the second thing the owner asked for: not just "who is this", but
"what is in front of me". It is deliberately a separate module from face
recognition, because the two have nothing in common:

* Face work is **local, offline and private**. Templates never leave the laptop.
* Scene questions need real visual understanding of arbitrary objects. A face
  embedder cannot do this - ArcFace only knows "face or not face". Answering
  "is there a pen" needs a vision-language model.
* A vision question therefore **sends a photo to a provider**, which is a
  privacy decision, not a technical one. So it is opt-in, it shows exactly which
  provider will see the image, and it refuses to run without an explicit,
  configured provider.

Providers, in the order the owner's constraints suggest:

1. ``local``  - an already-installed local vision model (e.g. Ollama with a
   vision model). Nothing leaves the machine, zero cost, best privacy. Used
   automatically when detected.
2. ``groq``   - the cloud provider the rest of LYA already uses, reading its key
   from LYA's own key store if available. Free-tier, but the frame is uploaded.
3. ``off``    - the default. Nothing runs and the answer says so honestly.

There is no "guess from face embeddings" fallback. A wrong "yes, I see a pen"
that was really a coin toss is worse than "I cannot see".

Cost control, matching the owner's "no load on the laptop" rule: the frame is
downscaled to ``SCENE_MAX_SIDE`` and JPEG-compressed before it is sent, a
question captures at most ``SCENE_MAX_FRAMES`` frames, and the camera is
released as soon as the answer arrives.
"""
from __future__ import annotations

import base64
import json
import os
import time
import urllib.request

import config


class SceneError(RuntimeError):
    """Raised when a scene question cannot be answered. Never faked."""


# ----------------------------------------------------------------------
# frame preparation
# ----------------------------------------------------------------------
def prepare_frame(frame_bgr, max_side: int = config.SCENE_MAX_SIDE,
                  quality: int = config.SCENE_JPEG_QUALITY) -> tuple[str, dict]:
    """Downscale and JPEG-encode one frame for a vision model.

    Returns ``(base64_jpeg, metadata)``. Downscaling is the single biggest cost
    saver: a 640x480 webcam frame at 896px costs a fraction of a phone photo,
    and a pen, a mug or a document is still plainly visible.
    """
    import cv2

    height, width = frame_bgr.shape[:2]
    scale = min(1.0, float(max_side) / float(max(height, width)))
    if scale < 1.0:
        frame_bgr = cv2.resize(
            frame_bgr, (int(width * scale), int(height * scale)),
            interpolation=cv2.INTER_AREA)
    ok, buffer = cv2.imencode(".jpg", frame_bgr,
                              [int(cv2.IMWRITE_JPEG_QUALITY), int(quality)])
    if not ok:
        raise SceneError("could not encode the camera frame")
    payload = base64.b64encode(buffer.tobytes()).decode("ascii")
    meta = {"width": int(frame_bgr.shape[1]), "height": int(frame_bgr.shape[0]),
            "bytes": int(buffer.size), "scale": round(scale, 3),
            "quality": quality}
    return payload, meta


# ----------------------------------------------------------------------
# provider discovery
# ----------------------------------------------------------------------
def _groq_key() -> str:
    """Find the Groq key the way LYA already does, without hardcoding it.

    Order: environment first (so a session can override), then LYA's own
    encrypted key store, then a plain file. If none exists the provider simply
    is not offered - we never invent a credential.
    """
    key = os.environ.get("GROQ_API_KEY", "").strip()
    if key:
        return key

    lya_security = os.path.join(os.path.dirname(config.ROOT), "security")
    for candidate in (os.path.join(lya_security, "groq_key.lya"),
                      os.path.join(lya_security, "groq_key.txt")):
        if not os.path.exists(candidate):
            continue
        try:
            if candidate.endswith(".lya"):
                import sys
                if lya_security not in sys.path:
                    sys.path.insert(0, os.path.dirname(lya_security))
                from security import vault as lya_vault

                return lya_vault.decrypt_file(candidate).decode().strip()
            with open(candidate, "r", encoding="utf-8") as handle:
                return handle.read().strip()
        except Exception:
            continue
    return ""


def _ollama_models() -> list[str]:
    """List locally installed Ollama models. Empty when Ollama is not running.

    A local model is the only way to answer a scene question with genuinely
    zero data leaving the laptop, so it is probed first and cheaply.
    """
    try:
        request = urllib.request.Request("http://127.0.0.1:11434/api/tags")
        with urllib.request.urlopen(request, timeout=1.2) as response:
            data = json.loads(response.read().decode("utf-8"))
        return [model.get("name", "") for model in data.get("models", [])]
    except Exception:
        return []


def local_vision_model() -> str | None:
    """Pick an installed local vision-capable model, if any.

    Names are matched by family because Ollama does not report vision support:
    ``llava``, ``bakllava``, ``moondream``, ``minicpm-v`` and ``qwen2-vl`` will
    accept an image; plain ``llama``/``mistral`` text models will not.
    """
    vision_markers = ("llava", "bakllava", "moondream", "minicpm-v", "qwen2-vl",
                      "qwen2.5-vl", "gemma3", "llama3.2-vision")
    for name in _ollama_models():
        lowered = name.lower()
        if any(marker in lowered for marker in vision_markers):
            return name
    return None


def provider_status() -> dict:
    """What could actually answer a scene question right now."""
    local = local_vision_model()
    groq = bool(_groq_key())
    if local:
        chosen, detail = "local", f"local vision model '{local}' (nothing uploaded)"
    elif groq:
        chosen, detail = "groq", "cloud provider - the frame will be uploaded"
    else:
        chosen, detail = "off", ("no local vision model and no provider key; "
                                 "scene questions cannot be answered")
    return {"provider": chosen, "detail": detail, "local_model": local,
            "cloud_key_present": groq,
            "endpoint": ("http://127.0.0.1:11434" if local else
                         ("https://api.groq.com" if groq else ""))}


# ----------------------------------------------------------------------
# providers
# ----------------------------------------------------------------------
def _ask_ollama(model: str, prompt: str, image_b64: str) -> str:
    body = json.dumps({
        "model": model,
        "prompt": prompt,
        "images": [image_b64],
        "stream": False,
        "options": {"temperature": 0.1, "num_predict": 220},
    }).encode("utf-8")
    request = urllib.request.Request(
        "http://127.0.0.1:11434/api/generate", data=body,
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=config.SCENE_HTTP_TIMEOUT) as response:
        return json.loads(response.read().decode("utf-8")).get("response", "").strip()


def _ask_groq(prompt: str, image_b64: str, model: str) -> str:
    key = _groq_key()
    if not key:
        raise SceneError("no cloud provider key is configured")
    body = json.dumps({
        "model": model,
        "temperature": 0.1,
        "max_tokens": 400,
        "messages": [{
            "role": "user",
            "content": [
                {"type": "text", "text": prompt},
                {"type": "image_url",
                 "image_url": {"url": f"data:image/jpeg;base64,{image_b64}"}},
            ],
        }],
    }).encode("utf-8")
    request = urllib.request.Request(
        "https://api.groq.com/openai/v1/chat/completions", data=body,
        headers={"Content-Type": "application/json",
                 "Authorization": f"Bearer {key}"})
    with urllib.request.urlopen(request, timeout=config.SCENE_HTTP_TIMEOUT) as response:
        data = json.loads(response.read().decode("utf-8"))
    return data["choices"][0]["message"]["content"].strip()


# ----------------------------------------------------------------------
# the question
# ----------------------------------------------------------------------
SYSTEM_RULES = (
    "You are looking through a single webcam frame on a person's desk. "
    "Answer only from what is actually visible in this image. "
    "If the asked object is not clearly visible, say plainly that you do not see "
    "it instead of guessing from context. "
    "Never invent objects, never claim to see something you cannot point to. "
    "Keep the answer under 70 words, plain sentences, no markdown."
)


def build_prompt(question: str, mode: str = "look") -> str:
    question = (question or "").strip()
    if mode == "find" and question:
        return (f"{SYSTEM_RULES}\n\nQuestion: is there {question} visible in this "
                f"image? Answer yes or no first, then one short sentence saying "
                f"where it is, and name anything else nearby that is relevant.")
    if question:
        return f"{SYSTEM_RULES}\n\nQuestion: {question}"
    return (f"{SYSTEM_RULES}\n\nDescribe briefly what is in front of the camera "
            f"and whether a person is present.")


def answer_question(question: str, frames: list, *, mode: str = "look",
                    provider: str | None = None) -> dict:
    """Answer one question about the scene from one or more camera frames.

    ``frames`` is a list of ``camera_control.Frame`` objects. More than one is
    useful for a "is it still there" question or when the first frame was
    blurred, but each extra frame costs money/time, so the default is one.

    Returns a structured report. On any failure it raises ``SceneError`` or
    returns ``answered=False`` with the reason - it never fabricates an answer.
    """
    started = time.time()
    status = provider_status()
    chosen = provider or status["provider"]

    if not frames:
        return {"answered": False, "provider": chosen, "answer": "",
                "reason": "no camera frame was captured",
                "elapsed": round(time.time() - started, 2)}

    if chosen == "off":
        return {"answered": False, "provider": "off", "answer": "",
                "reason": status["detail"],
                "elapsed": round(time.time() - started, 2)}

    prompt = build_prompt(question, mode)
    observations = []
    uploaded = []
    last_error = ""

    for frame in frames[:max(1, config.SCENE_MAX_FRAMES)]:
        try:
            image_b64, meta = prepare_frame(frame.bgr)
        except SceneError as exc:
            last_error = str(exc)
            continue

        uploaded.append(meta)
        try:
            if chosen == "local":
                model = status["local_model"]
                if not model:
                    raise SceneError("no local vision model is installed")
                text = _ask_ollama(model, prompt, image_b64)
            elif chosen == "groq":
                text = _ask_groq(prompt, image_b64,
                                 os.environ.get("FACE_SCENE_MODEL",
                                                "meta-llama/llama-4-scout-17b-16e-instruct"))
            else:
                raise SceneError(f"unknown provider '{chosen}'")
            if text:
                observations.append(text)
        except Exception as exc:
            last_error = str(exc)

    if not observations:
        return {"answered": False, "provider": chosen, "answer": "",
                "reason": last_error or "the provider returned nothing",
                "uploaded": uploaded, "elapsed": round(time.time() - started, 2)}

    answer = observations[0]
    if len(observations) > 1:
        # Only keep an extra frame's answer if it adds something; otherwise the
        # caller gets a confusing wall of near-identical text.
        extra = [o for o in observations[1:] if o and o not in answer]
        if extra:
            answer = answer + " (also: " + extra[0][:160] + ")"

    return {
        "answered": True,
        "provider": chosen,
        "answer": answer,
        "question": question,
        "frames_used": len(observations),
        "uploaded": uploaded,
        "privacy": ("processed on this machine; nothing was uploaded"
                    if chosen == "local" else
                    "this frame was sent to the configured cloud provider"),
        "elapsed": round(time.time() - started, 2),
    }
