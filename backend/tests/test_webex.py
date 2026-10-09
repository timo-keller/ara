import asyncio
import base64
import json
import uuid
from collections.abc import AsyncIterator, Iterator
from datetime import UTC, datetime, timedelta
from pathlib import Path

import httpx
import pytest
from asgi_client import ASGIClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from test_config import environment

from ara.api.routers import auth as auth_router
from ara.api.routers import groups as group_router
from ara.core.config import Settings, get_settings
from ara.core.errors import DomainError
from ara.domain.models import (
    ApplicationSession,
    Asset,
    AuditEvent,
    Group,
    GroupRole,
    Reservation,
    ReservationStatus,
    User,
    WebexDelivery,
)
from ara.infrastructure.database import Base, create_engine, create_session_factory
from ara.infrastructure.webex import WebexClient, space_uuid
from ara.main import create_app
from ara.services.authorization import EffectiveRoles
from ara.services.groups import GroupService
from ara.services.reservations import ReservationService
from ara.services.webex import WebexService
from ara.services.webex_links import parse_space_link

NOW = datetime(2030, 1, 2, 10, tzinfo=UTC)
SPACE = uuid.UUID("c149af1a-71e9-4955-a2b0-9ca8b423b129")
LINK = f"webexteams://im?space={SPACE}"
ROOM = (
    base64.b64encode(f"ciscospark://urn:TEAM:eu-central-1_k/ROOM/{SPACE}".encode())
    .decode()
    .rstrip("=")
)


@pytest.mark.parametrize(
    "link",
    [
        "https://example.test/?space=" + str(SPACE),
        "webexteams://chat?space=" + str(SPACE),
        "webexteams://im",
        "webexteams://im?space=",
        "webexteams://im?space=invalid",
        LINK + "&space=" + str(SPACE),
        LINK + "&space=",
        LINK + "&extra=yes",
        LINK + "#fragment",
        LINK.replace("im?", "im/path?"),
        "webexteams://im?space=" + SPACE.hex,
    ],
)
def test_space_links_reject_invalid_or_ambiguous_values(link: str) -> None:
    with pytest.raises(DomainError) as error:
        parse_space_link(link)
    assert error.value.code == "invalid_space_link"


def test_space_link_normalization() -> None:
    assert parse_space_link(f"WEBEXTEAMS://im?space={str(SPACE).upper()}") == (
        SPACE,
        LINK,
    )


@pytest.mark.parametrize("region", ["us", "urn:TEAM:eu-central-1_k"])
async def test_space_lookup_preserves_regional_id_and_paginates(region: str) -> None:
    room_id = base64.b64encode(f"ciscospark://{region}/ROOM/{SPACE}".encode()).decode()
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        assert request.headers["Authorization"] == "Bearer token"
        if len(calls) == 1:
            return httpx.Response(
                200,
                json={"items": []},
                headers={
                    "Link": (
                        "<https://webexapis.com/v1/rooms?max=100&cursor=next>; "
                        'rel="next"'
                    ),
                },
            )
        return httpx.Response(200, json={"items": [{"id": room_id, "type": "group"}]})

    client = WebexClient("token", httpx.MockTransport(handle))
    try:
        assert await client.resolve_space(SPACE) == room_id
        assert len(calls) == 2
    finally:
        await client.close()


@pytest.mark.parametrize(
    "value",
    [
        "not base64",
        f"ciscospark://us/PERSON/{SPACE}",
        f"https://example.test/ROOM/{SPACE}",
        "ciscospark://us/ROOM/not-a-uuid",
    ],
)
def test_room_id_parser_rejects_non_room_identifiers(value: str) -> None:
    encoded = base64.b64encode(value.encode()).decode()
    assert space_uuid(encoded) is None


@pytest.mark.parametrize(
    "destination",
    [
        "https://evil.test/v1/rooms",
        "http://webexapis.com/v1/rooms",
        "https://webexapis.com/v1/messages",
        "https://user@webexapis.com/v1/rooms",
        "https://webexapis.com:8443/v1/rooms",
    ],
)
async def test_lookup_never_follows_untrusted_pagination(destination: str) -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={"items": []},
            headers={
                "Link": f'<{destination}>; rel="next"',
            },
        )

    client = WebexClient("token", httpx.MockTransport(handle))
    try:
        with pytest.raises(DomainError):
            await client.resolve_space(SPACE)
        assert len(calls) == 1
    finally:
        await client.close()


