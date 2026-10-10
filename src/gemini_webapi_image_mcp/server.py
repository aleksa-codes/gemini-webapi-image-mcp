"""
MCP Server for Gemini image generation/editing via browser cookies.

Unofficial web client (NOT the official Gemini API): authenticates with
__Secure-1PSID / __Secure-1PSIDTS cookies, same as a logged-in browser.
No API keys. Free, but cookies expire and must be refreshed periodically.

Image-only: generate, edit, reset, status. No chat.

Built on HanaokaYuzu/gemini-webapi (2.x). The request layer is patched
with browser-captured parameters that route to the fast image path;
response parsing, model discovery, and full-size downloads are native
to the library.
"""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Optional

from mcp.server.fastmcp import FastMCP, Context

# ---------------------------------------------------------------------------
# Logging (stderr only — stdout reserved for MCP stdio transport)
# ---------------------------------------------------------------------------
logger = logging.getLogger("gemini_image_mcp")
logger.addHandler(logging.StreamHandler(sys.stderr))
logger.setLevel(logging.INFO)
logger.propagate = False  # own stderr handler only — root propagation double-prints

# gemini_webapi logs cookie/init progress through loguru at DEBUG; keep it
# quiet unless someone debugs the library itself.
try:
    from loguru import logger as _loguru

    _loguru.disable("gemini_webapi")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
_env_output_dir = os.environ.get("GEMINI_OUTPUT_DIR")
IMAGES_DIR = Path(_env_output_dir).expanduser().resolve() if _env_output_dir else Path.home() / "Pictures" / "gemini"

# Hard ceiling for a single generation call (seconds). Override with GEMINI_GEN_TIMEOUT.
GEN_TIMEOUT = float(os.environ.get("GEMINI_GEN_TIMEOUT", "600"))
# Per-image cap for the download+save step (seconds). Override with GEMINI_DOWNLOAD_TIMEOUT.
DOWNLOAD_TIMEOUT = float(os.environ.get("GEMINI_DOWNLOAD_TIMEOUT", "60"))

# Optional stage timing: set GEMINI_DEBUG_TIMING=1 to log per-stage wall-time.
_DEBUG_TIMING = os.environ.get("GEMINI_DEBUG_TIMING") == "1"
# Native full-size fetch (RPC) costs extra time per image; disable with
# GEMINI_SKIP_2X=1 to take the smaller preview instead.
_SKIP_2X = os.environ.get("GEMINI_SKIP_2X", "0") != "0"
# Skip the model-id remap in patched_request (which forces the fast image
# model). Set to "1" to send the discovered model as-is. Debugging only.
_NO_REMAP = os.environ.get("GEMINI_NO_REMAP") == "1"
# Skip the browser body-param injection, keeping header override + temp flag.
# Diagnostic only: bisects Google-side 4xx/auth failures. Debugging only.
_NO_BODY = os.environ.get("GEMINI_NO_BODY") == "1"

# Natural-language aspect hints appended to the prompt (Nano Banana follows
# phrasing better than parameters). 1:1 is the model default, no hint needed.
_ASPECT_HINTS = {
    "1:1": "",
    "16:9": "wide landscape 16:9 aspect ratio",
    "9:16": "tall portrait 9:16 aspect ratio",
    "4:3": "4:3 aspect ratio",
    "3:2": "3:2 aspect ratio",
}


def _stage(label: str, t0: float) -> float:
    """Log elapsed seconds since t0 for a named stage when timing is enabled."""
    import time
    now = time.monotonic()
    if _DEBUG_TIMING:
        logger.info("[timing] %s: %.2fs", label, now - t0)
    return now

# ---------------------------------------------------------------------------
# Cookie resolution: env vars → browser-cookie3 → error
# ---------------------------------------------------------------------------

