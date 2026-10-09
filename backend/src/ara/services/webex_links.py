"""Validate supported Webex space links without treating them as network URLs."""

import re
import uuid
from urllib.parse import parse_qs, urlsplit

from ara.core.errors import DomainError


def parse_space_link(value: str) -> tuple[uuid.UUID, str]:
    try:
        link = urlsplit(value)
        query = parse_qs(link.query, keep_blank_values=True, strict_parsing=True)
        spaces = query.get("space", [])
        if (
            link.scheme != "webexteams"
            or link.netloc != "im"
            or link.path
            or link.fragment
            or set(query) != {"space"}
            or len(spaces) != 1
            or not re.fullmatch(
                r"[0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}", spaces[0]
            )
            or any(character.isspace() for character in value)
        ):
            raise ValueError
        identifier = uuid.UUID(spaces[0])
    except ValueError:
        raise DomainError(
            "invalid_space_link",
            "Enter a Webex space link in the form webexteams://im?space=<space UUID>.",
            status_code=422,
        ) from None
    return identifier, f"webexteams://im?space={identifier}"
