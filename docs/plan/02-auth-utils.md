# 02 - Auth Utilities

**Goal:** Establish Redis client, JWT issuing/validation functions, and AES Sanctum encryption for connector OAuth2 logic.

## Definition of Done

- `core/redis.py` connects correctly to Redis.
- `core/jwt.py` validates/issues JWTs containing encrypted Sanctum Tokens.
- `core/crypto.py` handles AES-256-GCM.
- 100% test coverage for these internal security logic files.

## Implementation Steps

1. **Redis Client (`src/core/redis.py`):**
   - Initialize an async Redis client (`redis.asyncio`).
   - Implement helper functions equivalent to: `set_with_ttl(key, value, ttl)`, `get_and_delete(key)` (must be atomic to prevent code replays!).

2. **Crypto Layer (`src/core/crypto.py`):**
   - Use `cryptography.hazmat` to setup AES-256-GCM encryption.
   - Requires `ENCRYPTION_KEY` from settings.
   - Implement `encrypt(sanctum_token: str) -> str` and `decrypt(encrypted: str) -> str`.
   - Write tests: Ensure string round-trips successfully, tampered ciphertext throws error, and unique nonces cause unique ciphertext.

3. **JWT Layer (`src/core/jwt.py`):**
   - Use `python-jose[cryptography]`.
   - Implement `create_jwt(user_id: int, sanctum_token: str)` which signs with `HS256` and `JWT_SECRET`. Store the encrypted sanctum token in payload as `tok`, and set `exp` to 1 year.
   - Implement `validate_jwt(token: str) -> (user_id, sanctum_token)`. This should decode, verify the signature, and automatically decrypt the embedded `tok`.
   - Write tests: Happy path, expiry, invalid signature, and tamper tests.
