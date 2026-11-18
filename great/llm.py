"""Ollama and optional compatible API clients: disk cache, tolerant JSON/XML extraction, retry, interaction log.

Every call is appended to pipeline/genai_logs/<run>.jsonl so that Deliverable 5
("GenAI Interaction Logs -- prompts, responses, accepted/rejected outputs and
validation records") can be produced verbatim.
"""
from __future__ import annotations
import hashlib, json, re, time, os, urllib.request, urllib.error
from pathlib import Path
from . import config as C

_LOG_PATH: Path | None = None
MIN_PREDICT = 1500
MAX_PREDICT = 12000

_STATS = {"calls": 0, "cache_hits": 0, "retries": 0, "gen_tokens": 0, "wall_s": 0.0}


def start_log(name: str) -> Path:
    global _LOG_PATH
    C.LOG_DIR.mkdir(parents=True, exist_ok=True)
    _LOG_PATH = C.LOG_DIR / f"{name}.jsonl"
    _LOG_PATH.write_text("")
    return _LOG_PATH


def stats() -> dict:
    return dict(_STATS)


def _log(rec: dict) -> None:
    if _LOG_PATH is None:
        return
    with _LOG_PATH.open("a") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def _key(prompt, system, temperature, seed, num_predict, fmt, backend="ollama", model=None) -> str:
    identity = [model or C.LLM_MODEL, prompt, system, temperature, seed, num_predict, fmt]
    # Preserve the established local cache for the unchanged default endpoint.
    # Explicit remote/API backends get their own namespace; credentials never
    # participate in cache filenames or logs.
    if backend != "ollama" or C.OLLAMA_HOST != "http://localhost:11434":
        identity = [backend, os.environ.get("GREAT_CROSS_MODEL_API_URL")
                    if backend == "api" else C.OLLAMA_HOST, *identity]
    blob = json.dumps(identity, sort_keys=True)
    return hashlib.sha256(blob.encode()).hexdigest()


def _post(payload: dict) -> dict:
    req = urllib.request.Request(
        f"{C.OLLAMA_HOST}/api/generate",
        data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=C.LLM_TIMEOUT) as resp:
        return json.loads(resp.read().decode())


