"""Immutable, authenticated text intake."""

import hashlib
import uuid

from .identity import Identity, authorize
from .models import SourceRevision


class IntakeService:
    def __init__(self, store):
        self.store = store

    def submit(self, identity: Identity, text: str, simulated: bool) -> SourceRevision:
        authorize(identity, identity.scope_id, "write")
        revision = SourceRevision(
            id="source-" + uuid.uuid4().hex, scope_id=identity.scope_id, text=text,
            sha256=hashlib.sha256(text.encode("utf-8")).hexdigest(),
            simulated=simulated, submitted_by=identity.account_id,
        )
        self.store.append_source(identity.scope_id, revision)
        return revision
