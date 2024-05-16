"""`partners.json` keeps a record of all collection partners"""

from __future__ import annotations

from typing import ClassVar, Dict, List, Sequence

from .common import Node


class Partner(Node, frozen=True):
    id: str


class Partners(Node, frozen=True):
    """`partners.json` keeps a record of all collection partners"""

    file_name: ClassVar[str] = "partners.json"

    active: Sequence[Partner] = ()

    def get_updated(self, update: Partners) -> Partners:
        assert set(self.model_fields) == {"active"}, set(self.model_fields)

        known_partners = {p.id for p in self.active}
        new_partners: List[Partner] = []
        partner_updates: Dict[str, Partner] = {}
        for p in update.active:
            if p.id in known_partners:
                partner_updates[p.id] = p
            else:
                new_partners.append(p)

        return Partners(
            active=[
                partner_updates[p.id] if p.id in partner_updates else p
                for p in self.active
            ]
            + new_partners
        )
