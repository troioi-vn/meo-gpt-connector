# meo-gpt-connector

A small standalone service that connects a publicly discoverable **ChatGPT GPT (via Actions)** with the **Meo Mai Moi** main application API.

The goal is to ship a fast prototype that proves a “chat-first” pet management experience **without building a complex UI** in the main app. ChatGPT handles the conversational UX and (optionally) multimodal inputs; this service focuses on **auth, orchestration, and secure API calls** to the main app.

---

## What this service does

- Exposes an **Actions-compatible HTTP API** (OpenAPI schema) that a custom GPT can call.
- Handles **account connection** (login + consent) to the Meo Mai Moi main app.
- Calls the **main app API** to:
  - create and manage pets
  - upload documents (vaccination certificates, vet records, etc.)
  - retrieve pet data for summaries / Q&A

---

## What this service does NOT do (initially)

- Does not embed into the main app UI.
- Does not attempt to be the system of record (the main app remains the source of truth).
- Avoids running expensive AI pipelines server-side in the first iteration (keep costs low).

---

## Tech stack (decision open)

We discussed multiple options; the final choice should optimize for:
- clean **OpenAPI / schema** support (ChatGPT Actions)
- robust **auth** and security
- fast iteration for prototyping
- easy containerization/deployment

### Option A: TypeScript + Fastify
**Pros**
- Fast iteration, great DX for “API adapter” services
- Strong OpenAPI tooling and plugin ecosystem
- Good middleware support (rate limiting, validation)

**Cons**
- Requires runtime validation discipline (TS types aren’t enough)
- Dependency sprawl risk if not kept lean

### Option B: TypeScript + NestJS
**Pros**
- Scales well structurally (DI, modules, guards)
- Strong Swagger/OpenAPI integration
- Good for longer-term growth

**Cons**
- More ceremony; slower early prototyping

### Option C: Python + FastAPI
**Pros**
- Excellent OpenAPI-first experience
- Built-in request/response validation (Pydantic)
- Easy to extend with background jobs later

**Cons**
- Async/sync mixing pitfalls if not careful

### Option D: Go (Gin/Fiber) + OpenAPI-first workflow
**Pros**
- Simple deployment and small containers
- Great performance and production robustness
- Good for spec-first development (codegen)

**Cons**
- More boilerplate than FastAPI/Fastify

### Option E: .NET Minimal APIs / ASP.NET Core
**Pros**
- Very mature security + middleware ecosystem
- Great performance and maintainability
- Strong OpenAPI support

**Cons**
- Larger learning curve if not already using .NET

> Decision pending: choose based on preferred workflow (spec-first vs code-first), learning goals, and speed-to-prototype.

---

## High-level architecture

### Components
1. **ChatGPT (Custom GPT + Actions)**
   - The user chats with the GPT.
   - The GPT uses Actions to call `meo-gpt-connector` endpoints.
   - The GPT can ask clarifying questions when data is missing or ambiguous.

2. **meo-gpt-connector (this service)**
   - Presents an Actions-compatible API + OpenAPI schema.
   - Manages auth/connect flow (redirect to login, token exchange, token storage).
   - Validates inputs and calls the main app API.
   - Returns structured responses suitable for the GPT.

3. **Meo Mai Moi main app (Laravel + Fortify)**
   - Source of truth for pets, owners, documents, etc.
   - Provides internal/external API endpoints.
   - Stores uploaded files locally (initially).
   - May run background jobs later (e.g., extraction/verification).

### Interaction flow (conceptual)

#### A) Account connection (auth)
1. User tells the GPT they want to manage pets.
2. GPT initiates a **connect** tool call.
3. Connector presents a **login/consent** page (hosted by main app or connector).
4. User authenticates via existing Fortify setup.
5. Connector receives an authorization result and obtains an API token/session mapping.
6. Future Actions calls include the user’s connector token (or an opaque session id) so the connector can call the main app on their behalf.

> Note: Fortify is not an OAuth server by default. We’ll need a defined token strategy (e.g., Passport, Sanctum, or a custom “auth code → API token” bridge) when we finalize the API plan.