def generate(prompt: str, *, system: str = "", temperature: float = 0.0,
             seed: int = 0, num_predict: int = 2048, fmt: str | None = None,
             think: bool | None = None, tag: str = "", phase: str = "",
             backend: str = "ollama", model: str | None = None,
             ensemble_kind: str | None = None) -> str:
    """One completion.  fmt='json' asks Ollama to constrain output to JSON."""
    # This model emits an internal reasoning pass before its answer; a small
    # generation budget is consumed entirely by that pass and yields an empty
    # body, so never ask for fewer than MIN_PREDICT tokens.
    if backend not in ("ollama", "api"):
        raise ValueError(f"unsupported LLM backend: {backend}")
    model = model or C.LLM_MODEL
    # Dataset jobs can select the same model's non-thinking mode explicitly.
    # Resolve it before the cache key so outputs from different modes cannot mix.
    if think is None and backend == "ollama" and "GREAT_LLM_THINK" in os.environ:
        mode = os.environ["GREAT_LLM_THINK"].strip().lower()
        if mode not in {"0", "false", "off", "1", "true", "on"}:
            raise ValueError("GREAT_LLM_THINK must be a boolean")
        think = mode in {"1", "true", "on"}
    num_predict = max(num_predict, MIN_PREDICT)
    ck = _key(prompt, system, temperature, seed, num_predict, (fmt, think), backend, model)
    cache_file = C.CACHE_DIR / f"{ck}.json"
    if C.LLM_CACHE and cache_file.exists():
        cached = json.loads(cache_file.read_text())
        _STATS["calls"] += 1
        _STATS["cache_hits"] += 1
        _log({"ts": time.time(), "phase": phase, "tag": tag, "cached": True,
              "model": model, "backend": backend, "ensemble_kind": ensemble_kind, "think": think, "system": system, "prompt": prompt,
              "response": cached["response"]})
        return cached["response"]

    # Ollama defaults to a 4096-token context; anything longer is silently
    # truncated and this model then returns an empty body.  Size the window to
    # the actual prompt (~3.4 chars/token) plus the generation budget.
    est = int((len(prompt) + len(system)) / 3.4) + num_predict + 512
    num_ctx = max(4096, min(C.LLM_MAX_CTX, 1 << (est - 1).bit_length()))
    payload = {"model": model, "prompt": prompt, "stream": False,
               "options": {"temperature": temperature, "seed": seed,
                           "num_predict": num_predict, "num_ctx": num_ctx}}
    if system:
        payload["system"] = system
    if fmt:
        payload["format"] = fmt
    if think is not None:
        payload["think"] = think

    t0, last_err = time.time(), None
    for attempt in range(3):
        try:
            if backend == "ollama":
                data = _post(payload)
            else:
                messages = ([{"role": "system", "content": system}] if system else [])
                messages.append({"role": "user", "content": prompt})
                req = urllib.request.Request(
                    os.environ["GREAT_CROSS_MODEL_API_URL"],
                    data=json.dumps({"model": model, "messages": messages,
                                     "temperature": temperature,
                                     "max_tokens": payload["options"]["num_predict"]}).encode(),
                    headers={"Content-Type": "application/json",
                             "Authorization": "Bearer " + os.environ["GREAT_CROSS_MODEL_API_KEY"]})
                with urllib.request.urlopen(req, timeout=C.LLM_TIMEOUT) as response:
                    api = json.loads(response.read())
                data = {"response": api["choices"][0]["message"]["content"],
                        "eval_count": api.get("usage", {}).get("completion_tokens", 0)}
            text = data.get("response", "")
            if not text.strip():
                # Empty body.  With this reasoning model the usual cause is that
                # the hidden reasoning pass consumed the entire generation budget
                # before any answer token was emitted -- re-rolling the seed at the
                # same budget mostly reproduces the failure.  So each retry also
                # doubles the budget (and the context window to fit it).  The cache
                # key was computed from the ORIGINAL parameters above, so a
                # successful retry is still found by the next identical request.
                payload["options"]["seed"] = int(seed) + 101 * (attempt + 1)
                grown = min(payload["options"]["num_predict"] * 2, MAX_PREDICT)
                payload["options"]["num_predict"] = grown
                need = int((len(prompt) + len(system)) / 3.4) + grown + 512
                payload["options"]["num_ctx"] = max(
                    payload["options"]["num_ctx"],
                    min(C.LLM_MAX_CTX * 2, 1 << (need - 1).bit_length()))
                raise ValueError(f"empty response body from model "
                                 f"(retrying with num_predict={grown})")
            dt = time.time() - t0
            _STATS["calls"] += 1
            _STATS["gen_tokens"] += data.get("eval_count", 0) or 0
            _STATS["wall_s"] += dt
            C.CACHE_DIR.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(json.dumps({"response": text}))
            _log({"ts": time.time(), "phase": phase, "tag": tag, "cached": False,
                  "model": model, "backend": backend, "ensemble_kind": ensemble_kind, "temperature": temperature, "seed": seed, "num_ctx": num_ctx, "think": think,
                  "system": system, "prompt": prompt, "response": text,
                  "eval_count": data.get("eval_count"), "wall_s": round(dt, 2),
                  "attempt": attempt})
            return text
        except Exception as exc:                       # noqa: BLE001
            last_err = exc
            _STATS["retries"] += 1
            _log({"ts": time.time(), "phase": phase, "tag": tag,
                  "model": model, "backend": backend, "ensemble_kind": ensemble_kind,
                  "error": f"{type(exc).__name__}: {exc}", "attempt": attempt})
            time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"LLM call '{tag}' failed after 3 attempts: {last_err}")


# ------------------------------------------------------------------ parsing
_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.S)
_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


def strip_reasoning(text: str) -> str:
    return _THINK.sub("", text).strip()


def close_truncated(text: str):
    """Recover a JSON value whose tail was cut off by the generation budget.

    A reasoning model that runs out of tokens stops mid-structure, e.g. inside
    the last string of a `"reasoning": [ ...` array.  The balanced-brace scan
    below would then skip the unterminated outer object and return the first
    complete INNER fragment -- one `recovered_constants` entry -- as if it were
    the whole answer, which silently corrupted the Phase-6 score.  Here we walk
    from the first opener, cut back to the last point where the structure was
    consistent, and append the closers still owed, keeping everything the model
    actually finished.
    """
    starts = [i for i in (text.find("{"), text.find("[")) if i != -1]
    if not starts:
        return None
    body = text[min(starts):]
    stack, in_str, esc, last_safe = [], False, False, None
    for i, ch in enumerate(body):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
            continue
        if ch == '"':
            in_str = True
        elif ch in "{[":
            stack.append("}" if ch == "{" else "]")
        elif ch in "}]":
            if not stack:
                return None
            stack.pop()
            if not stack:
                return None                  # complete value: not truncation
            last_safe = (i + 1, list(stack))
        elif ch == "," and stack:
            last_safe = (i, list(stack))     # cut just before this separator
    if not stack or last_safe is None:
        return None
    cut, owed = last_safe
    candidate = body[:cut].rstrip().rstrip(",") + "".join(reversed(owed))
    try:
        return json.loads(candidate)
    except Exception:                                  # noqa: BLE001
        return None