async def test_lookup_pagination_is_bounded() -> None:
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(
            200,
            json={"items": []},
            headers={
                "Link": (
                    f'<https://webexapis.com/v1/rooms?cursor={len(calls)}>; rel="next"'
                ),
            },
        )

    client = WebexClient("token", httpx.MockTransport(handle))
    try:
        with pytest.raises(DomainError):
            await client.resolve_space(SPACE)
        assert len(calls) == 20
    finally:
        await client.close()


def settings(*, enabled: bool = True) -> Settings:
    values = environment()
    if enabled:
        values["ARA_WEBEX_BOT_TOKEN"] = "test-bot-secret"
    return Settings.from_environment(values)


@pytest.fixture
async def database(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[tuple[async_sessionmaker[AsyncSession], Asset, User, Group]]:
    monkeypatch.setattr("ara.services.webex.utc_now", lambda: NOW)
    monkeypatch.setattr("ara.services.reservations.utc_now", lambda: NOW)
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'webex.db'}")
    factory = create_session_factory(engine)
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    async with factory() as session:
        group = Group(name="Lab", webex_room_id="room-1")
        user = User(
            oidc_issuer="https://issuer.example",
            oidc_subject="user",
            email="user@example.test",
            display_name="Test User",
        )
        session.add_all((group, user))
        await session.flush()
        asset = Asset(name="Laptop", asset_type="computer", group_id=group.id)
        session.add(asset)
        await session.commit()
    yield factory, asset, user, group
    await engine.dispose()


@pytest.mark.parametrize(
    "start_delta", [timedelta(), timedelta(days=-1), timedelta(minutes=5)]
)
async def test_start_timing_and_destinations(
    database: tuple, monkeypatch: pytest.MonkeyPatch, start_delta: timedelta
) -> None:
    factory, asset, user, group = database
    roles = EffectiveRoles(is_owner=False, group_roles={group.id: GroupRole.USER})
    async with factory() as session:
        reservation = await ReservationService(
            session, settings=settings()
        ).create_for_current_user(
            roles,
            asset_id=asset.id,
            user_id=user.id,
            starts_at=NOW + start_delta,
            ends_at=NOW + timedelta(hours=2),
        )
        future = start_delta > timedelta()
        assert reservation.personal_start_eligible is future
        assert await session.scalar(
            select(func.count()).select_from(WebexDelivery)
        ) == (0 if future else 1)
        await session.commit()
        if future:
            monkeypatch.setattr("ara.services.webex.utc_now", lambda: NOW + start_delta)
        service = WebexService(session, settings())
        await service.generate_due()
        await service.generate_due()
        messages = list(await session.scalars(select(WebexDelivery)))
        assert {message.destination_type for message in messages} == (
            {"person", "room"} if future else {"room"}
        )
        assert len(messages) == (2 if future else 1)
        assert all(
            message.kind == "start"
            and "Test User" in message.text
            and f"/assets/{asset.id}" in message.text
            for message in messages
        )


async def test_personal_reminders_ignore_room_settings_and_track_extensions(
    database: tuple,
) -> None:
    factory, asset, user, group = database
    async with factory() as session:
        stored_asset = await session.get(Asset, asset.id)
        stored_asset.room_notifications_enabled = False
        reservation = Reservation(
            asset_id=asset.id,
            user_id=user.id,
            starts_at=NOW - timedelta(hours=2),
            ends_at=NOW + timedelta(minutes=10),
        )
        session.add(reservation)
        await session.commit()
        service = WebexService(session, settings())
        await service.generate_due()
        await service.generate_due()
        messages = list(await session.scalars(select(WebexDelivery)))
        assert len(messages) == 2
        assert {item.kind for item in messages} == {
            "end_reminder:60",
            "end_reminder:15",
        }
        assert all(
            item.destination_type == "person" and item.destination == user.email
            for item in messages
        )
        reservation.ends_at = NOW + timedelta(minutes=30)
        await session.commit()
        await service.generate_due()
        assert (
            await session.scalar(select(func.count()).select_from(WebexDelivery)) == 3
        )
        await session.commit()
        sent = []

        def handle(request: httpx.Request) -> httpx.Response:
            sent.append(json.loads(request.content))
            return httpx.Response(200, json={"id": "message-1"})

        client = WebexClient("token", httpx.MockTransport(handle))
        assert await service.dispatch(client) == 1
        assert len(sent) == 1
        assert sent[0]["toPersonEmail"] == user.email
        assert "10:30" in sent[0]["text"]
        await client.close()


