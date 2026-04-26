import json
import logging

import boto3
import redis
from django.conf import settings

from .models import LogBlock
from .redis_client import redis_client as r

# from datetime import datetime, timezone


s3 = boto3.client("s3")
BUCKET = getattr(settings, "EVENT_MACHINE_S3_BUCKET_NAME")

# Configure logger
logger = logging.getLogger(__name__)


def flush_time_block(group, time_block):
    """
    Flush logs for a specific group and time block from Redis to S3.

    Args:
        group (str): The group to manage log queues.
        time_block (str): The time block identifier for the logs.

    Returns:
        int: The number of events flushed to S3.
    """
    # Log an info message when a flush is called
    # logger.info(f"Flush called for group: {group}, time_block: {time_block}")

    key = f"log_buffer:{group}:{time_block}"
    events = r.lrange(key, 0, -1)

    # Debug log the data stored in Redis keys
    try:
        data = r.lrange(key, 0, -1)  # Retrieve all elements of the list
        logger.debug(f"Redis key: {key}, Data: {data}")
    except redis.exceptions.ResponseError as e:
        logger.error(f"Error accessing Redis key: {key}, Error: {e}")

    logger.info(
        f"Flushing {len(events)} events for group: {group}, time_block: {time_block}"
    )
    logger.info(f"Events: {events}")

    # Ensure the LogBlock entry is created
    log_block, created = LogBlock.objects.get_or_create(
        group=group,
        time_block=time_block,
        defaults={"log_data": [], "statistics": {}},
    )

    if created:
        logger.info(
            f"Created new LogBlock for group: {group}, time_block: {time_block}"
        )

    # Append flushed events to log_data and remove each event from Redis as validated
    for event in events:
        try:
            decoded_event = json.loads(event.decode())
            log_block.log_data.append(decoded_event)
            r.lrem(key, 0, event)  # Remove the event from Redis
        except json.JSONDecodeError as e:
            logger.error(f"Failed to decode event: {event}, Error: {e}")

    log_block.save()

    # Validate the Redis key is empty and remove it
    remaining_events = r.lrange(key, 0, -1)
    if not remaining_events:
        try:
            r.delete(key)
            logger.info(f"Successfully removed Redis key: {key}")
        except redis.exceptions.ResponseError as e:
            logger.error(f"Failed to remove Redis key: {key}, Error: {e}")
    else:
        logger.warning(f"Redis key: {key} still contains events: {remaining_events}")

    # if not BUCKET:
    #     return len(events)

    # # Write the contents of the log_data file to S3 as a backup
    # s3.put_object(
    #     Bucket=BUCKET, Key=s3_key, Body=file_content, ContentType="application/json"
    # )

    return len(events)
