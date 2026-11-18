"""The outbox worker: the postman who empties the outbox tray and sends the emails.

Run:  python -m leavedesk.worker          (keeps going, checks every second)
      python -m leavedesk.worker --once   (one pass, then stops)

Why a tray? The approval and its "please email Priya" row are saved in ONE transaction,
so either both happen or neither does. If the email server is down, the row simply
waits and is sent on a later pass. Nothing is lost and nothing is sent by mistake."""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import Session, sessionmaker

from leavedesk.api.config import DatabaseSettings
from leavedesk.db.engine import make_engine, make_session_factory
from leavedesk.db.models import OutboxRow
from leavedesk.db.repository import SqlAlchemyLeaveRepository
from leavedesk.domain.models import NotificationEvent
from leavedesk.domain.notifications import EmailNotifier, NotificationService

log = logging.getLogger("leavedesk.worker")


async def drain_outbox(
    session_factory: sessionmaker[Session],
    notifications: NotificationService,
    batch_size: int = 20,
) -> int:
    """Send up to batch_size waiting messages. Returns how many were sent."""
    repo = SqlAlchemyLeaveRepository(session_factory)
    with session_factory() as session, session.begin():
        # FOR UPDATE SKIP LOCKED: lock the rows we take, and SKIP rows another worker
        # has already locked. So two workers never send the same email twice.
        rows = session.scalars(
            select(OutboxRow)
            .where(OutboxRow.processed_at.is_(None))
            .order_by(OutboxRow.id)
            .limit(batch_size)
            .with_for_update(skip_locked=True)
        ).all()
        for row in rows:
            request = repo.get_request(row.request_id)
            await notifications.notify(NotificationEvent(row.event), request)
            row.processed_at = func.now()  # marked sent; committed with the batch
    return len(rows)


async def run(once: bool, poll_seconds: float = 1.0) -> None:
    settings = DatabaseSettings()
    engine = make_engine(settings)
    session_factory = make_session_factory(engine)
    repo = SqlAlchemyLeaveRepository(session_factory)
    notifications = NotificationService(repo, [EmailNotifier(repo)])
    log.info("outbox worker started")
    try:
        while True:
            sent = await drain_outbox(session_factory, notifications)
            if sent:
                log.info("sent %d message(s)", sent)
            if once:
                break
            await asyncio.sleep(poll_seconds)
    finally:
        engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Send waiting LeaveDesk emails.")
    parser.add_argument("--once", action="store_true", help="one pass, then stop")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s")
    try:
        asyncio.run(run(args.once))
    except KeyboardInterrupt:
        pass  # Ctrl+C stops the worker quietly


if __name__ == "__main__":
    main()