async def test_return_is_transactional_and_cancellation_has_no_message(
    database: tuple,
) -> None:
    factory, asset, user, group = database
    roles = EffectiveRoles(is_owner=False, group_roles={group.id: GroupRole.USER})
    async with factory() as session:
        reservations = ReservationService(session, settings=settings())
        current = await reservations.create_for_current_user(
            roles,
            asset_id=asset.id,
            user_id=user.id,
            starts_at=NOW,
            ends_at=NOW + timedelta(hours=1),
        )
        future = await reservations.create_for_current_user(
            roles,
            asset_id=asset.id,
            user_id=user.id,
            starts_at=NOW + timedelta(hours=2),
            ends_at=None,
        )
        await reservations.cancel(roles, actor_id=user.id, reservation_id=future.id)
        await reservations.return_own(
            roles, actor_id=user.id, reservation_id=current.id
        )
        messages = list(await session.scalars(select(WebexDelivery)))
        assert sorted(item.kind for item in messages) == ["return", "start"]
        await session.commit()
        client = WebexClient(
            "token",
            httpx.MockTransport(lambda _: httpx.Response(200, json={"id": "return-1"})),
        )
        assert await WebexService(session, settings()).dispatch(client) == 1
        await client.close()
        messages = list(await session.scalars(select(WebexDelivery)))
        assert {item.kind: item.state for item in messages} == {
            "start": "skipped",
            "return": "delivered",
        }


@pytest.mark.parametrize("missing", ["email", "room", "asset_disabled"])
async def test_missing_destinations_do_not_block_events(
    database: tuple, missing: str
) -> None:
    factory, asset, user, group = database
    async with factory() as session:
        if missing == "email":
            (await session.get(User, user.id)).email = None
        elif missing == "room":
            (await session.get(Group, group.id)).webex_room_id = None
        else:
            (await session.get(Asset, asset.id)).room_notifications_enabled = False
        reservation = Reservation(
            asset_id=asset.id, user_id=user.id, starts_at=NOW, ends_at=None
        )
        session.add(reservation)
        await session.flush()
        await WebexService(session, settings()).enqueue_event(
            reservation, "start", NOW, personal=True, room=True
        )
        await session.commit()
        messages = list(await session.scalars(select(WebexDelivery)))
        assert len(messages) == 2
        assert sum(item.state == "skipped" for item in messages) == 1


async def test_disabled_webex_and_rolled_back_events(database: tuple) -> None:
    factory, asset, user, group = database
    async with factory() as session:
        reservation = Reservation(
            asset_id=asset.id, user_id=user.id, starts_at=NOW, ends_at=None
        )
        session.add(reservation)
        await session.flush()
        await WebexService(session, settings(enabled=False)).enqueue_event(
            reservation, "start", NOW, personal=True, room=True
        )
        assert (
            await session.scalar(select(func.count()).select_from(WebexDelivery)) == 0
        )
        await WebexService(session, settings()).enqueue_event(
            reservation, "start", NOW, room=True
        )
        await session.rollback()
    async with factory() as session:
        assert (
            await session.scalar(select(func.count()).select_from(WebexDelivery)) == 0
        )
        assert await session.scalar(select(func.count()).select_from(Reservation)) == 0