def _resolve_cookies() -> tuple[str, str]:
    """Resolve Gemini auth cookies with clear priority chain.

    1. Environment variables GEMINI_PSID / GEMINI_PSIDTS (explicit override).
    2. Chrome browser cookies via browser-cookie3 (automatic).
    3. RuntimeError with actionable instructions.

    Returns (psid, psidts). psidts may be empty.
    Cookie values are never logged.
    """
    # --- Priority 1: explicit env vars ---
    psid = os.environ.get("GEMINI_PSID", "")
    psidts = os.environ.get("GEMINI_PSIDTS", "")
    if psid:
        logger.info("Using Gemini cookies from environment variables")
        return psid, psidts

    # --- Priority 2: Chrome browser cookies ---
    try:
        import browser_cookie3

        cookie_file = os.environ.get("CHROME_COOKIE_FILE") or None
        cj = browser_cookie3.chrome(domain_name=".google.com", cookie_file=cookie_file)
        for cookie in cj:
            if cookie.name == "__Secure-1PSID" and cookie.value:
                psid = cookie.value
            elif cookie.name == "__Secure-1PSIDTS" and cookie.value:
                psidts = cookie.value
        if psid:
            logger.info("Using Gemini cookies from Chrome browser")
            return psid, psidts
        logger.warning("browser-cookie3: no __Secure-1PSID cookie found in Chrome")
    except ImportError:
        logger.warning("browser-cookie3 not installed — cannot read cookies from Chrome")
    except Exception as exc:
        logger.warning("browser-cookie3: failed to read Chrome cookies — %s", type(exc).__name__)

    # --- Nothing worked ---
    raise RuntimeError(
        "Gemini cookies not found. Options:\n"
        "  1. Log into gemini.google.com in Chrome and install browser-cookie3, or\n"
        "  2. Set GEMINI_PSID (and optionally GEMINI_PSIDTS) environment variables."
    )


# ---------------------------------------------------------------------------
# Lifespan: initialise GeminiClient once, reuse across all tool calls
# ---------------------------------------------------------------------------

@asynccontextmanager
async def app_lifespan(server):
    from gemini_webapi import GeminiClient

    psid, psidts = _resolve_cookies()

    account_index = int(os.environ.get("GEMINI_ACCOUNT_INDEX", "0"))
    client = GeminiClient(secure_1psid=psid, secure_1psidts=psidts or None, account_index=account_index)
    if account_index:
        logger.info("Using Google account index: %d", account_index)
    await client.init(timeout=300, watchdog_timeout=45, auto_close=False, auto_refresh=True)
    _patch_client(client)

    yield {"gemini_client": client}

    await client.close()


mcp = FastMCP("gemini-webapi-image-mcp", lifespan=app_lifespan)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_client(ctx: Context):
    return ctx.request_context.lifespan_context["gemini_client"]


_image_mode = False
_temporary_mode = False
_image_lock = asyncio.Lock()


