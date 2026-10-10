---
name: gemini-image-mcp
description: Generate and edit images with Gemini Nano Banana via unofficial web-client cookies. Use when the user asks for image generation, image editing, or visual concepts. No API keys, free, temporary by default.
---

# Gemini Image MCP

Image generation and editing through `gemini.google.com` (unofficial web client, cookie auth — not the official API).

## Tools

- `generate_image(prompt, aspect_ratio?, conversation_id?, temporary=True, output_dir?)` — new image from text.
- `edit_image(paths, prompt, aspect_ratio?, conversation_id?, temporary=True, output_dir?)` — transform existing image(s). At least one path required.
- `status()` — validate cookies. Call first when generations fail; it tells you exactly whether cookies are missing or expired and how to refresh.
- `reset()` — re-initialise the client. Call after updating cookies, or on repeated auth errors.

## Rules

- **Always use `temporary=True`** (the default) unless the user explicitly asks to keep history.
- **Prompt well**: read `references/image-prompting.md` before generating. Natural sentences, not tag soup. Quote text to render. Prefer editing over re-rolling.
- **Aspect ratio**: pass `aspect_ratio` (`1:1`, `16:9`, `9:16`, `4:3`, `3:2`) instead of writing it into the prompt by hand.
- **Iterate**: responses include `conversation_id` — pass it back for refinements ("more dramatic", "add rain") rather than starting over.
- **Output dir**: default `~/Pictures/gemini/`. For project assets, pass an explicit `output_dir`.
- **On auth errors**: run `status()`, follow its refresh instructions, then `reset()`. Never ask the user for passwords; cookies come from their own logged-in Chrome.