def extract_json(text: str):
    """Tolerant JSON recovery: fenced block, then first balanced {...} / [...]."""
    text = strip_reasoning(text)
    for cand in [text, *(m.group(1) for m in _FENCE.finditer(text))]:
        cand = cand.strip()
        try:
            return json.loads(cand)
        except Exception:                              # noqa: BLE001
            pass
    salvaged = close_truncated(text)
    if salvaged is not None:
        return salvaged
    for opener, closer in (("{", "}"), ("[", "]")):
        start = text.find(opener)
        while start != -1:
            depth, in_str, esc = 0, False, False
            for i in range(start, len(text)):
                ch = text[i]
                if in_str:
                    esc = (ch == "\\") and not esc
                    if ch == '"' and not esc:
                        in_str = False
                    continue
                if ch == '"':
                    in_str, esc = True, False
                elif ch == opener:
                    depth += 1
                elif ch == closer:
                    depth -= 1
                    if depth == 0:
                        try:
                            return json.loads(text[start:i + 1])
                        except Exception:              # noqa: BLE001
                            break
            start = text.find(opener, start + 1)
    return None


def _coerce(parsed, expect: str, key_hint: str | None):
    """Shape-guard the parsed value so callers can rely on the type they asked for.

    The model occasionally answers a "return ONE JSON object" prompt with a bare
    array (or with the object wrapped in a single-element array). Rather than let
    every call site defend itself with isinstance checks, normalise here and
    treat anything still wrong as a parse failure so the repair prompt fires.
    """
    if parsed is None or expect == "any":
        return parsed
    if expect == "object":
        if isinstance(parsed, dict):
            return parsed
        if isinstance(parsed, list):
            if len(parsed) == 1 and isinstance(parsed[0], dict):
                return parsed[0]
            if key_hint and all(isinstance(x, dict) for x in parsed):
                return {key_hint: parsed}
        return None
    if expect == "array":
        if isinstance(parsed, list):
            return parsed
        if isinstance(parsed, dict):
            for v in parsed.values():
                if isinstance(v, list):
                    return v
        return None
    return parsed


def _missing_keys(parsed, required_keys) -> list:
    if not required_keys or not isinstance(parsed, dict):
        return []
    return [k for k in required_keys if k not in parsed]


def generate_json(prompt: str, *, retry_prompt: str | None = None,
                  expect: str = "object", key_hint: str | None = None,
                  required_keys: tuple = (), **kw):
    """Ask for JSON; on parse failure re-ask once with an explicit repair prompt.

    Returns (parsed_or_None, record) where record documents accept/reject so the
    phase change-log can show the validation trail (paper Deliverable 5).
    """
    # NOTE: ollama's format="json" grammar constraint returns an empty body for
    # this model, so we rely on prompt discipline + the tolerant parser instead.
    kw.setdefault("fmt", None)
    try:
        raw = generate(prompt, **kw)
    except RuntimeError as exc:
        # A dead LLM call is a fault to be logged by the caller, never a reason
        # to abandon a phase that has already produced work.
        return None, {"parsed": False, "repaired": False, "raw_len": 0,
                      "raw_head": "", "call_failed": str(exc)}
    raw_parsed = extract_json(raw)
    parsed = _coerce(raw_parsed, expect, key_hint)
    rec = {"parsed": parsed is not None, "repaired": False,
           "raw_len": len(raw), "raw_head": raw[:400]}
    # A salvaged fragment must still look like the answer that was asked for,
    # otherwise one inner array element could be scored as a whole response.
    missing = _missing_keys(parsed, required_keys)
    if missing:
        rec["shape_rejected"] = f"parsed value lacked required keys {missing}"
        parsed = None
        raw_parsed = None
    if raw_parsed is not None and parsed is None:
        rec["shape_rejected"] = (f"expected a JSON {expect}, got "
                                 f"{type(raw_parsed).__name__}")
    if parsed is None:
        rec["rejected_response"] = raw
        rp = retry_prompt or (
            f"Your previous response was not a valid JSON {expect}.\n"
            f"Output ONE JSON {expect} and nothing else -- no prose, no markdown "
            "fences, no explanation, no surrounding array.\n\nOriginal task:\n"
            + prompt + "\n\nEND OF INPUT. Do not complete or rewrite source code. "
            + f"Answer the original analysis task with ONE JSON {expect} only. "
            + (f"Include the requested {key_hint} field." if key_hint else ""))
        kw2 = dict(kw); kw2["tag"] = kw.get("tag", "") + ":repair"
        try:
            raw2 = generate(rp, **kw2)
        except RuntimeError as exc:
            rec["call_failed"] = str(exc)
            return None, rec
        parsed = _coerce(extract_json(raw2), expect, key_hint)
        if _missing_keys(parsed, required_keys):
            parsed = None
        rec.update(repaired=True, parsed=parsed is not None, raw_head=raw2[:400])
    return parsed, rec