def _patch_client(gemini_client):
    """Patch GeminiClient request layer for fast image generation.

    1. Override model ID in header (Google rotates IDs periodically).
    2. Add browser-compatible body params during image generation.
    3. Inject the temporary (no-history) flag when requested.

    Response parsing, model discovery, and full-size downloads are native
    to gemini-webapi 2.x and intentionally left alone.
    """
    # Model id used by the browser for fast image generation (Flash).
    # Override via GEMINI_IMAGE_MODEL_ID if Google rotates it.
    _IMAGE_MODEL_ID = os.environ.get("GEMINI_IMAGE_MODEL_ID", "56fdd199312815e2")
    # Capability flags array — the browser sends [4,5,6,8].
    _IMAGE_MODEL_CAPS = "[4,5,6,8]"

    # Browser-compatible body params (indices in inner_req_list), captured from a
    # real browser image-generation request. These route the request to the fast
    # image path.
    _BROWSER_PARAMS = {
        1: [os.environ.get("GEMINI_LANGUAGE", "en")],
        6: [1],
        7: 1,
        10: 1,
        11: 0,
        17: [[1]],
        18: 0,
        27: 1,
        30: [4],
        41: [1],
        53: 0,
        61: [],
        68: 2,
    }

    http = gemini_client.client  # curl_cffi.AsyncSession
    _orig_request = http.request

    async def patched_request(method, url, **kwargs):
        global _image_mode, _temporary_mode

        # Only touch StreamGenerate traffic issued while an image tool runs.
        if not (method == "POST" and "StreamGenerate" in str(url) and _image_mode):
            return await _orig_request(method, url, **kwargs)

        headers = kwargs.get("headers") or {}

        # Per-request UUID — the browser uses an UPPERCASE uuid, embedded in
        # both jspb headers AND inner[59], all three must match.
        req_uuid = str(uuid.uuid4()).upper()

        # Replace the model header with the exact browser shape for fast image
        # generation. Browser: [1,null,null,null,"<id>",null,null,0,[4,5,6,8],null,null,2,null,null,1,1,"<UUID>"]
        if not _NO_REMAP:
            headers["x-goog-ext-525001261-jspb"] = (
                '[1,null,null,null,"' + _IMAGE_MODEL_ID + '",null,null,0,'
                + _IMAGE_MODEL_CAPS + ',null,null,2,null,null,1,1,"' + req_uuid + '"]'
            )

        headers["x-goog-ext-73010989-jspb"] = "[0]"
        headers["x-goog-ext-73010990-jspb"] = "[0,0,0]"
        headers["x-goog-ext-525005358-jspb"] = json.dumps([req_uuid, 1])

        kwargs["headers"] = headers

        # Inject browser-compatible body params into f.req
        data = kwargs.get("data")
        if isinstance(data, dict) and "f.req" in data:
            try:
                outer = json.loads(data["f.req"])
                inner = json.loads(outer[1])
                # Force the captured browser values (overwrite: the library
                # pre-sets some of these to slow-path values).
                if not _NO_BODY:
                    for idx, val in _BROWSER_PARAMS.items():
                        if idx < len(inner):
                            inner[idx] = val
                # Sync UUID with header
                if len(inner) > 59:
                    inner[59] = req_uuid

                # Temporary (no-history) flag.
                if _temporary_mode:
                    if len(inner) > 45:
                        inner[45] = 1
                    else:
                        inner.extend([None] * (46 - len(inner)))
                        inner[45] = 1

                # Fix file_data format for edits:
                # Library:  [[[url], "name"]]
                # Browser:  [[[url, 1, null, "mime"], "name", null*6, [0]]]
                file_data = inner[0][3] if isinstance(inner[0], list) and len(inner[0]) > 3 else None
                if file_data and isinstance(file_data, list):
                    _MIME_MAP = {
                        ".png": "image/png", ".jpg": "image/jpeg",
                        ".jpeg": "image/jpeg", ".webp": "image/webp",
                        ".gif": "image/gif", ".bmp": "image/bmp",
                    }
                    for fd in file_data:
                        if isinstance(fd, list) and len(fd) == 2:
                            url_arr, filename = fd[0], fd[1]
                            if isinstance(url_arr, list) and len(url_arr) == 1:
                                ext = Path(filename).suffix.lower() if isinstance(filename, str) else ""
                                mime = _MIME_MAP.get(ext, "image/png")
                                fd[0] = [url_arr[0], 1, None, mime]
                                fd.extend([None, None, None, None, None, None, [0]])

                outer[1] = json.dumps(inner)
                data["f.req"] = json.dumps(outer)
                kwargs["data"] = data
                if _DEBUG_TIMING:
                    logger.info("[req] model_hdr=%s", headers.get("x-goog-ext-525001261-jspb"))
            except Exception as _e:
                if _DEBUG_TIMING:
                    logger.warning("[req] patch failed: %s", _e)

        return await _orig_request(method, url, **kwargs)

    http.request = patched_request
    logger.info("Patched GeminiClient with browser-compatible parameters")


def _handle_error(e: Exception) -> str:
    from gemini_webapi import AuthError, APIError
    from gemini_webapi.exceptions import (
        TimeoutError as GeminiTimeoutError,
        ImageGenerationError,
        TemporarilyBlockedError,
    )

    if isinstance(e, AuthError):
        return (
            "Error: Authentication failed. Cookies may have expired. "
            "Refresh GEMINI_PSID / GEMINI_PSIDTS from a logged-in Chrome session, then call reset."
        )
    if isinstance(e, ImageGenerationError):
        return (
            "Error: Image generation blocked for this account. This may be due to "
            "regional restrictions or account limitations — cookies alone cannot fix it."
        )
    if isinstance(e, TemporarilyBlockedError):
        return "Error: Gemini is throttling this account right now. Wait a few minutes and try again."
    if isinstance(e, GeminiTimeoutError):
        return "Error: Request timed out. Try again or simplify the prompt."
    if isinstance(e, APIError):
        return f"Error: Gemini API error — {e}"
    return f"Error: {type(e).__name__} — {e}"


def _with_aspect(prompt: str, aspect_ratio: Optional[str]) -> str:
    """Append a natural-language aspect hint (Nano Banana follows phrasing, not params)."""
    if not aspect_ratio:
        return prompt
    hint = _ASPECT_HINTS.get(aspect_ratio.strip(), aspect_ratio.strip())
    if not hint:
        return prompt
    return f"{prompt.rstrip()} ({hint})."


