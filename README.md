# meo-gpt-connector

This connector is retired and no longer deployed.

It connected a ChatGPT Custom GPT to [Meo Mai Moi](https://meo-mai-moi.com)
through ChatGPT Actions. During its public run, the GPT marketplace produced
zero organic registrations. Maintaining a separate protocol bridge for that
result did not make sense.

Agents should now use [meo-mcp](https://github.com/troioi-vn/meo-mcp), the
universal agent gateway for Meo Mai Moi. OAuth-capable clients can connect to:

```text
https://mcp.meo-mai-moi.com/mcp
```

The source remains here as a historical reference. It includes the old OAuth
bridge, semantic tool shapes, and ChatGPT-specific adapter code, but it should
not be used for a new deployment.
