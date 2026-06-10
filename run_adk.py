"""Lanzador de ADK para Windows sin privilegios de symlink.

ADK intenta crear un symlink de log en Windows, lo que requiere
SeCreateSymbolicLinkPrivilege. Este script parchea os.symlink para
ignorar ese error antes de invocar el CLI de ADK.

Uso:
    python run_adk.py run verificar_fake_news
    python run_adk.py web verificar_fake_news
"""
import os
import sys

_original_symlink = os.symlink


def _symlink_safe(*args, **kwargs):
    try:
        _original_symlink(*args, **kwargs)
    except OSError:
        pass  # ignorar WinError 1314 sin privilegios de symlink


os.symlink = _symlink_safe

from google.adk.cli.cli_tools_click import main  # noqa: E402

sys.exit(main())
