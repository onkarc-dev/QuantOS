"""QuantOS Redis/RQ worker entrypoint.

Run with:
    python -m app.worker

This module gives Docker, VPS deployments, and local operators a stable
application-aware worker command instead of relying on a raw `rq worker` shell
command. It initializes the database schema before processing jobs so the worker
can run independently from the API process startup order.
"""
from __future__ import annotations

import logging

from redis import Redis
from rq import Worker, Queue

from app.core.config import settings
from app.db import init_db


logger = logging.getLogger("quantos.worker")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    if not settings.redis_url:
        raise RuntimeError("REDIS_URL is required to run the QuantOS RQ worker")

    init_db()
    redis_conn = Redis.from_url(settings.redis_url)
    queue = Queue("prismflow", connection=redis_conn)
    worker = Worker([queue], connection=redis_conn)

    logger.info("Starting QuantOS RQ worker queue=prismflow db_backend=%s", settings.db_backend)
    worker.work(with_scheduler=False)


if __name__ == "__main__":
    main()