#### B) Create pet
1. User: “Create a pet: Mimi, female, cat, born 2023-03-01”
2. GPT calls connector `POST /pets`
3. Connector validates and forwards to main app API
4. Main app creates pet and returns the new pet record
5. Connector returns a concise success payload for the GPT

#### C) Upload vaccination certificate
1. User uploads an image/PDF in chat
2. GPT calls connector `POST /documents` (or `POST /uploads` then `POST /pets/{id}/documents`)
3. Connector stores file locally (initially) or delegates upload to main app
4. (Later) background job extracts fields; GPT can ask user to confirm

#### D) Ask questions about owned pets
1. User: “When is Mimi’s next vaccine due?”
2. GPT calls connector endpoints to fetch pet + vaccination data
3. GPT answers using retrieved structured data (and can clarify if data is missing)

---

## API surface (placeholder)

The exact endpoints will live in `tmp/api_plan.md` in the main repo and will be updated for bot-first needs, especially auth.

Expected minimal endpoints:
- `GET /health`
- `GET /.well-known/openapi.json` (or similar for Actions)
- `POST /auth/connect/start`
- `GET /auth/connect/callback`
- `POST /pets`
- `GET /pets`
- `GET /pets/{id}`
- `POST /pets/{id}/documents` (or a two-step upload flow)

---

## First iteration user stories (MVP)

### 1) Connect account
- **As a user**, I can connect my ChatGPT session to my Meo Mai Moi account so the bot can act on my behalf.
- **Acceptance criteria**
  - I can login via a secure web flow
  - The bot can confirm the account is linked
  - I can disconnect/revoke access

### 2) Create a pet via chat (primary)
- **As a user**, I can create a pet by describing it in natural language.
- **Acceptance criteria**
  - If required fields are missing, the bot asks follow-up questions
  - Pet is created in the main app and I receive a confirmation with key fields
  - I can list my pets to verify the result

Example prompts:
- “Create a pet named Mimi, a female cat, born March 1st 2023.”
- “Add my dog: Kiki, male, golden retriever, 2 years old.”

### 3) Upload a vaccination certificate
- **As a user**, I can upload a vaccination certificate in chat and attach it to a pet.
- **Acceptance criteria**
  - I can select which pet it belongs to (or the bot infers and confirms)
  - The file is stored and linked to the pet record
  - The bot confirms upload success and shows the document entry

Example prompts:
- “Upload this vaccination certificate for Mimi.”
- “Attach this PDF to Kiki’s documents.”

### 4) Ask questions about owned pets (retrieval-based)
- **As a user**, I can ask questions about my pets and get answers based on stored data.
- **Acceptance criteria**
  - Answers are grounded in data returned from the main app API
  - If data is missing, the bot says what’s missing and suggests next steps
  - The bot can link me to the relevant pet/document record

Example prompts:
- “List all my pets and their ages.”
- “Show Mimi’s vaccinations.”
- “When did Kiki last visit the vet?” (if data exists)

### 5) Basic corrections
- **As a user**, I can correct mistakes made during pet creation (e.g., wrong birthday).
- **Acceptance criteria**
  - The bot can update a pet’s fields after confirmation
  - Changes are persisted in the main app

---

## Non-functional goals (MVP)

- **Security first**
  - No leaking tokens in logs
  - Rate limiting for public endpoints
  - Minimal stored PII in the connector (prefer opaque references)

- **Reliability**
  - Deterministic, validated request/response schemas (tool-friendly)
  - Clear errors suitable for conversational recovery

- **Operational simplicity**
  - Runs as a single container
  - Simple env-based configuration
  - Structured logging

---

## Next steps

1. Review and update `tmp/api_plan.md` with:
   - auth/connect flow details (Fortify + token strategy)
   - bot-first endpoint shapes (tool-friendly schemas)
2. Choose bot service stack (FastAPI vs Fastify vs others)
3. Scaffold the service + OpenAPI schema suitable for ChatGPT Actions
4. Implement MVP endpoints: auth connect, create pet, list pets