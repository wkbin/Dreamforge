#!/usr/bin/env python3
# -*- coding: utf-8 -*-

from __future__ import annotations


class ZaomengError(Exception):
    """Base exception for project-specific failures."""


class ConfigLoadError(ZaomengError):
    """Raised when config content cannot be loaded safely."""


class BudgetExceededError(ZaomengError):
    """Raised when a request would exceed the configured budget."""


class MissingAPIKeyError(ZaomengError):
    """Raised when an online provider is enabled without credentials."""


class LLMRequestError(ZaomengError):
    """Raised when an upstream LLM request fails."""


class TextDecodingError(ZaomengError):
    """Raised when a novel text file cannot be decoded."""


class OptionalDependencyError(ZaomengError):
    """Raised when an optional dependency is required but unavailable."""