async def test_link_lookup_missing_token_preserves_settings(database: tuple) -> None:
    factory, _, _, group = database
    async with factory() as session:
        with pytest.raises(DomainError) as error:
            await GroupService(session).update_webex(
                EffectiveRoles(is_owner=True, group_roles={}),
                group.id,
                None,
                space_link=LINK,
                resolve_link=True,
                settings=settings(enabled=False),
            )
        assert error.value.code == "missing_bot_token"
        stored = await session.get(Group, group.id)
        assert stored.webex_room_id == "room-1"
        assert stored.webex_space_link is None
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_link_lookup_releases_write_lock_and_rechecks_archive(
    database: tuple,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    factory, _, _, group = database

    async def handle(request: httpx.Request) -> httpx.Response:
        # A concurrent writer must finish while the lookup is in progress.
        async with factory() as other:
            stored = await other.get(Group, group.id)
            stored.archived_at = NOW
            await other.commit()
        return httpx.Response(200, json={"items": [{"id": ROOM, "type": "group"}]})

    monkeypatch.setattr(
        "ara.services.groups.WebexClient",
        lambda token: WebexClient(token, httpx.MockTransport(handle)),
    )
    async with factory() as session:
        # Simulate pending session maintenance having acquired a write lock.
        stored = await session.get(Group, group.id)
        stored.description = "uncommitted maintenance"
        await session.flush()
        with pytest.raises(DomainError) as error:
            await GroupService(session).update_webex(
                EffectiveRoles(is_owner=True, group_roles={}),
                group.id,
                None,
                space_link=LINK,
                resolve_link=True,
                settings=settings(),
            )
        assert error.value.code == "group_archived"
        stored = await session.get(Group, group.id)
        assert stored.webex_room_id == "room-1"
        assert stored.webex_space_link is None
        assert await session.scalar(select(func.count()).select_from(AuditEvent)) == 0


async def test_restart_recovery_rate_limit_and_no_duplicate_success(
    database: tuple, monkeypatch: pytest.MonkeyPatch
) -> None:
    factory, asset, user, group = database
    roles = EffectiveRoles(is_owner=True, group_roles={})
    async with factory() as session:
        delivery = await WebexService(session, settings()).test_room(roles, group.id)
        delivery.state = "sending"
        delivery.claimed_at = NOW - timedelta(minutes=6)
        await session.commit()
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, headers={"Retry-After": "120"})
        return httpx.Response(200, json={"id": "success"})

    client = WebexClient("token", httpx.MockTransport(handle))
    async with factory() as session:
        assert await WebexService(session, settings()).dispatch(client) == 0
    async with factory() as session:
        assert await WebexService(session, settings()).dispatch(client) == 0
    assert len(calls) == 1
    monkeypatch.setattr(
        "ara.services.webex.utc_now", lambda: NOW + timedelta(minutes=3)
    )
    async with factory() as session:
        assert await WebexService(session, settings()).dispatch(client) == 1
        assert await WebexService(session, settings()).dispatch(client) == 0
        item = await session.scalar(select(WebexDelivery))
        assert item.attempts == 2 and item.message_id == "success"
    assert len(calls) == 2
    await client.close()


@pytest.mark.parametrize(
    "status,code",
    [
        (400, "invalid_destination"),
        (401, "invalid_bot_token"),
        (403, "permission_denied"),
        (404, "recipient_not_found"),
        (500, "webex_unavailable"),
    ],
)
async def test_failures_are_sanitized_and_classified(
    database: tuple, status: int, code: str
) -> None:
    factory, _, _, group = database
    async with factory() as session:
        service = WebexService(session, settings())
        await service.test_room(EffectiveRoles(is_owner=True, group_roles={}), group.id)
        client = WebexClient(
            "token",
            httpx.MockTransport(
                lambda _: httpx.Response(status, text="secret response body")
            ),
        )
        await service.dispatch(client)
        item = await session.scalar(select(WebexDelivery))
        assert item.error_code == code
        assert item.state == ("pending" if status == 500 else "failed")
        await client.close()


async def test_stale_room_and_future_starts_are_suppressed(database: tuple) -> None:
    factory, asset, user, group = database
    async with factory() as session:
        service = WebexService(session, settings())
        await service.test_room(EffectiveRoles(is_owner=True, group_roles={}), group.id)
        (await session.get(Group, group.id)).webex_room_id = "different-room"
        session.add_all(
            [
                Reservation(
                    asset_id=asset.id,
                    user_id=user.id,
                    starts_at=NOW - timedelta(hours=2),
                    ends_at=None,
                    personal_start_eligible=True,
                    start_notification_processed=False,
                ),
                Reservation(
                    asset_id=asset.id,
                    user_id=user.id,
                    starts_at=NOW - timedelta(minutes=2),
                    ends_at=None,
                    status=ReservationStatus.CANCELLED,
                    personal_start_eligible=True,
                    start_notification_processed=False,
                ),
            ]
        )
        await session.commit()
        await service.generate_due()
        client = WebexClient(
            "token",
            httpx.MockTransport(
                lambda _: pytest.fail("Stale messages must not be sent")
            ),
        )
        assert await service.dispatch(client) == 0
        assert (
            await session.scalar(select(WebexDelivery))
        ).error_code == "room_changed"
        await client.close()


