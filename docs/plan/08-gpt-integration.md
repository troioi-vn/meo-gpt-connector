# 08 - GPT Integration & System Prompt

**Goal:** Fine-tune the connector's auto-generated `openapi.json` syntax so ChatGPT "vision and reasoning" inherently understands it without hallucinating.

## Definition of Done

- All FastAPI endpoints contain rich `@app.post(..., operation_id="...", description="...")` tags explicitly giving instruction to GPT.
- Custom GPT configured on `chatgpt.com`.
- Hardcoded `gpt-system-prompt.md` acts as the Custom GPT instructions.
- E2E testing using live GPT queries matches expected behaviors.

## Implementation Steps

1. **OpenAPI Schema Tuning (`src/routers/*`):**
   - Review all Pydantic schemas. Write precise docstrings for each schema variable (E.g. "Use this exact name to query duplicates...").
   - Strip ambiguous optional overloads. Force inputs strings into strict Literals/Enums (`sex: Literal['male', 'female', 'unknown']`) whenever possible.
   - Ensure `id` fields are consistently outputted so the GPT learns to chain tool responses.
2. **Setup Custom GPT (OpenAI Builder):**
   - Use URL: `https://gpt.troioi.vn/openapi.json`.
   - Authentication Type: OAuth2 Authorization Code.
   - Add Authorization endpoint: `https://gpt.troioi.vn/oauth/authorize`.
   - Add Token endpoint: `https://gpt.troioi.vn/oauth/token`.
   - Map scope placeholders and client credentials.

3. **System Prompt Updates (`docs/gpt-system-prompt.md`):**
   - Verify rules explicitly instruct: "Never invent IDs", "Always call find_pets first", "Ask for missing required fields simultaneously, not one-by-one."
   - Refine the list of tools and mapping rules context.
4. **QA (Manual Testing):**
   - Open ChatGPT in developer mode. Upload a dummy `.jpg` of a vaccination form.
   - Prompt: "Add this to Mimi's file."
   - Verify execution flow: Calls `/pets/find(Mimi)` -> Gets ID -> Extracts Photo Data via LLM vision -> calls `/pets/{id}/vaccinations`. Result = Correctly created.
