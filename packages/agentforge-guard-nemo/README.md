# agentforge-guard-nemo

NVIDIA [NeMo Guardrails](https://docs.nvidia.com/nemo/guardrails/)
programmable rails for AgentForge guardrails (feat-018).

Adds the `nemo` validator to both input and output sections of
`modules.guardrails`:

```yaml
modules:
  guardrails:
    input:
      - nemo:
          config_path: ./rails/  # directory containing Colang + config.yml
    output:
      - nemo:
          config_path: ./rails/
```

```bash
agentforge add module guard-nemo
```

NeMo Guardrails is a programmable-rail framework (Colang DSL).
The adapter consumes a directory carrying `config.yml` + `*.co`
files and loads it once per Agent. Tests inject a fake rail
runner so `nemoguardrails` doesn't need to be installed at test
time.
