"""Versioned prompt files from prompts/*.md.

A file starts with front matter holding `version`, followed by sections that begin
with `# <name>` lines. Sections are string.Template texts with $placeholders.
"""

import re
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from string import Template

PROMPTS_DIR = Path(__file__).resolve().parent.parent / "prompts"
_FRONT_MATTER = re.compile(r"\A---\n(.*?)\n---\n", re.S)
_SECTION = re.compile(r"^# (\w+)\n", re.M)


@dataclass(frozen=True)
class Prompt:
    name: str
    version: str
    sections: dict[str, str]

    @property
    def tag(self) -> str:
        """Identifier stored with results, e.g. 'research@1'."""
        return f"{self.name}@{self.version}"

    def render(self, section: str, **values: object) -> str:
        return Template(self.sections[section]).substitute(values).strip()


def parse_prompt(name: str, text: str) -> Prompt:
    text = text.replace("\r\n", "\n")
    match = _FRONT_MATTER.match(text)
    if not match:
        raise ValueError(f"prompt {name!r} has no front matter")
    meta = dict(
        line.split(":", 1) for line in match.group(1).splitlines() if line.strip()
    )
    version = meta.get("version", "").strip()
    if not version:
        raise ValueError(f"prompt {name!r} has no version")
    parts = _SECTION.split(text[match.end() :])
    sections = {parts[i]: parts[i + 1] for i in range(1, len(parts), 2)}
    for required in ("system", "user"):
        if required not in sections:
            raise ValueError(f"prompt {name!r} has no '# {required}' section")
    return Prompt(name, version, sections)


@cache
def load_prompt(name: str) -> Prompt:
    return parse_prompt(name, (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8"))
