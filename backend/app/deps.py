"""Acesso à conexão e à configuração guardadas no app."""
from __future__ import annotations

import sqlite3

from fastapi import Request

from .config import Config


def con(request: Request) -> sqlite3.Connection:
    return request.app.state.con


def cfg(request: Request) -> Config:
    return request.app.state.cfg
