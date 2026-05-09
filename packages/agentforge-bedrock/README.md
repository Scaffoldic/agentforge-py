# agentforge-bedrock

AWS Bedrock provider for [AgentForge](https://github.com/Scaffoldic/agentforge-py).

Implements the `LLMClient` and `EmbeddingClient` contracts from
`agentforge-core` over the AWS Bedrock Converse and embeddings APIs.

## Install

```bash
uv add agentforge-bedrock
```

## Quickstart

```python
from agentforge import Agent

# Cross-region inference profile — recommended for production.
async with Agent(model="bedrock:us.anthropic.claude-haiku-4-5-20251001-v1:0") as agent:
    result = await agent.run("Summarise the AgentForge project in one sentence.")
    print(result.output)
```

Credentials follow the standard boto3 chain (env vars, `~/.aws/credentials`,
IAM role). Pass `aws_profile=` to override.

## Model identifiers

Three forms are supported, all passed through to Bedrock unchanged:

| Form | Example |
| --- | --- |
| Region-pinned | `bedrock:anthropic.claude-3-5-sonnet-20240620-v1:0` |
| Cross-region (geo) | `bedrock:us.anthropic.claude-haiku-4-5-20251001-v1:0` |
| Cross-region (global) | `bedrock:global.anthropic.claude-sonnet-4-5-20250929-v1:0` |

Cross-region profiles route requests across destination regions
automatically, smoothing throttling and improving availability.
See [Bedrock cross-region inference](https://docs.aws.amazon.com/bedrock/latest/userguide/cross-region-inference.html).
