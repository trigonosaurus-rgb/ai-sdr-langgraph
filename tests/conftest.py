"""Shared fixtures; fakes live in fakes.py."""

import pytest

from core.config import Settings
from core.context import RunContext
from core.schemas import Brief
from fakes import ABOUT, NEWS, FakeClock, FakeLLM, FakeSearch, source


@pytest.fixture
def brief() -> Brief:
    return Brief(
        company="Acme",
        website="https://www.acme.com/",
        offer="Data engineering contractors for analytics teams",
        recipient="VP of Engineering",
        language="English",
        tone="Direct",
    )


@pytest.fixture
def search() -> FakeSearch:
    return FakeSearch(
        official=[source("https://acme.com/about", "About Acme", ABOUT)],
        web=[source("https://acme.com/about/", "About Acme (dup)", ABOUT)],
        news=[source("https://news.example.com/acme-warsaw", "Acme expands to Warsaw", NEWS)],
    )


@pytest.fixture
def make_ctx(search):
    def make(llm: FakeLLM, *, max_rewrites: int = 2, search_client=None) -> RunContext:
        return RunContext(
            settings=Settings(max_rewrites=max_rewrites),
            llm=llm,
            search_client=search_client or search,
            clock=FakeClock(),
        )

    return make

