from __future__ import annotations

import asyncio
from typing import TYPE_CHECKING

from slice_panel.domain.follow_ended import FollowEnded
from slice_panel.domain.follow_source import FollowSource
from slice_panel.infrastructure.follow_line_payload import FollowLinePayload, FollowLineRejectedError

if TYPE_CHECKING:
    from collections.abc import AsyncIterator, Sequence

    from slice_panel.domain.follow_line import FollowLine


class SubprocessFollowSource(FollowSource):
    def __init__(self, *, argv: Sequence[str]) -> None:
        self._argv = tuple(argv)

    async def events(self) -> AsyncIterator[FollowLine | FollowEnded]:
        try:
            process = await asyncio.create_subprocess_exec(
                *self._argv, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
        except OSError as error:
            yield FollowEnded(exit_code=None, detail=f"{self._argv[0]} could not be started: {error}")
            return
        assert process.stdout is not None
        assert process.stderr is not None
        stderr = asyncio.create_task(process.stderr.read())
        try:
            async for raw in process.stdout:
                text = raw.decode("utf-8").strip()
                if not text:
                    continue
                try:
                    line = FollowLinePayload.parsed(text).to_domain()
                except FollowLineRejectedError as error:
                    yield FollowEnded(exit_code=None, detail=str(error))
                    return
                yield line
            exit_code = await process.wait()
            yield FollowEnded(exit_code=exit_code, detail=(await stderr).decode("utf-8").strip())
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()
            stderr.cancel()
