import argparse
import asyncio
import logging
import time
import traceback

from cogbot.cog_bot import CogBot
from cogbot.cog_bot_state import CogBotState

log = logging.getLogger(__name__)


# TODO Consider switching to the library rewrite: https://github.com/Rapptz/discord.py/tree/rewrite
# The rewrite has auto-reconnect behaviour: https://github.com/Rapptz/discord.py/blob/rewrite/discord/client.py#L405
# This would make our hacky crash workarounds trivial.


def _attempt_logout(loop, bot):
    try:
        log.info('Logging out...')
        loop.run_until_complete(bot.logout())

        log.info('Gathering leftover tasks...')
        pending = asyncio.Task.all_tasks(loop=loop)
        gathered = asyncio.gather(*pending, loop=loop)

        log.info('Cancelling leftover tasks...')
        gathered.cancel()
        loop.run_until_complete(gathered)
        gathered.exception()

    except Exception as ex:
        log.critical(f'Encountered an error while attempting to logout: {ex}')
        traceback.print_tb(ex.__traceback__)
        bot.force_logout()


def run():
    state = CogBotState(args.state)

    loop = asyncio.get_event_loop()

    last_death = None

    while True:
        log.info('Starting bot...')
        bot = CogBot(state=state, loop=loop)

        if last_death:
            for manager in state.managers:
                message = f'Hello! I\'ve just recovered from a fatal crash caused by: `{last_death}`'
                bot.queue_message(bot.get_user_info, manager, message)

        try:
            loop.run_until_complete(bot.start(args.token))

        except KeyboardInterrupt:
            _attempt_logout(loop, bot)
            break

        except Exception as ex:
            last_death = ex

            log.critical(f'Encountered a fatal exception: {ex}')
            traceback.print_tb(ex.__traceback__)

            log.warning('Attempting clean logout...')
            _attempt_logout(loop, bot)

            log.warning(f'Restarting bot in {state.restart_delay} seconds...')
            time.sleep(state.restart_delay)

    log.info('Closing loop...')
    loop.close()

    log.info('Bot terminated')


arg_parser = argparse.ArgumentParser()
arg_parser.add_argument('token')
arg_parser.add_argument('--log', help='Log level', default='WARNING')
arg_parser.add_argument('--state', help='Bot state file', default='bot.json')
args = arg_parser.parse_args()

try:
    import loggy

    loggy.install(level=args.log)
except:
    logging.basicConfig(level=args.log)

log.info('Hello!')
run()
log.info('Goodbye!')