ApiFixture = tuple[ASGIClient, uuid.UUID, uuid.UUID, dict[str, EffectiveRoles]]


@pytest.fixture
def api(tmp_path: Path) -> Iterator[ApiFixture]:
    engine = create_engine(f"sqlite+aiosqlite:///{tmp_path / 'api.db'}")
    factory = create_session_factory(engine)

    async def setup() -> tuple[uuid.UUID, uuid.UUID]:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
        async with factory() as session:
            groups = [Group(name="Lab", webex_room_id="room-1"), Group(name="Other")]
            session.add_all(groups)
            await session.commit()
            session.add(
                WebexDelivery(
                    group_id=groups[0].id,
                    event_key="private-event",
                    kind="start",
                    destination_type="person",
                    destination="private@example.test",
                    text="Private message",
                    state="pending",
                    scheduled_for=NOW,
                    next_attempt_at=NOW,
                )
            )
            await session.commit()
            return groups[0].id, groups[1].id

    group_id, other_id = asyncio.run(setup())
    app = create_app()
    roles = {
        "value": EffectiveRoles(
            is_owner=False, group_roles={group_id: GroupRole.GROUP_ADMIN}
        )
    }

    async def session_dependency() -> AsyncIterator[AsyncSession]:
        async with factory() as session:
            yield session

    async def csrf() -> None:
        pass

    app.dependency_overrides[group_router.get_effective_roles] = lambda: roles["value"]
    app.dependency_overrides[get_settings] = settings
    app.dependency_overrides[group_router.get_session] = session_dependency
    app.dependency_overrides[auth_router.require_csrf] = csrf
    with ASGIClient(app) as client:
        yield client, group_id, other_id, roles
    asyncio.run(engine.dispose())


def test_group_webex_api_is_scoped_and_status_is_private(api: ApiFixture) -> None:
    client, group_id, other_id, roles = api
    url = f"/api/groups/{group_id}/webex"
    response = client.patch(url, json={"webex_room_id": " room-2 "})
    assert response.status_code == 200 and response.json()["webex_room_id"] == "room-2"
    assert client.patch(url, json={"webex_room_id": "not a room"}).status_code == 422
    assert client.post(url + "/test").status_code == 202
    status = client.get(url).json()
    assert status["counts"] == {"pending": 1}
    assert "destination" not in status["items"][0] and "text" not in status["items"][0]
    assert client.get(f"/api/groups/{other_id}/webex").status_code == 403
    assert (
        client.patch(
            f"/api/groups/{other_id}/webex", json={"webex_room_id": "room"}
        ).status_code
        == 403
    )
    assert client.post(f"/api/groups/{other_id}/webex/test").status_code == 403
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={group_id: GroupRole.USER}
    )
    assert client.get(url).status_code == 403
    assert client.post(url + "/test").status_code == 403


def test_space_link_update_requires_csrf(monkeypatch: pytest.MonkeyPatch) -> None:
    app = create_app()
    app.dependency_overrides[group_router.get_effective_roles] = lambda: EffectiveRoles(
        is_owner=True, group_roles={}
    )
    app.dependency_overrides[auth_router.get_current_application_session] = lambda: (
        ApplicationSession(csrf_token_hash="unused")
    )
    monkeypatch.setattr(
        "ara.services.groups.WebexClient",
        lambda _: pytest.fail("CSRF failure must not contact Webex"),
    )
    with ASGIClient(app) as client:
        response = client.patch(
            f"/api/groups/{uuid.uuid4()}/webex",
            json={"webex_space_link": LINK},
        )
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "csrf_validation_failed"


