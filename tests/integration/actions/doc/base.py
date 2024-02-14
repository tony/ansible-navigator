"""Base class for doc interactive/stdout tests."""

from __future__ import annotations

import difflib
import os

from collections.abc import Generator

import pytest

from tests.defaults import FIXTURES_COLLECTION_DIR
from tests.integration._common import retrieve_fixture_for_step
from tests.integration._common import update_fixtures
from tests.integration._tmux_session import TmuxSession


class BaseClass:
    """Base class for interactive/stdout doc tests."""

    UPDATE_FIXTURES = False
    TEST_FOR_MODE: str | None = None

    @staticmethod
    @pytest.fixture(scope="module", name="tmux_doc_session")
    def fixture_tmux_doc_session(
        request: pytest.FixtureRequest,
    ) -> Generator[TmuxSession, None, None]:
        """Tmux fixture for this module.

        :param request: A fixture providing details about the test caller
        :yields: Tmux session
        """
        with TmuxSession(
            pane_height=2000,
            pane_width=200,
            setup_commands=[
                f"export ANSIBLE_COLLECTIONS_PATH={FIXTURES_COLLECTION_DIR}",
                "export ANSIBLE_DEVEL_WARNING=False",
                "export ANSIBLE_DEPRECATION_WARNINGS=False",
            ],
            request=request,
        ) as tmux_session:
            yield tmux_session

    def test(
        self,
        request: pytest.FixtureRequest,
        tmux_doc_session: TmuxSession,
        index: int,
        user_input: str,
        comment: str,
        testname: str,
        expected_in_output: list[str] | None,
        skip_if_already_failed: bool | None = None,
    ) -> None:
        # pylint: disable=too-many-arguments
        # pylint: disable=too-many-locals
        """Run the tests for ``doc``, mode and ``ee`` set in child class.

        :param request: A fixture providing details about the test caller
        :param tmux_doc_session: The tmux session to use
        :param index: Step index
        :param user_input: Value to send to the tmux session
        :param comment: Comment to add to the fixture
        :param testname: Name of test
        :param expected_in_output: A list of strings or string to find
        :raises ValueError: When the test mode is not set
        """
        if self.TEST_FOR_MODE == "interactive":
            search_within_response = ":help help"
        elif self.TEST_FOR_MODE == "stdout":
            search_within_response = tmux_doc_session.cli_prompt
            # clear the screen so it starts with stdout
            user_input = f"clear && {user_input}"
        else:
            msg = (
                "Value of 'TEST_FOR_MODE' is not set.",
                " Valid value is either 'interactive' or 'stdout'",
            )
            raise ValueError(msg)

        received_output = tmux_doc_session.interaction(user_input, search_within_response)
        updated_received_output = []
        mask = "X" * 50
        for line in received_output:
            if tmux_doc_session.cli_prompt in line or ("filename" in line or "│warnings:" in line):
                updated_received_output.append(mask)
            else:
                for value in ["time=", "skipping entry", "failed:", "permission denied"]:
                    if value in line:
                        break
                else:
                    updated_received_output.append(line)

        if expected_in_output:
            for out in expected_in_output:
                assert any(out in line for line in received_output), (out, received_output)
        else:
            fixtures_update_requested = (
                self.UPDATE_FIXTURES
                or os.environ.get("ANSIBLE_NAVIGATOR_UPDATE_TEST_FIXTURES") == "true"
            )
            if fixtures_update_requested:
                update_fixtures(request, index, updated_received_output, comment, testname=testname)

            expected_output = retrieve_fixture_for_step(request, index, testname)
            assert expected_output == updated_received_output, "\n" + "\n".join(
                difflib.unified_diff(
                    expected_output,
                    updated_received_output,
                    "expected",
                    "received",
                ),
            )
