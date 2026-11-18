---
name: gemini-image
description: Use when the user asks to generate or edit an image, iterate on a generated visual, or use Gemini Nano Banana for image work.
---

# Gemini Image MCP

Use the `gemini-image` MCP server. If the tools are not available, report that
instead of trying to access browser cookies directly.

1. For a new image, call `gemini-image:generate_image` with a `prompt`. To
   edit an existing image, call `gemini-image:edit_image` with the prompt
   and at least one source in `paths`. Use the bundled
   [prompting reference](references/image-prompting.md) for complex briefs.
2. Pass `aspect_ratio` separately when specified. Keep `temporary` at its
   default unless the user asks to keep history. Set `output_dir` when
   saving project assets to a specific directory.
3. Report the resulting image path. Reuse a returned `conversation_id` for
   follow-up refinements when supported by the tool.

In OpenCode Code Mode, call the tool through `execute`:

```js
await tools["gemini-image"]["generate_image"]({
  prompt: "A studio photo of a red ceramic mug on a warm gray background.",
  aspect_ratio: "4:3",
});
```

On authentication errors, call `gemini-image:status`. If it reports that
the session needs refreshing, relay its instructions and call
`gemini-image:reset` after the user refreshes it. Do not ask for passwords
or cookie values.
