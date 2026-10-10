# jev-melee

Run repeated local Super Smash Bros. Melee matches through Slippi Dolphin and
libmelee. The goal is to let Jev, TypeSafe AI's System One model, control a character;
the current runner handles the match lifecycle while the character stays idle.
No TypeSafe credentials or model calls are needed yet.

## Python setup

Requires Python 3.10 or newer. [Libmelee](https://github.com/vladfi1/libmelee) is published on PyPI as `melee` and pinned in `requirements.txt`.

Ensure Python is available in your terminal, then run these commands from the project directory. If your system uses `python3` instead of `python`, use `python3` to create the virtual environment.

Create a virtual environment:

```sh
python -m venv .venv
```

Activate it using the command for your shell:

| Shell | Command |
| --- | --- |
| Bash / Zsh (macOS or Linux) | `source .venv/bin/activate` |
| PowerShell (Windows) | `.\.venv\Scripts\Activate.ps1` |
| Command Prompt (Windows) | `.venv\Scripts\activate.bat` |

Once activated, `python` uses the project's environment. Install dependencies and verify that libmelee imports successfully:

```sh
python -m pip install -r requirements.txt
python -c "import melee; from importlib.metadata import version; print(version('melee'))"
```

Activate the environment again whenever you open a new terminal. Run `deactivate` when you're finished.

Running games also requires Slippi Dolphin and a Melee game image; see the [libmelee setup instructions](https://github.com/vladfi1/libmelee#setup-instructions).

## Run the match loop

Use a libmelee-compatible **Slippi Dolphin** build and your own **NTSC 1.02 Melee**
game image. Ordinary Dolphin does not provide the Slippi game-state stream.
Pass the Dolphin executable or its installation folder and the image explicitly:

```powershell
python -m jev_melee --dolphin "C:\path\to\Slippi Dolphin\Dolphin.exe" --iso "C:\path\to\Melee.iso"
```

To save these paths, copy the example config once:

```powershell
Copy-Item jev-melee.example.json jev-melee.local.json
```

Edit `jev-melee.local.json` with your Dolphin folder or executable and ISO path.
Use forward slashes in JSON paths, as in the example (backslashes must be doubled).
The local file is ignored by Git. Then run from the project directory:

```powershell
python -m jev_melee
```

The runner reads `jev-melee.local.json` from the current directory automatically.
Use `--config "C:/path/to/config.json"` to select another file. Relative paths in
the config are resolved from the config's directory; command-line paths are
resolved from the current directory. `--dolphin` and `--iso` override saved paths
individually, so you can temporarily change one without editing the config.

The runner boots Dolphin in a window, navigates to local VS mode, selects Fox on
port 1 and a level-9 Marth CPU on port 2, and selects Final Destination. The controlled
character currently stays idle; the CPU plays normally so matches can finish.
After a match, both controllers dismiss the results and the runner selects the
characters and stage again. It repeats until **Ctrl+C**. Match starts and finishes
are logged, and sudden death belongs to the same match.

For a bounded smoke test or different matchup:

```powershell
python -m jev_melee --dolphin "C:\path\to\Dolphin.exe" --iso "C:\path\to\Melee.iso" --matches 2 --character FALCO --opponent FOX --cpu-level 7 --stage BATTLEFIELD
```

`--bot-port` and `--cpu-port` accept distinct ports from 1 through 4. Run
`python -m jev_melee --help` for all options. `--verbose` logs menu transitions.
The runner stops with an error if game states stop arriving for 30 seconds or it
cannot start a match within 120 seconds of menu navigation; adjust these with
`--state-timeout` and `--menu-timeout` for slower machines.

Libmelee configures the controller pipes and menu extraction codes in a fresh,
temporary Dolphin user directory. Normal Dolphin settings are not changed. Match
rules use the game's defaults, with infinite time disabled. Replays are disabled
for this initial runner. Shutdown disconnects controllers, stops its Dolphin
process, and removes the temporary user directory, including on failures and Ctrl+C.
Run one instance at a time: Windows controller pipe names and the Slippi port are fixed.

## Verification

Run the automated tests after installing requirements:

```sh
python -m unittest discover -s tests -v
```

Tests exercise configuration loading, repeated matches, CPU readiness, stage
re-selection, sudden death, match limits, timeouts, and resource cleanup using
simulated game states.

For a live smoke test, run with your saved paths:

```sh
python -m jev_melee --matches 2
```

Confirm two start/finish log pairs, stage re-selection between matches, and a clean
exit. Live verification requires the emulator and game image.

See [AGENTS.md](AGENTS.md) for code organization and instructions for agents
working on the project.
