# GPT Configuration Guide for Meo Mai Moi

This document describes how to configure a Custom GPT to safely and effectively interact with the meo-gpt-connector service.

---

# 1. GPT Instructions (System Behavior)

Use clear, rule-based instructions. Avoid vague personality prompts.

## Recommended Instruction Template

You are the Meo Mai Moi assistant.

Your responsibilities:

* Help users manage their pets.
* Ask clarifying questions when required fields are missing.
* Never guess or fabricate IDs or stored data.
* Always rely on tool responses for factual information.
* Confirm successful operations clearly and concisely.
* If an API call returns an error, explain it and request correction.

Tool usage rules:

* Call tools only when all required fields are available.
* Do not call tools speculatively.
* Do not repeat tool calls unless correcting an error.

Tone guidelines:

* Friendly but concise.
* Clear confirmations after successful operations.

---

# 2. Actions Configuration

In GPT Builder:

1. Open "Configure"
2. Go to "Actions"
3. Add a new action
4. Provide:

   * Base URL of meo-gpt-connector
   * OpenAPI schema URL or upload JSON

---

# 3. Authentication Setup

Select OAuth authentication.

Required fields:

* Authorization URL (connector endpoint)
* Token URL
* Client ID / Client Secret
* Scopes (if applicable)

Flow:

* User attempts first protected action
* GPT platform prompts user to connect
* User logs in via connector
* Platform stores token
* Future requests include token automatically

The GPT never sees the token directly.

---

# 4. Tool Schema Design Best Practices

Design OpenAPI with LLM compatibility in mind.

## Example: Create Pet

POST /pets

Request body:
{
"name": "string",
"species": "string",
"sex": "male" | "female",
"birth_date": "YYYY-MM-DD"
}

Mark required fields explicitly.

Avoid optional overloads or ambiguous unions.

---

# 5. Handling Missing Information

The GPT should:

User: "Create a cat named Mimi."

Assistant:

* Ask for missing fields (sex, birth_date)
* Wait for answer
* Then call POST /pets

Never call the API with partial required data.

---

# 6. Handling Updates

Use PATCH /pets/{id} for partial updates.

Workflow:

1. If pet ID is unknown, call GET /pets first.
2. Identify correct pet.
3. Confirm with user if ambiguous.
4. Then call PATCH.

---

# 7. Error Recovery Pattern

If connector returns:

{
"error": "VALIDATION_ERROR",
"message": "birth_date must be YYYY-MM-DD"
}

The GPT should:

* Explain the issue
* Ask user for correction
* Retry the tool call with corrected value

---

# 8. Conversation Design Principles

* Confirm operations after success.
* When listing pets, format cleanly.
* Do not invent data if retrieval fails.
* Encourage correction when ambiguity exists.

---

# 9. Testing Checklist

Before production:

* Test missing field flows
* Test invalid date formats
* Test duplicate names
* Test unauthorized access
* Test revoked tokens
* Test network failure simulation

---

# 10. Minimal Viable Tool Set

For MVP:

* POST /pets
* GET /pets
* PATCH /pets/{id}
* POST /pets/{id}/documents
* Auth endpoints

Add advanced endpoints later only after validating chat UX.

---

# 11. Deployment Considerations

* Ensure HTTPS only
* Enable rate limiting
* Log request_id for each call
* Monitor error frequency

---

# Final Note

The GPT is an interpreter of intent.
The backend is the executor of truth.

Keep them separate.
Keep them constrained.
Keep them observable.
