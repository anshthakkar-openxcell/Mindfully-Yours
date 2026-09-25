"""
Avatar rendering adapter.

UNRESOLVED VENDOR -- see documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #8: the source
material gives three different answers (Spatius.ai in the earliest draft, HeyGen in the two later
architecture PDFs, and a 2-D character via Rive/Live2D as APPROACH.md's own stated preference to
avoid per-render fees). This file implements the HeyGen shape as the currently-latest-documented
option -- do NOT treat this as a final vendor decision. If Rive/Live2D is chosen instead, this
should become a local rendering call, not an HTTP adapter at all.

Avatar is opt-in and cost-gated by design -- never call this unconditionally. See
app.providers.factory for how AVATAR_ENABLED gates whether this adapter is even constructed.

TODO: wire up the real HeyGen (or whichever vendor is finally chosen) streaming avatar API.
"""

from collections.abc import AsyncIterator

from app.providers.base import AvatarProvider


class HeyGenAvatarProvider(AvatarProvider):
    def __init__(self, api_key: str):
        self._api_key = api_key

    async def render_stream(self, audio_chunks: AsyncIterator[bytes]) -> AsyncIterator[bytes]:
        raise NotImplementedError(
            "Avatar vendor is not yet finalized -- see "
            "documnets/understanding/15_OPEN_QUESTIONS_AND_BLOCKERS.md #8."
        )
        yield  # pragma: no cover
