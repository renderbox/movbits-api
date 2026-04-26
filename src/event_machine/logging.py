import json
import logging

from django.utils.timezone import now as django_now

from .models import LogBlock
from .redis_client import redis_client as r

# Configure logging to display debug-level messages
logging.basicConfig(level=logging.DEBUG)

logger = logging.getLogger(__name__)


def get_time_block(dt, interval=5):
    """
    Calculate the time block for a given datetime object.

    Args:
        dt (datetime): The datetime object to calculate the time block for.
        interval (int): The interval in minutes for the time block.

    Returns:
        str: The formatted time block as a string.
    """
    minute_block = dt.minute - (dt.minute % interval)
    return dt.replace(minute=minute_block, second=0, microsecond=0).strftime(
        "%Y%m%dT%H%M"
    )


def log_event(group, user_id, request=None, **kwargs):
    """
    Log an event with the specified group, user ID, and additional data.

    Args:
        group (str): The group to manage log queues.
        user_id (int): The ID of the user associated with the event.
        request (HttpRequest, optional): The HTTP request object to extract IP address.
        **kwargs: Additional data to include in the event.

    Returns:
        None
    """
    current_time = django_now()
    time_block = get_time_block(current_time)

    serializable_kwargs = {}
    for key, value in kwargs.items():
        try:
            json.dumps(value)
            serializable_kwargs[key] = value
        except (TypeError, ValueError):
            logger.warning(
                f"[event_machine] Non-serializable kwarg '{key}': {repr(value)}"
            )

    # Extract fields from the request if available
    ip_address = request.META.get("REMOTE_ADDR") if request else None

    event = {
        "timestamp": current_time.isoformat(),
        "group": group,
        "user_id": user_id,
        "ip_address": ip_address,
        **serializable_kwargs,
    }

    logger.debug(
        f"Logging event: {event}, group: {group}, user_id: {user_id}, time_block: {time_block}"
    )

    # Create or update LogBlock in the database
    logger.debug(
        f"Creating or updating LogBlock for group: {group}, user_id: {user_id}, time_block: {time_block}"
    )

    log_block, created = LogBlock.objects.get_or_create(
        group=group,
        time_block=time_block,
        user=user_id,
        defaults={"log_data": [], "statistics": {}},
    )

    logger.debug(
        f"LogBlock created: {created}, existing log_data: {log_block.log_data}"
    )

    log_block.log_data.append(event)
    log_block.save()

    logger.debug(f"LogBlock updated with new event: {event}")

    # Log the event to the Django logger in JSON format with a prefix for filtering
    logger.info(f"[event_machine_log] {json.dumps(event)}")

    # Add the event to Redis for redundancy
    key = f"log_buffer:{group}:{time_block}"
    r.rpush(key, json.dumps(event))
