# jev-melee

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
