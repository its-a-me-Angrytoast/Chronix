"""Prompt sanitizer and simple safety checks for AI prompts.

This module provides lightweight, conservative sanitization suitable for
default use. It's not a replacement for a security review, but helps catch
obvious dangerous inputs (shell commands, excessive length, mention spam).
"""
from __future__ import annotations

from typing import Tuple, List
import re

MAX_PROMPT_LEN = 2000

# Simple blacklist of dangerous substrings
_DANGEROUS_SUBSTRINGS = ["rm -rf", "sudo", "shutdown", "reboot", "eval(", "exec(", "import os", "open('/etc/passwd'", "DELETE FROM"]


def sanitize_prompt(prompt: str) -> Tuple[str, List[str]]:
    """Return (sanitized_prompt, list_of_removed_tokens).

    - Strips mentions like <@123456> and @everyone/@here
    - Removes backticks and common code fence markers
    - Rejects or removes obviously dangerous substrings
    - Truncates to MAX_PROMPT_LEN
    """
    removed: List[str] = []
    if not isinstance(prompt, str):
        return ("", ["non-str-prompt"])
    p = prompt
    # remove mentions
    p_new = re.sub(r"<@!?(\d+)>", "", p)
    if p_new != p:
        removed.append("mentions")
        p = p_new
    # remove everyone/here
    if "@everyone" in p or "@here" in p:
        p = p.replace("@everyone", "").replace("@here", "")
        removed.append("mass-mentions")
    # remove backticks and code fences
    if "`" in p:
        p = p.replace("`", "")
        removed.append("backticks")
    p = p.replace("```", "")
    # check dangerous substrings
    lowered = p.lower()
    for s in _DANGEROUS_SUBSTRINGS:
        if s.lower() in lowered:
            # remove the substring
            p = re.sub(re.escape(s), "", p, flags=re.IGNORECASE)
            removed.append(f"danger:{s}")
    # enforce max length
    if len(p) > MAX_PROMPT_LEN:
        p = p[:MAX_PROMPT_LEN]
        removed.append("truncated")
    # whitespace normalization
    p = re.sub(r"\s+", " ", p).strip()
    return (p, removed)
