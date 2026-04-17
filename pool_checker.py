import os
import sys
import ast
import logging
import httpx
from datetime import datetime

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

THRESHOLD_HOURS = 72

POOL_CONFIGS = [
    {
        "name": "ys",
        "url": "https://raw.githubusercontent.com/PaiGramTeam/PaiGram/refs/heads/main/metadata/pool/pool_301.py",
        "push_key": "ys",
    },
    {
        "name": "sr",
        "url": "https://raw.githubusercontent.com/PaiGramTeam/PamGram/refs/heads/sr/metadata/pool/pool_11.py",
        "push_key": "sr",
    },
    {
        "name": "zzz",
        "url": "https://raw.githubusercontent.com/PaiGramTeam/MibooGram/refs/heads/zzz/metadata/pool/pool_2.py",
        "push_key": "zzz",
    },
]


def fetch_remote_data(url):
    """Fetch data from remote URL using httpx"""
    try:
        logger.info(f"Fetching data from {url}")
        with httpx.Client(timeout=10.0) as client:
            response = client.get(url)
            response.raise_for_status()
        logger.info(f"Successfully fetched data from {url}")
        return response.text
    except httpx.TimeoutException:
        logger.error(f"Request timeout while fetching data from {url}")
        raise
    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error {e.response.status_code} while fetching {url}")
        raise
    except httpx.RequestError as e:
        logger.error(f"Request failed for {url}: {e}")
        raise


def parse_remote_data(data):
    """Parse the remote data into Python object"""
    try:
        string = "[\n" + "\n".join(data.split("\n")[1:])
        parsed_data = ast.literal_eval(string)
        logger.info("Successfully parsed remote data")
        return parsed_data
    except (SyntaxError, ValueError) as e:
        logger.error(f"Failed to parse remote data: {e}")
        raise


def check_pool_expiration(pool_data, pool_name):
    """Check if pool is expiring soon or already expired"""
    try:
        to_field = pool_data[0]["to"]
        logger.info(f"[{pool_name}] Extracted 'to' field: {to_field}")

        expiration_time = datetime.strptime(to_field, "%Y-%m-%d %H:%M:%S")
        current_time = datetime.now()
        time_difference = expiration_time - current_time

        logger.info(f"[{pool_name}] Current time: {current_time}")
        logger.info(f"[{pool_name}] Expiration time: {expiration_time}")
        logger.info(f"[{pool_name}] Time remaining: {time_difference}")

        hours_remaining = time_difference.total_seconds() / 3600

        if hours_remaining < THRESHOLD_HOURS or hours_remaining <= 0:
            logger.info(
                f"[{pool_name}] Pool is expiring soon or expired. Hours remaining: {hours_remaining:.2f}"
            )
            return True
        else:
            logger.info(
                f"[{pool_name}] Pool is not expiring soon. Hours remaining: {hours_remaining:.2f}"
            )
            return False

    except KeyError as e:
        logger.error(f"[{pool_name}] Missing required field in pool data: {e}")
        raise
    except ValueError as e:
        logger.error(f"[{pool_name}] Invalid datetime format in 'to' field: {e}")
        raise


def send_telegram_notification(bot_token, chat_id, message):
    """Send notification via Telegram bot"""
    try:
        from telegram import Bot
        import asyncio

        bot = Bot(token=bot_token)
        logger.info(f"Sending Telegram message to chat_id: {chat_id}")

        async def send_message():
            await bot.send_message(chat_id=chat_id, text=message)

        asyncio.run(send_message())
        logger.info("Telegram message sent successfully")

    except Exception as e:
        logger.error(f"Failed to send Telegram message: {e}")
        raise


def main():
    """Main function to orchestrate the pool checking process"""
    logger.info("=" * 50)
    logger.info("Starting pool expiration checker")
    logger.info("=" * 50)

    need_push = []

    try:
        for config in POOL_CONFIGS:
            pool_name = config["name"]
            url = config["url"]
            push_key = config["push_key"]

            logger.info(f"\nChecking {pool_name} pool...")

            try:
                remote_data = fetch_remote_data(url)
                parsed_data = parse_remote_data(remote_data)

                if check_pool_expiration(parsed_data, pool_name):
                    need_push.append(push_key)

            except Exception as e:
                logger.error(f"Failed to check {pool_name} pool: {e}")
                continue

        logger.info(f"\nPools to push: {need_push}")

        if need_push:
            bot_token = os.environ.get("bot_token")
            chat_id = os.environ.get("chat_id")

            if not bot_token or not chat_id:
                logger.error(
                    "Missing required environment variables: bot_token or chat_id"
                )
                sys.exit(1)

            game_names = {"ys": "原神", "sr": "星穹铁道", "zzz": "绝区零"}

            games = [game_names.get(key, key) for key in need_push]
            message = (
                f"#notice 以下游戏卡池即将结束或已结束，请注意更新：{', '.join(games)}"  # noqa
            )

            send_telegram_notification(bot_token, chat_id, message)
        else:
            logger.info("No notification needed - all pools are not expiring soon")

        logger.info("Pool checking completed successfully")

    except Exception as e:
        logger.error(f"Script failed with error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
