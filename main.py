import logging
import os

from busi.claude_agent import register_weixin_claude_handler
from lib.task_scheduler import TaskScheduler
from lib.tasks.get_latest_news import run_get_latest_news
from lib.weixin_bot.daemon import PersonalWeixinDaemon


def _log_level_from_env() -> int:
    name = os.environ.get("LOG_LEVEL", "INFO").strip().upper()
    level = getattr(logging, name, None)
    if isinstance(level, int):
        return level
    return logging.INFO


def main() -> None:
    logging.basicConfig(
        level=_log_level_from_env(),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    scheduler = TaskScheduler()
    scheduler.register_interval_task(
        name="get_latest_news",
        func=run_get_latest_news,
        interval_seconds=60 * 30,
        run_on_start=False,
    )
    scheduler.start()

    daemon = PersonalWeixinDaemon()
    register_weixin_claude_handler(daemon)
    try:
        daemon.run_forever()
    finally:
        scheduler.stop()


if __name__ == "__main__":
    main()
