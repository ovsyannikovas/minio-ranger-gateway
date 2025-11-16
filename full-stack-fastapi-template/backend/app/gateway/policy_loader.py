"""Background task for loading policies from Ranger periodically."""

import asyncio
import logging
from typing import Any

from app.core.config import settings
from app.gateway.cache import set_policies
from app.gateway.ranger_client import get_ranger_client

logger = logging.getLogger(__name__)

# Background task
_policy_loader_task: asyncio.Task | None = None
_loader_running = False


async def load_policies(service_name: str | None = None) -> list[dict[str, Any]]:
    """
    Load policies from Ranger for a service.

    Args:
        service_name: Service name (defaults to config)

    Returns:
        List of policy dictionaries
    """
    service = service_name or settings.RANGER_SERVICE_NAME
    ranger_client = get_ranger_client()

    try:
        policies = await ranger_client.get_policies(service)
        logger.info(f"Loaded {len(policies)} policies for service {service}")
        set_policies(service, policies)
        return policies
    except Exception as e:
        logger.error(f"Error loading policies for service {service}: {e}")
        return []


async def policy_loader_loop(interval: int = 300) -> None:
    """
    Background task that periodically loads policies from Ranger.

    Args:
        interval: Refresh interval in seconds (default: 5 minutes)
    """
    global _loader_running
    _loader_running = True

    # Load immediately on start
    await load_policies()

    # Then load periodically
    while _loader_running:
        try:
            await asyncio.sleep(interval)
            await load_policies()
        except asyncio.CancelledError:
            logger.info("Policy loader task cancelled")
            break
        except Exception as e:
            logger.error(f"Error in policy loader loop: {e}")
            # Continue even on error
            await asyncio.sleep(interval)


def start_policy_loader(interval: int | None = None) -> None:
    """
    Start the background policy loader task.

    Args:
        interval: Refresh interval in seconds (defaults to RANGER_CACHE_TTL)
    """
    global _policy_loader_task
    if _policy_loader_task is not None and not _policy_loader_task.done():
        logger.warning("Policy loader already running")
        return

    refresh_interval = interval or settings.RANGER_CACHE_TTL
    _policy_loader_task = asyncio.create_task(policy_loader_loop(refresh_interval))
    logger.info(f"Started policy loader with interval {refresh_interval}s")


def stop_policy_loader() -> None:
    """Stop the background policy loader task."""
    global _policy_loader_task, _loader_running
    _loader_running = False
    if _policy_loader_task is not None:
        _policy_loader_task.cancel()
        logger.info("Stopped policy loader")

