# region Imports
from typing import Dict, TYPE_CHECKING
from os import getenv
from dotenv import load_dotenv
if TYPE_CHECKING:
    from subprocess import Popen
    from discord.ext.commands import Bot  # type: ignore
    from blockchain.models.blockchain import Blockchain
    from models.checkpoints import ChannelCheckpoints
    from models.grifter_suppliers import GrifterSuppliers
    from models.log import Log
    from models.slot_machine import SlotMachine
    from models.transfers_waiting_approval import TransfersWaitingApproval
    from utils.decrypt_transactions import DecryptedTransactionsSpreadsheet
# endregion

# region Constants
load_dotenv()

DISCORD_TOKEN: str | None = getenv('DISCORD_TOKEN')
# endregion

# region Global variables

# Number of messages to keep track of in each channel
per_channel_checkpoint_limit: int = 3
active_slot_machine_players: Dict[int, float] = {}
starting_bonus_timeout: int = 30
time_zone: str = "Canada/Central"

waitress_process: "Popen[str] | None" = None
log: "Log | None" = None
blockchain: "Blockchain | None" = None
slot_machine: "SlotMachine | None" = None
grifter_suppliers: "GrifterSuppliers | None" = None
transfers_waiting_approval: "TransfersWaitingApproval | None" = None
decrypted_transactions_spreadsheet: (
    "DecryptedTransactionsSpreadsheet | None") = None
bot: "Bot | None" = None

# Bot configuration
coin: str = ""
Coin: str = ""
coins: str = ""
Coins: str = ""
coin_emoji_id: int = 0
coin_emoji_name: str = ""
casino_house_id: int = 0
administrator_id: int = 0
casino_channel_id: int = 0
blockchain_name: str = ""
Blockchain_name: str = ""
grifter_swap_id: int = 0
sbcoin_id: int = 0
auto_approve_transfer_limit: int = 0
aml_office_thread_id: int = 0

all_channel_checkpoints: "Dict[int, ChannelCheckpoints]" = {}

about_command_formatted: str | None = None

active_slot_machine_players: Dict[int, float] = {}
# endregion

# region Get variables
def get_variables():
    return (per_channel_checkpoint_limit,
            active_slot_machine_players,
            starting_bonus_timeout,
            waitress_process,
            log,
            blockchain,
            slot_machine,
            grifter_suppliers,
            transfers_waiting_approval,
            coin,
            Coin,
            coins,
            Coins,
            coin_emoji_id,
            coin_emoji_name,
            casino_house_id,
            administrator_id,
            casino_channel_id,
            blockchain_name,
            Blockchain_name,
            about_command_formatted,
            grifter_swap_id,
            sbcoin_id,
            auto_approve_transfer_limit,
            aml_office_thread_id)
# endregion