def test_space_link_save_reload_test_clear_and_authorization(
    api: ApiFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, group_id, other_id, roles = api
    calls = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        return httpx.Response(200, json={"items": [{"id": ROOM, "type": "group"}]})

    monkeypatch.setattr(
        "ara.services.groups.WebexClient",
        lambda token: WebexClient(token, httpx.MockTransport(handle)),
    )
    url = f"/api/groups/{group_id}/webex"
    response = client.patch(url, json={"webex_space_link": LINK})
    assert response.status_code == 200
    assert response.json()["webex_room_id"] == ROOM
    assert response.json()["webex_space_link"] == LINK
    assert client.get(f"/api/groups/{group_id}").json()["webex_space_link"] == LINK
    assert client.post(url + "/test").status_code == 202
    assert (
        client.patch(
            url, json={"webex_space_link": LINK + "&space=" + str(SPACE)}
        ).status_code
        == 422
    )
    assert client.get(f"/api/groups/{group_id}").json()["webex_room_id"] == ROOM
    assert (
        client.patch(
            f"/api/groups/{other_id}/webex", json={"webex_space_link": LINK}
        ).status_code
        == 403
    )
    roles["value"] = EffectiveRoles(
        is_owner=False, group_roles={group_id: GroupRole.USER}
    )
    assert client.patch(url, json={"webex_space_link": LINK}).status_code == 403
    assert len(calls) == 1
    roles["value"] = EffectiveRoles(is_owner=True, group_roles={})
    response = client.patch(url, json={"webex_space_link": None})
    assert response.status_code == 200
    assert response.json()["webex_room_id"] is None
    assert response.json()["webex_space_link"] is None
    assert client.post(url + "/test").status_code == 409
    assert client.post(f"/api/groups/{group_id}/archive").status_code == 200
    assert client.patch(url, json={"webex_space_link": LINK}).status_code == 409
    assert len(calls) == 1


@pytest.mark.parametrize(
    "failure,code",
    [
        (401, "invalid_bot_token"),
        (403, "request_rejected"),
        (429, "rate_limited"),
        (500, "webex_unavailable"),
        ("network", "webex_unavailable"),
        ("empty", "space_not_visible"),
        ("direct", "direct_space"),
        ("malformed", "webex_unavailable"),
    ],
)
def test_lookup_failures_preserve_configuration(
    api: ApiFixture,
    monkeypatch: pytest.MonkeyPatch,
    failure: int | str,
    code: str,
) -> None:
    client, group_id, _, _ = api

    def handle(request: httpx.Request) -> httpx.Response:
        if failure == "network":
            raise httpx.ConnectError("sensitive detail", request=request)
        if failure == "missing":
            pytest.fail("Missing token must not trigger a lookup")
        if isinstance(failure, int):
            return httpx.Response(failure, text="sensitive body")
        if failure == "direct":
            return httpx.Response(200, json={"items": [{"id": ROOM, "type": "direct"}]})
        return httpx.Response(
            200, json={"items": []} if failure == "empty" else {"bad": "sensitive body"}
        )

    monkeypatch.setattr(
        "ara.services.groups.WebexClient",
        lambda token: WebexClient(token, httpx.MockTransport(handle)),
    )
    response = client.patch(
        f"/api/groups/{group_id}/webex", json={"webex_space_link": LINK}
    )
    assert response.status_code in (422, 503)
    assert response.json()["error"]["code"] == code
    assert "sensitive" not in response.text
    if failure == "empty":
        assert "Add ARA Notification Bot" in response.json()["error"]["message"]
    stored = client.get(f"/api/groups/{group_id}").json()
    assert stored["webex_room_id"] == "room-1"
    assert stored["webex_space_link"] is None


async def test_reminder_batches_progress_past_already_queued_reservations(
    database: tuple,
) -> None:
    factory, asset, user, _ = database
    async with factory() as session:
        session.add_all(
            [
                Reservation(
                    asset_id=asset.id,
                    user_id=user.id,
                    starts_at=NOW - timedelta(hours=2),
                    ends_at=NOW + timedelta(minutes=10),
                )
                for _ in range(101)
            ]
        )
        await session.commit()
        service = WebexService(session, settings())
        await service.generate_due()
        await service.generate_due()
        await service.generate_due()
        assert (
            await session.scalar(select(func.count()).select_from(WebexDelivery)) == 202
        )


async def test_recovered_exhausted_attempts_do_not_send_again(database: tuple) -> None:
    factory, _, _, group = database
    async with factory() as session:
        service = WebexService(session, settings())
        delivery = await service.test_room(
            EffectiveRoles(is_owner=True, group_roles={}), group.id
        )
        delivery.state, delivery.attempts = "sending", 6
        delivery.claimed_at = NOW - timedelta(minutes=6)
        await session.commit()
        client = WebexClient(
            "token",
            httpx.MockTransport(
                lambda _: pytest.fail("Exhausted messages must not send")
            ),
        )
        assert await service.dispatch(client) == 0
        item = await session.scalar(select(WebexDelivery))
        assert item.state == "failed" and item.error_code == "retry_exhausted"
        await client.close()
