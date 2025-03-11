# region Imports
# Third party
from discord import Member
from discord.raw_models import RawReactionActionEvent
from discord.ext.commands import Bot  # type: ignore

# Local
from core.global_state import bot
from utils.process_reaction import process_reaction
# endregion

# region Reaction
# assert bot is not None, "bot has not been initialized."
assert isinstance(bot, Bot), "bot has not been initialized."


@bot.event
async def on_raw_reaction_add(payload: RawReactionActionEvent) -> None:
    """
    Handles the event when a reaction is added to a message.
    The process_reaction_function is called, which adds a transaction if the
    reaction is the coin emoji set in the configuration.

    Args:
        payload: An instance of the RawReactionActionEvent
            class from the discord.raw_models module that contains the data of
            the reaction event.
    """

    if payload.event_type == "REACTION_ADD":
        if payload.message_author_id is None:
            return

        sender: Member | None = payload.member
        if sender is None:
            print("ERROR: Sender is None.")
            return
        receiver_user_id: int = payload.message_author_id
        message_id: int = payload.message_id
        channel_id: int = payload.channel_id

        await process_reaction(message_id=message_id,
                               emoji=payload.emoji,
                               sender=sender,
                               receiver_id=receiver_user_id,
                               channel_id=channel_id)
        del receiver_user_id
        del sender
        del message_id
# endregion
