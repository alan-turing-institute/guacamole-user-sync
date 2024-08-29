#! /usr/bin/env python3
import logging
import os
import time

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO,
    format=r"%(asctime)s [%(levelname)-8s] %(message)s",
    datefmt=r"%Y-%m-%d %H:%M:%S",
)


def main(repeat_interval: int):
    logger.info("Starting synchronisation.")
    synchronise()
    logger.info(f"Waiting {repeat_interval} seconds.")
    time.sleep(repeat_interval)


def synchronise():
    logger.info("Synchronising...")


if __name__ == "__main__":
    main(repeat_interval=int(os.getenv("REPEAT_INTERVAL", 10)))