async def _generate(
    client,
    prompt: str,
    files: Optional[list[str]],
    conversation_id: Optional[list[str]],
    output_dir: Optional[str],
) -> str:
    """Shared generate/edit core. Returns JSON with saved paths + conversation_id."""
    import time
    t0 = time.monotonic()
    try:
        # Resolve output directory: per-call param > IMAGES_DIR (respects GEMINI_OUTPUT_DIR)
        save_dir = Path(output_dir).expanduser().resolve() if output_dir else IMAGES_DIR

        # Validate input files
        resolved_files = []
        if files:
            for f in files:
                p = Path(f).expanduser().resolve()
                if not p.exists():
                    return f"Error: File not found — {p}"
                resolved_files.append(str(p))

        async with _image_lock:
            t = _stage("acquired image lock", t0)
            global _image_mode
            _image_mode = True
            try:
                if conversation_id:
                    chat = client.start_chat(metadata=conversation_id)
                    gen_coro = chat.send_message(prompt, files=resolved_files or None)
                else:
                    gen_coro = client.generate_content(
                        prompt, files=resolved_files or None
                    )
                # Hard cap: never let the library's stall-retry loop run for
                # minutes when Gemini throttles the account. Fail fast instead.
                response = await asyncio.wait_for(gen_coro, timeout=GEN_TIMEOUT)
            except asyncio.TimeoutError:
                logger.warning("generate_content exceeded %.0fs cap — aborting", GEN_TIMEOUT)
                return (
                    f"Error: Gemini did not return an image within {GEN_TIMEOUT:.0f}s. Try again."
                )
            finally:
                _image_mode = False
            _stage("generate_content returned", t)

            conv_id = list(conversation_id[:3]) if conversation_id else None
            if chat:
                conv_id = [chat.cid or "", chat.rid or "", chat.rcid or ""]
            elif getattr(response, "metadata", None):
                conv_id = list(response.metadata[:3])

        if not response.images:
            return response.text or "No images were generated. Try rephrasing your prompt."

        save_dir.mkdir(parents=True, exist_ok=True)
        saved = []

        for i, image in enumerate(response.images):
            try:
                # Native full-size fetch (RPC) with a hard per-image cap so a
                # stalled CDN fetch can never hang the call forever.
                filepath = await asyncio.wait_for(
                    image.save(
                        path=str(save_dir),
                        filename=f"{datetime.now().strftime('%Y%m%d%H%M%S')}_{i}.png",
                        verbose=False,
                        full_size=not _SKIP_2X,
                    ),
                    timeout=DOWNLOAD_TIMEOUT,
                )
            except asyncio.TimeoutError:
                logger.warning("Image save exceeded %.0fs cap for image %d", DOWNLOAD_TIMEOUT, i)
                continue
            except Exception as save_err:
                logger.warning("Image save failed for %d: %s", i, save_err)
                continue
            t = _stage(f"download+save image {i}", t)

            if not filepath:
                continue

            title = getattr(image, "title", None) or f"image_{i}"
            saved.append({"title": title, "path": filepath, "dir": str(save_dir)})

        result = {
            "text": response.text or "",
            "images_saved_to": str(save_dir),
            "images": saved,
            "conversation_id": conv_id,
        }
        return json.dumps(result, ensure_ascii=False, indent=2)

    except Exception as e:
        return _handle_error(e)


# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@mcp.tool(
    name="generate_image",
    annotations={
        "title": "Generate Image",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def generate_image(
    prompt: str,
    ctx: Context,
    aspect_ratio: Optional[str] = None,
    conversation_id: Optional[list[str]] = None,
    temporary: bool = True,
    output_dir: Optional[str] = None,
) -> str:
    """Generate an image from a text description with Nano Banana.

    Pass conversation_id from a previous call to keep refining in the same
    thread (e.g. "make it more dramatic"). You can also use a cid from the
    Gemini web URL (gemini.google.com/app/{cid}).

    Images save to ~/Pictures/gemini/ by default (GEMINI_OUTPUT_DIR env var
    or output_dir param override).

    Args:
        prompt: Natural-language scene description (see skill prompting guide).
        aspect_ratio: 1:1 (default), 16:9, 9:16, 4:3, or 3:2.
        conversation_id: Optional [cid, rid, rcid] from a previous response.
        temporary: Default True — not saved to Gemini history. Set False to persist.
        output_dir: Directory for saved images. Supports ~ and relative paths.

    Returns:
        JSON with saved image paths and conversation_id for continuation.
    """
    global _temporary_mode
    _temporary_mode = temporary
    try:
        client = _get_client(ctx)
        return await _generate(
            client,
            _with_aspect(prompt, aspect_ratio),
            files=None,
            conversation_id=conversation_id,
            output_dir=output_dir,
        )
    finally:
        _temporary_mode = False


@mcp.tool(
    name="edit_image",
    annotations={
        "title": "Edit Image",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True,
    },
)
async def edit_image(
    paths: list[str],
    prompt: str,
    ctx: Context,
    aspect_ratio: Optional[str] = None,
    conversation_id: Optional[list[str]] = None,
    temporary: bool = True,
    output_dir: Optional[str] = None,
) -> str:
    """Edit/transform existing image(s) with Nano Banana.

    Args:
        paths: Local image file paths (at least one). Multiple allowed.
        prompt: Editing instruction (e.g. 'change the sky to sunset, keep
                everything else exactly the same').
        aspect_ratio: 1:1 (default), 16:9, 9:16, 4:3, or 3:2.
        conversation_id: Optional [cid, rid, rcid] from a previous response.
        temporary: Default True — not saved to Gemini history. Set False to persist.
        output_dir: Directory for saved images. Supports ~ and relative paths.

    Returns:
        JSON with saved image paths and conversation_id for continuation.
    """
    global _temporary_mode
    _temporary_mode = temporary
    try:
        if not paths:
            return "Error: edit_image needs at least one image path."
        client = _get_client(ctx)
        return await _generate(
            client,
            _with_aspect(prompt, aspect_ratio),
            files=paths,
            conversation_id=conversation_id,
            output_dir=output_dir,
        )
    finally:
        _temporary_mode = False


@mcp.tool(
    name="status",
    annotations={
        "title": "Cookie Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def status(ctx: Context) -> str:
    """Check whether the Gemini cookies are valid.

    Probes a fresh client with a short timeout — does not disturb the
    shared session. If this reports expired, refresh GEMINI_PSID /
    GEMINI_PSIDTS from a logged-in Chrome (devtools → Application →
    Cookies → gemini.google.com → __Secure-1PSID and __Secure-1PSIDTS).

    Returns:
        JSON with ok flag, auth source, and config summary.
    """
    from gemini_webapi import GeminiClient, AuthError

    try:
        psid, psidts = _resolve_cookies()
    except RuntimeError as e:
        return json.dumps({"ok": False, "reason": "missing", "detail": str(e)})

    source = "env" if os.environ.get("GEMINI_PSID") else "chrome"
    probe = None
    try:
        probe = GeminiClient(secure_1psid=psid, secure_1psidts=psidts or None)
        await asyncio.wait_for(
            probe.init(timeout=60, watchdog_timeout=15, auto_close=False, auto_refresh=False),
            timeout=90,
        )
        return json.dumps({
            "ok": True,
            "source": source,
            "cookies": {"psid": f"{len(psid)} chars", "psidts": f"{len(psidts)} chars"},
            "output_dir": str(IMAGES_DIR),
        })
    except AuthError:
        return json.dumps({
            "ok": False,
            "reason": "expired",
            "detail": (
                "Cookies rejected by Google. Refresh from a logged-in Chrome: "
                "devtools → Application → Cookies → https://gemini.google.com → "
                "copy __Secure-1PSID and __Secure-1PSIDTS into GEMINI_PSID / GEMINI_PSIDTS."
            ),
        })
    except Exception as e:
        return json.dumps({"ok": False, "reason": "probe_failed", "detail": f"{type(e).__name__}: {e}"})
    finally:
        if probe is not None:
            try:
                await probe.close()
            except Exception:
                pass


@mcp.tool(
    name="reset",
    annotations={
        "title": "Reset Client",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False,
    },
)
async def reset(ctx: Context) -> str:
    """Re-initialise the client (refresh cookies, clear state).

    Use after updating GEMINI_PSID / GEMINI_PSIDTS, or when calls fail
    with authentication errors.

    Returns:
        Confirmation message or error.
    """
    try:
        from gemini_webapi import GeminiClient

        old = _get_client(ctx)
        await old.close()

        psid, psidts = _resolve_cookies()

        account_index = int(os.environ.get("GEMINI_ACCOUNT_INDEX", "0"))
        new_client = GeminiClient(
            secure_1psid=psid, secure_1psidts=psidts or None, account_index=account_index
        )
        await new_client.init(timeout=300, watchdog_timeout=45, auto_close=False, auto_refresh=True)
        _patch_client(new_client)

        ctx.request_context.lifespan_context["gemini_client"] = new_client
        return "Client re-initialised with fresh cookies."
    except Exception as e:
        return _handle_error(e)
