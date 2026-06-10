# VHS tape — swap-by-config demo for the README.
# Render headlessly from the repo root (python/agentforge-py):
#   vhs examples/swap-by-config/demo.tape
# Produces demo.gif (deterministic, offline, no API key / network).
# Assumes the uv workspace venv exists at ./.venv (run `uv sync` first).

Output examples/swap-by-config/demo.gif

Set Shell "bash"
Set FontSize 19
Set Width 1180
Set Height 720
Set Padding 22
Set Theme "Catppuccin Mocha"
Set TypingSpeed 38ms

# --- setup (hidden): enter the example dir, use the workspace venv ---
Hide
Type "source .venv/bin/activate && cd examples/swap-by-config"
Enter
Type "clear"
Enter
Show

# --- scene 1: an agent that runs locally, no key, no network ---
Type "# Run a real AgentForge agent locally — no API key, no network:"
Enter
Sleep 900ms
Type "python smoke.py"
Enter
Sleep 2.6s

# --- scene 2: swap the backend by editing one line of YAML ---
Type "# Switch the LLM backend by editing ONE line of YAML:"
Enter
Sleep 900ms
Type "grep -n 'model:' *.yaml"
Enter
Sleep 2.8s

# --- scene 3: the agent code never names a vendor ---
Type "# ...and agent.py never changes — it never names a provider:"
Enter
Sleep 900ms
Type "grep -n 'Agent(' agent.py"
Enter
Sleep 2.6s

# --- closing beat ---
Type "# Every backend is its own package, swapped by config,"
Enter
Type "# behind a version-locked contract. That's the whole idea."
Enter
Sleep 3s
