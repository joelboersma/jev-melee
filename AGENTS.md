# Working on jev-melee

This project aims to let Jev, TypeSafe AI's System One model, control a Melee
character through libmelee and Slippi Dolphin. The current implementation runs
repeated local matches against a CPU; the gameplay policy is idle.

See [README.md](README.md) for Python setup, emulator requirements, local path
configuration, and usage. Keep that file focused on users and human contributors.

## Code organization

- `jev_melee/__main__.py` handles CLI arguments, saved paths, and user-facing errors.
- `jev_melee/loop.py` owns the match lifecycle and emulator resource cleanup.
- `MatchLoop` accepts a `policy(gamestate, controller)` callback, invoked once per
  received gameplay frame, including sudden death. Add gameplay decisions through
  this callback and keep menu navigation in the outer loop.
- When implementing TypeSafe integration, follow
  [.agents/skills/typesafe-ai/SKILL.md](.agents/skills/typesafe-ai/SKILL.md), including
  reading the live docs relevant to the integration.

## Behavior to preserve

- Wait for the CPU's character, controller status, and level to be ready before
  starting a match.
- Treat sudden death as part of the same match. Count completion once, even when
  results screens persist across several frames.
- Re-select the stage for each new match without depending on observing menu frame
  zero, and preserve the stadium toggle state across matches.
- Clear menu inputs before handing control to the gameplay policy.
- Preserve timeouts and cleanup on normal completion, failures, and Ctrl+C.
  Disconnect controllers, stop the owned Dolphin process, and remove its temporary
  user directory. Keep normal Dolphin settings isolated from the runner.
- Keep personal paths in the ignored `jev-melee.local.json`. Use placeholders in
  the tracked example config. Preserve individual CLI overrides and resolve saved
  relative paths from the config file's directory.

## Verification

After relevant code changes, run:

```sh
python -m unittest discover -s tests -v
```

Add or update tests for changed lifecycle or configuration behavior. Automated
tests use simulated game states and do not establish live emulator compatibility.

For live verification, follow the README smoke test with `--matches 2`: confirm
two start/finish log pairs, stage re-selection, and a clean exit. This requires
Slippi Dolphin and a Melee image. State which checks actually ran; report live
verification as unperformed when those prerequisites are unavailable.
