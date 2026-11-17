---
name: gemini-image
description: 'Use this skill when the user asks for image generation, image editing, visual concepts, or assets, or wants to iterate on an existing image. Generates and edits images with Gemini Nano Banana via unofficial web-client cookies (no API keys, free, temporary by default). Triggers on: generate image, edit image, Nano Banana, Gemini image, make a picture, create an image, image prompt, aspect ratio, conversation_id. Tools: generate_image, edit_image, status, reset. Invoke through execute with bracket notation: tools["gemini-image"]["generate_image"]({...}).'
---

# Gemini Image MCP

Image generation and editing through `gemini.google.com` (unofficial web client, cookie auth — not the official API).

## Calling the tools

These are **MCP tools**, not skill functions. The skill only provides guidance; it does not generate images. Invoke them through `execute` using **bracket notation** — the namespace contains a hyphen, so dot access (`tools.gemini-image...`) throws `Unknown identifier`:

```js
await tools["gemini-image"]["generate_image"]({
  prompt: "A cinematic wide shot...",
  aspect_ratio: "16:9"
})
```

Same pattern for `edit_image`, `status`, and `reset`.

## Tools

- `generate_image(prompt, aspect_ratio?, conversation_id?, temporary=True, output_dir?)` — new image from text.
- `edit_image(paths, prompt, aspect_ratio?, conversation_id?, temporary=True, output_dir?)` — transform existing image(s). At least one path required.
- `status()` — validate cookies. Call first when generations fail; it tells you exactly whether cookies are missing or expired and how to refresh.
- `reset()` — re-initialise the client. Call after updating cookies, or on repeated auth errors.

## Rules

- **Always use `temporary=True`** (the default) unless the user explicitly asks to keep history.
- **Prompt well**: read `references/image-prompting.md` before generating. Natural sentences, not tag soup. Quote text to render. Prefer editing over re-rolling.
- **Aspect ratio**: pass `aspect_ratio` (`1:1`, `16:9`, `9:16`, `4:3`, `3:2`) instead of writing it into the prompt by hand.
- **Iterate**: to refine Gemini's previous output, call `generate_image` with the returned `conversation_id` and an editing prompt ("more dramatic", "add rain"). Prefer this over re-uploading the saved image. Use `edit_image` with `paths` for external images or when the original conversation is unavailable.
- **Output dir**: default `~/Pictures/gemini/`. For project assets, pass an explicit `output_dir`.
- **On auth errors**: run `status()`, follow its refresh instructions, then `reset()`. Never ask the user for passwords; cookies come from their own logged-in Chrome.
