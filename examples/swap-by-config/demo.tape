# VHS tape — README hero reel for AgentForge.
# Render headlessly from the repo root (python/agentforge-py):
#   vhs examples/swap-by-config/demo.tape
# Produces demo.gif (deterministic, offline, no API key / network).
# Assumes the uv workspace venv exists at ./.venv (run `uv sync` first)
# and that examples/swap-by-config/demo-recording.sqlite was seeded
# (run `python examples/swap-by-config/seed_recording.py` first).
#
# Three beats: (1) from zero to a runnable project, (2) the full loop
# running offline with budget + tracing, (3) swap vendor or reasoning
# loop by config. The run_id below comes from seed_recording.py.

Output examples/swap-by-config/demo.gif

Set Shell "bash"
Set FontSize 19
Set Width 1180
Set Height 720
Set Padding 20
Set Theme "Catppuccin Mocha"
Set TypingSpeed 32ms
Set Framerate 24

# --- setup (hidden) ---
Hide
Type "source .venv/bin/activate && cd examples/swap-by-config && rm -rf my-agent"
Enter
Type "clear"
Enter
Show

# --- beat 1: from an empty folder to a complete agent project ---
Type "# 1. From zero to a complete, runnable agent project — one command:"
Enter
Sleep 800ms
Type "agentforge new my-agent --template minimal --no-prompts"
Enter
Sleep 2.2s

# --- beat 2: run the full loop offline, no API key (a recorded run) ---
Hide
Type "clear"
Enter
Show
Type "# 2. Run the full loop — budget + tracing wired in — offline, no key:"
Enter
Sleep 800ms
Type 'agentforge run --replay 01KV76FZTJ2SZ9EKV5R5Z10DAD --path agentforge.demo.yaml "Summarise the Agile Manifesto in three bullets."'
Enter
Sleep 2.8s

# --- beat 3: swap the vendor OR the reasoning loop, by config ---
Hide
Type "clear"
Enter
Show
Type "# 3. Swap the vendor — one line of YAML, agent.py never changes:"
Enter
Sleep 800ms
Type "grep -n 'model:' agentforge.anthropic.yaml agentforge.openai.yaml"
Enter
Sleep 2.1s
Type "# ...and the reasoning loop is the same one-line swap:"
Enter
Sleep 700ms
Type "grep -n 'strategy:' agentforge.demo.yaml"
Enter
Sleep 2.0s

# --- closing beat ---
Type "# Same agent.py. Swap the vendor, the memory, the reasoning loop — all by config."
Enter
Sleep 2.2s

# --- cleanup (hidden) ---
Hide
Type "rm -rf my-agent"
Enter
