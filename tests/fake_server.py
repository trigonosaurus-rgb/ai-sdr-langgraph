"""The real API on a scripted, slowed-down graph for browser tests. No network, no keys, no cost.

uvicorn tests.fake_server:app --port 8765

The company name picks the scenario: "slow" stretches research to a few seconds (time to reload
or cancel), "broken" fails research; anything else runs to a ready draft.
"""

import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))  # for `fakes`

from core.config import Settings  # noqa: E402
from core.context import RunContext  # noqa: E402
from core.llm import LLMError  # noqa: E402
from core.schemas import Brief, Draft  # noqa: E402
from fakes import ABOUT, NEWS, FakeLLM, FakeSearch, happy_script, source  # noqa: E402
from server.app import create_app  # noqa: E402
from server.runs import RunManager  # noqa: E402
from server.store import Store  # noqa: E402

DRAFT = Draft(
    subject="Staffing the Warsaw analytics team",
    body=(
        "Acme is hiring 30 engineers for its new analytics team in Warsaw.\n\n"
        "We place contract data engineers who can start within two weeks, "
        "so the team can ship while permanent hiring continues.\n\n"
        "Worth a short call next week?"
    ),
)


class PacedLLM(FakeLLM):
    """FakeLLM with realistic pauses: a delay per call and per streamed chunk."""

    def __init__(self, script, *, call_delay: float, research_delay: float):
        super().__init__(script, chunk_chars=6)
        self.call_delay, self.research_delay = call_delay, research_delay

    def generate(self, stage, schema, system, user, on_partial=None):
        time.sleep(self.research_delay if stage == "Research" else self.call_delay)
        paced = None
        if on_partial is not None:

            def paced(partial):
                time.sleep(0.02)
                on_partial(partial)

        return super().generate(stage, schema, system, user, paced)


def make_context(brief: Brief, cancel: threading.Event) -> RunContext:
    name = brief.company.lower()
    script = happy_script(Writing=[DRAFT])
    if "broken" in name:
        script["Research"] = [LLMError("simulated provider outage")]
    llm = PacedLLM(script, call_delay=0.3, research_delay=4.0 if "slow" in name else 0.5)
    search = FakeSearch(
        official=[source("https://acme.com/about", "About Acme", ABOUT)],
        news=[source("https://news.example.com/acme-warsaw", "Acme expands to Warsaw", NEWS)],
    )
    return RunContext(settings=Settings(), llm=llm, search_client=search, cancel=cancel)


def make_manager() -> RunManager:
    store = Store(Path(tempfile.mkdtemp(prefix="sdr-e2e-")) / "sdr.sqlite3")
    return RunManager(store, make_context, max_workers=1, runs_per_hour=1000)


app = create_app(make_manager)
