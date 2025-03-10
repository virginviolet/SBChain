"""
Scopes:
- applications.commands
- bot

Permissions:
- Send Messages
- Read Message History

Privileged Gateway Intents:
- Server Members Intent
- Message Content Intent
"""

# region Imports
from typing import Dict
from pathlib import Path
from os.path import exists, basename
import os
import pandas as pd
import threading
import subprocess
import signal
import asyncio
import json
import pytz
import random
import math
import blockchain.sbchain as sbchain
from builtins import open
from time import sleep, time
from datetime import datetime
from humanfriendly import format_timespan
from discord import (Guild, Intents, Interaction, Member, Message, Client,
                     Emoji, MessageInteraction, PartialEmoji, Role, User,
                     TextChannel, VoiceChannel, app_commands, utils,
                     CategoryChannel, ForumChannel, StageChannel, DMChannel,
                     GroupChannel, Thread, AllowedMentions, InteractionMessage,
                     File)
from discord.app_commands import AppCommand
from discord.abc import PrivateChannel
from discord.ui import View, Button, Item
from discord.ext import commands
from discord.raw_models import RawReactionActionEvent
from discord.utils import MISSING
from os import environ as os_environ, getenv, makedirs
from os.path import exists
from dotenv import load_dotenv
from hashlib import sha256
from sys import exit as sys_exit
from sympy import (symbols, Expr, Add, Mul, Float, Integer, Eq, Lt, Ge, Gt,
                   Rational, simplify, Piecewise, pretty)
from _collections_abc import dict_items
from typing import (Dict, KeysView, List, LiteralString, NoReturn, TextIO, cast,
                    Literal, Any)
from type_aliases import (BotConfig, Reels, ReelSymbol,
                          ReelResult, ReelResults,
                          SpinEmojis, SlotMachineConfig,
                          SaveData, TransactionRequest, T)
from utils.get_project_root import get_project_root
# endregion

# region Bot setup
intents: Intents = Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot("!", intents=intents)
client = Client(intents=intents)
# Load .env file for the bot DISCORD_TOKEN
load_dotenv()
DISCORD_TOKEN: str | None = getenv('DISCORD_TOKEN')
# Number of messages to keep track of in each channel
per_channel_checkpoint_limit: int = 3
active_slot_machine_players: Dict[int, float] = {}
starting_bonus_timeout = 30
# endregion

# region Checkpoints


class ChannelCheckpoints:
    """
    ChannelCheckpoints is a class that manages checkpoints for a specific
    channel in a guild. It allows for saving, loading, and managing
    message IDs as checkpoints.

    Methods:
        __init__(self,
            guild_name,
            guild_id,
            channel_name,
            channel_id,
            max_checkpoints):
            Initializes checkpoints for a channel in a guild.
        count_lines(self):
        create(self):
            Creates a checkpoint file for the channel, including necessary
            directories and metadata files.
        save(self, message_id):
            Saves the given message ID as a checkpoint in the file.
            If the number of checkpoints exceeds the maximum allowed, the
            oldest checkpoint is removed.
        remove_first_line(self):
        load(self):
            Loads the checkpoints from the file specified by self.file_name.
        """

    def __init__(self,
                 guild_name: str,
                 guild_id: int,
                 channel_name: str,
                 channel_id: int,
                 max_checkpoints: int = 10) -> None:
        """
        Initialize checkpoints for a channel in a guild.

        Args:
            guild_name: The name of the guild
            guild_id: The ID of the guild
            channel_name: The name of the channel
            channel_id: The ID of the channel
            max_checkpoints: The maximum number of checkpoints

        Attributes:
            max_checkpoints: The maximum number of checkpoints
            guild_name: The name of the guild
            guild_id: The ID of the guild
            channel_name: The name of the channel
            channel_id: The ID of the channel
            directory: The directory path for storing checkpoints
            file_name: The file name for storing channel checkpoints
            entry_count: The count of entries in the checkpoints file
            last_message_ids: The last message IDs in the channel
        """
        self.max_checkpoints: int = max_checkpoints
        self.guild_name: str = guild_name
        self.guild_id: int = guild_id
        self.channel_name: str = channel_name
        self.channel_id: int = channel_id
        self.directory: str = (f"data/checkpoints/guilds/{self.guild_id}"
                               f"/channels/{self.channel_id}")
        self.file_name: str = f"{self.directory}/channel_checkpoints.json"
        self.entry_count: int = self.count_lines()
        self.last_message_ids: List[Dict[str, int]] | None = self.load()

    def count_lines(self) -> int:
        """
        Counts the number of lines in the file specified by self.file_name.
        Returns:
            int: The number of lines in the file. Returns 0 if the file
                does not exist.
        """
        if not exists(self.file_name):
            return 0

        with open(self.file_name, "r") as file:
            count: int = sum(1 for _ in file)
            return count

    def create(self) -> None:
        """
        Creates an checkpoint file for the channel.

        This method performs the following tasks:
        1. Creates any missing directories in the path specified
            by `self.file_name`.
        2. Writes the guild name to a JSON file named `guild_name.json` in
            the directory corresponding to the guild ID.
        3. Writes the channel name to a JSON file named `channel_name.json` in
            the directory corresponding to the channel ID.
        4. Creates an empty checkpoints file at the path specified
            by `self.file_name`.

        The directory structure is created based on the path specified
        in `self.file_name`.
        The guild and channel names are written to files in directories named
        after their IDs, allowing bot maintainers to identify guilds and
        channels by their names.
        """
        # Create missing directories
        directories: str = self.file_name[:self.file_name.rfind("/")]
        for i, directory in enumerate(directories.split("/")):
            path: str = "/".join(directories.split("/")[:i+1])
            if not exists(directory):
                makedirs(path, exist_ok=True)
            # Write the guild name and channel name to files in the id
            # directories, so that bot maintainers can identify the guilds and
            # channels
            # Channel names can change, but the IDs will not
            if directory.isdigit() and int(directory) == self.guild_id:
                name_file_name: str = f"{path}/guild_name.json"
                with open(name_file_name, "w") as file:
                    file.write(json.dumps({"guild_name": self.guild_name}))
                    pass
            elif directory.isdigit() and int(directory) == self.channel_id:
                name_file_name: str = f"{path}/channel_name.json"
                with open(name_file_name, "w") as file:
                    file.write(json.dumps({"channel_name": self.channel_name}))
                    pass

        print(f"Creating checkpoints file: '{self.file_name}'")
        with open(self.file_name, "w"):
            pass

    def save(self, message_id: int) -> None:
        """
        Saves the given message ID as a checkpoint in the file.
        If the file does not exist, it creates a new one. The message ID is
        appended to the file in JSON format. If the number of checkpoints
        exceeds the maximum allowed, the oldest checkpoint is removed.
        Args:
            message_id: The ID of the message to save as a checkpoint.
        """
        if not exists(self.file_name):
            self.create()

        # print(f"Saving checkpoint: {message_id}")
        self.entry_count = self.count_lines()
        with open(self.file_name, "a") as file:
            if self.entry_count == 0:
                file.write(json.dumps({"last_message_id": message_id}))
            else:
                file.write("\n" + json.dumps({"last_message_id": message_id}))
        self.entry_count += 1

        while self.entry_count > self.max_checkpoints:
            self.remove_first_line()
            self.entry_count -= 1

    def remove_first_line(self) -> None:
        """
        Removes the first line from the file specified by self.file_name.

        This method reads all lines from the file, then writes all lines except
        the first one
        back to the file, effectively removing the first line.
        """
        with open(self.file_name, "r") as file:
            lines: List[str] = file.readlines()
        with open(self.file_name, "w") as file:
            file.writelines(lines[1:])

    def load(self) -> List[Dict[str, int]] | None:
        """
        Loads checkpoints from a file.
        Returns:
            A list of dictionaries containing checkpoint data if the file
                exists, otherwise None.
        """
        if not exists(self.file_name):
            return None

        with open(self.file_name, "r") as file:
            checkpoints: List[Dict[str, int]] | None = []
            # print("Loading checkpoints...")
            for line in file:
                checkpoint: Dict[str, int] = (
                    {k: int(v) for k, v in json.loads(line).items()})
                # print(f"checkpoint: {checkpoint}")
                checkpoints.append(checkpoint)
                return checkpoints
# endregion

# region Log


class Log:
    """
    Provides functionality for logging events with timestamps to a file.
    For timestamps, the local time zone is used by default, but a different
    time zone can be specified.

    The log cannot be verified or generated from the blockchain.
    Use a validated transactions file for verification (see
    Blockchain.validate_transactions_file()).
    The log is meant to be a local record of interesting events on the server.

    Attributes:
        file_name: The name of the file where transactions are logged.
        time_zone: The time zone to be used for logging. If None, the
                    local time zone is used.
    Methods:
        __init__(file_name = "data/transactions.log", time_zone) -> None:
            Initializes the log file with the specified file name and time zone.
        create(): Creates the necessary directories and an empty log file.
        log(line, timestamp): Logs a line of text with a timestamp to the file.
    """

    def __init__(self,
                 file_name: str = "data/transactions.log",
                 time_zone: str | None = None) -> None:
        """
        Initializes the log file.

        Args:
            file_name: The name of the file where transactions are logged.
                        Defaults to "data/transactions.log".
            time_zone: The time zone to be used for logging. If None, the
                        local time zone is used. Defaults to None.
        """

        print("Initializing log...")
        self.file_name: str = file_name
        self.time_zone: str | None = time_zone
        timestamp: float = time()
        if time_zone is not None:
            self.log(f"The time zone is set to '{time_zone}'.", timestamp)
        else:
            self.log("The time zone is set to the local time zone.", timestamp)
        print("Log initialized.")

    def create(self) -> None:
        """
        Creates the necessary directories and an empty log file.
        This method performs the following steps:
        1. Extracts the directory path from the file name.
        2. Splits the directory path and iterates through each directory.
        3. Checks if each directory exists, and if not, creates it.
        4. Creates an empty log file at the specified file name.
        """
        # Create missing directories
        directories: str = self.file_name[:self.file_name.rfind("/")]
        for _, directory in enumerate(directories.split("/")):
            if not exists(directory):
                makedirs(directory)

        # Create the log file
        with open(self.file_name, "w"):
            pass

    def log(self, line: str, timestamp: float) -> None:
        """
        Logs a line of text with a timestamp to a file.
        Args:
            line: The line of text to log.
            timestamp: The Unix timestamp that will be converted to a
                        human-readable format and prepended to the line.
        Returns:
            None
        """

        timestamp_friendly: str = format_timestamp(timestamp, self.time_zone)

        # Create the log file if it doesn't exist
        if not exists(self.file_name):
            self.create()

        with open(self.file_name, "a") as f:
            timestamped_line: str = f"{timestamp_friendly}: {line}"
            print(timestamped_line)
            f.write(f"{timestamped_line}\n")


# endregion

# region Bot config
class BotConfiguration:
    """
    A class to handle the bot configuration.

    Methods:
        __init__(file_name = "data/bot_configuration.json"): Initializes
            the bot configuration.
        create(): Creates the necessary directories and a default
            configuration file.
        read(): Reads the bot configuration from a file and overrides it
            with environment variables if they exist.
        """

    def __init__(self, file_name: str = "data/bot_configuration.json") -> None:
        """
        Initializes the bot configuration.

        Args:
            file_name: The path to the configuration file. Defaults
                        to "data/bot_configuration.json".

        Attributes:
            file_name: The path to the configuration file.
            configuration: The bot configuration read from the file.
            coin: The coin name from the configuration.
            Coin: The capitalized coin name from the configuration.
            coins: The plural form of the coin name from the configuration.
            Coins: The capitalized plural form of the coin name from
                the configuration.
            coin_emoji_id: The emoji ID for the coin from the configuration.
            administrator_id: The administrator ID from the configuration.
            casino_house_id: The casino house ID from the configuration.

        Warnings:
            If `coin_emoji_id` is 0, a warning is printed indicating
                that COIN_EMOJI_ID is not set.
            If `administrator_id` is 0, a warning is printed indicating
                that ADMINISTRATOR_ID is not set.
        """
        print("Initializing bot configuration...")
        # TODO Do not integers as string
        self.file_name: str = file_name
        self._default_config: BotConfig = {
            "coin": "coin",
            "Coin": "Coin",
            "coins": "coins",
            "Coins": "Coins",
            "coin_emoji_id": 0,
            "coin_emoji_name": "",
            "casino_house_id": 0,
            "administrator_id": 0,
            "casino_channel_id": 0,
            "blockchain_name": "blockchain",
            "Blockchain_name": "Blockchain",
            "grifter_swap_id": 0,
            "sbcoin_id": 0,
            "auto_approve_transfer_limit": 0,
            "aml_office_thread_id": 0
        }
        attributes_set = False
        while attributes_set is False:
            try:
                self.configuration: BotConfig = self.read()
                self.coin: str = self.configuration["coin"]
                self.Coin: str = self.configuration["Coin"]
                self.coins: str = self.configuration["coins"]
                self.Coins: str = self.configuration["Coins"]
                self.coin_emoji_id: int = (
                    self.configuration["coin_emoji_id"])
                self.coin_emoji_name: str = (
                    self.configuration["coin_emoji_name"])
                self.administrator_id: int = (
                    self.configuration["administrator_id"])
                self.casino_house_id: int = (
                    self.configuration["casino_house_id"])
                self.casino_channel_id: int = (
                    self.configuration["casino_channel_id"])
                self.blockchain_name: str = (
                    self.configuration["blockchain_name"])
                self.Blockchain_name: str = (
                    self.configuration["Blockchain_name"])
                self.grifter_swap_id: int = (
                    self.configuration["grifter_swap_id"])
                self.sbcoin_id: int = (
                    self.configuration["sbcoin_id"])
                self.auto_approve_transfer_limit: int = (
                    self.configuration["auto_approve_transfer_limit"])
                self.aml_office_thread_id: int = (
                    self.configuration["aml_office_thread_id"])
                attributes_set = True
            except KeyError as e:
                print(f"ERROR: Missing key in bot configuration: {e}\n"
                      "The bot configuration file will be replaced "
                      "with template values.")
                self.create()

        # Iterate this class' attributes
        attributes: Dict[str, Any] = self.__dict__
        for attribute in attributes:
            if not attribute in self._default_config:
                continue
            configured_value: str | int = attributes[attribute]
            default_value: str | int = cast(
                str | int, self._default_config[attribute])
            if (configured_value == default_value):
                print(f"WARNING: `{attribute}` has not been set "
                      f"in '{self.file_name}' "
                      "nor in the environment variables.")
        print(f"Bot configuration initialized.")

    def create(self) -> None:
        """
        Creates the necessary directories and a default configuration file.
        This method performs the following actions:
        1. Creates any missing directories specified in the file path.
        2. Creates a configuration file with default settings if it does not
            already exist.
        The default configuration includes:
        - coin: Default coin name in lowercase.
        - Coin: Default coin name with the first letter capitalized.
        - coins: Plural form of the default coin name in lowercase.
        - Coins: Plural form of the default coin name with the first
                    letter capitalized.
        - coin_emoji_id: Placeholder for the emoji ID of the coin.
        - casino_house_id: Placeholder for the ID of the casino house.
        - administrator_id: Placeholder for the ID of the bot administrator.
        Raises:
            OSError: If there is an error creating directories or writing
                        the configuration file.
        """
        # Create missing directories
        directories: str = self.file_name[:self.file_name.rfind("/")]
        for directory in directories.split("/"):
            if not exists(directory):
                makedirs(directory)

        # Create the configuration file
        # Default configuration
        configuration: BotConfig = self._default_config
        # Save the configuration to the file
        with open(self.file_name, "w") as file:
            file.write(json.dumps(configuration))

    def read(self) -> BotConfig:
        """
        Reads the bot configuration from a file and overrides it with
        environment variables if they exist.
        If the configuration file does not exist, it creates a new one.
        Returns:
            The bot configuration dictionary with possible overrides
                from environment variables.
        """
        if not exists(self.file_name):
            self.create()

        with open(self.file_name, "r") as file:
            configuration: BotConfig = json.loads(file.read())
            # Override the configuration with environment variables
            # TODO Add reels env vars
            # BUG: Environment variable names are be case-insensitive on Windows
            for config_key in configuration:
                env_value: str | None = os_environ.get(config_key)
                if env_value:
                    if isinstance(configuration[config_key], int):
                        configuration[config_key] = int(env_value)
                    else:
                        configuration[config_key] = env_value
                    print(f"NOTE: {config_key} overridden by "
                          f"environment variable to {env_value}.")
            return configuration


# endregion

class SlotMachine:
    """
    Represents a slot machine game with various functionalities, such as
    loading configuration, calculating probabilities, managing reels,
    calculating expected value, and handling jackpots.
    Methods:
        __init__(file_name = "data/slot_machine.json"):
            Initializes the SlotMachine class with the given configuration file.
        load_reels():
            Loads the reels configuration from the
            slot machine configuration file.
        reels():
            Returns the reel configuration.
        reels(value):
            Sets the reel configuration and updates the configuration file.
        probabilities():
            Runs the calculate_all_probabilities method and returns the
            calculated probabilities.
        jackpot():
            Returns the current jackpot amount.
        jackpot(value):
            Sets the jackpot amount and updates the configuration file.
        load_jackpot():
            Loads the current jackpot pool.
        create_config():
            Creates a template slot machine configuration file.
        load_config():
            Loads the slot machine configuration from a JSON file.
        save_config():
            Saves the current slot machine configuration to a file.
        calculate_reel_symbol_probability(reel, symbol):
            Calculate the probability of a specific symbol appearing on a
            given reel.
        calculate_event_probability(symbol):
            Calculate the overall probability of a given symbol appearing across
            all reels.
        calculate_losing_probabilities():
            Calculate the probability of losing the entire wager and the
            probability of not getting any symbols to match.
        calculate_all_probabilities():
            Calculate the probabilities for all possible outcomes in the
            slot machine.
        count_symbols(ree):
            Count the total number of symbols in the specified reel or in all
            reels if no reel is specified.
        calculate_expected_value(silent):
            Calculate the expected total return and expected return for the
            slot machine.
        calculate_average_jackpot(seed_int):
            Calculate the average jackpot amount on payout based on a given
            seed (start amount) integer.
        calculate_rtp(wager):
            Calculate the return to player (RTP) percentage for a given wager.
        stop_reel(reel):
            Stops the specified reel and returns the symbol at the
            stopping position.
        calculate_award_money(wager, results):
            Calculate the award money based on the wager and the results of
            the reels.
        make_friendly_event_name(event_name):
            Make a friendly event name from the event name.
        """
    # region Slot config

    def __init__(self, file_name: str = "data/slot_machine.json") -> None:
        """
        Initializes the SlotMachine class with the given configuration file.

        Args:
            file_name: The name of the slot machine configuration file. Defaults
                to "data/slot_machine.json".

        Attributes:
            file_name: The name of the slot machine configuration file
            configuration: The loaded configuration for the slot machine
            _reels: The loaded reels for the slot machine
            _probabilities: The calculated probabilities for each event
            _jackpot: The current jackpot amount
            _fees: The fees associated with the slot machine
        """
        print("Starting the slot machines...")
        self.file_name: str = file_name
        attributes_set = False
        while attributes_set is False:
            try:
                self.configuration: SlotMachineConfig = (
                    self.load_config())
                self._reels: Reels = self.load_reels()
                # self.emoji_ids: Dict[str, int] = (
                #     cast(Dict[str, int], self.configuration["emoji_ids"]))
                self._probabilities: Dict[str, Float] = (
                    self.calculate_all_probabilities())
                self._jackpot: int = self.load_jackpot()
                self._fees: dict[str, int | float] = self.configuration["fees"]
                self.header: str = f"### {Coin} Slot Machine"
                self.next_bonus_wait_seconds: int = (
                    self.configuration["new_bonus_wait_seconds"])
                attributes_set = True
            except KeyError as e:
                print(f"ERROR: Missing key in slot machine configuration: {e}\n"
                      "The slot machine configuration file will be replaced "
                      "with template values.")
                self.create_config()

        print("Slot machines started.")

    def load_reels(self) -> Reels:
        """
        Loads the reels configuration from the bot's configuration file.

        Returns:
            The reels configuration.
        """
        # print("Getting reels...")
        self.configuration = self.load_config()
        reels: Reels = self.configuration["reels"]
        return reels

    @property
    def reels(self) -> Reels:
        """
        Returns the current state of the reels.

        Returns:
            Reels: The current state of the reels.
        """
        return self._reels

    @reels.setter
    def reels(self, value: Reels) -> None:
        """
        Sets the reels value and updates the configuration.

        Args:
            value: The new value for the reels.
        """
        self._reels = value
        self.configuration["reels"] = self._reels
        self.save_config()

    @property
    def probabilities(self) -> Dict[str, Float]:
        """
        Calculate and return the probabilities for various outcomes.

        Returns:
            Dict: A dictionary where the keys are event names and the values
                    are their corresponding probabilities.
        """
        return self.calculate_all_probabilities()

    @property
    def jackpot(self) -> int:
        """
        Returns the current jackpot amount.

        Returns:
            int: The current jackpot amount.
        """
        return self._jackpot

    @jackpot.setter
    def jackpot(self, value: int) -> None:
        """
        Sets the jackpot value and updates the configuration.

        Args:
            value (int): The new jackpot value.
        """
        self._jackpot = value
        self.configuration["jackpot_pool"] = self._jackpot
        self.save_config()

    def load_jackpot(self) -> int:
        """
        Loads the current jackpot pool.

        This method retrieves the jackpot seed from the configuration file
        and compares it to the current jackpot pool. The jackpot pool is
        automatically set to the jackpot seed if the jackpot pool is lower.

        Returns:
            int: The calculated jackpot amount.
        """
        self.configuration = self.load_config()
        combo_events: Dict[str,
                           ReelSymbol] = self.configuration["combo_events"]
        jackpot_seed: int = combo_events["jackpot"]["fixed_amount"]
        jackpot_pool: int = self.configuration["jackpot_pool"]
        if jackpot_pool < jackpot_seed:
            jackpot: int = jackpot_seed
        else:
            jackpot: int = jackpot_pool
        return jackpot

    def create_config(self) -> None:
        """
        Creates a template slot machine configuration file.
        This method performs the following steps:
        1. Prints a message indicating the creation of the configuration file.
        2. Creates any missing directories in the file path.
        3. Defines a default configuration for the slot machine, including:
            - Combo events with their respective emoji names, IDs,
                fixed amount payouts, and wager multiplier payouts.
            - Reels with the number of each unique symbol on each reel.
            - Fees for different wager levels.
            - Current jackpot pool amount placeholder (not the seed).
        4. Saves the configuration to the specified file in JSON format.
        5. Prints a message indicating the completion of the configuration
            file creation.
        """
        print("Creating template slot machine configuration file...")
        # Create missing directories
        directories: str = self.file_name[:self.file_name.rfind("/")]
        makedirs(directories, exist_ok=True)

        # Create the configuration file
        # Default configuration
        # jackpot_pool will automatically be set to the jackpot event's
        # fixed_amount value if the latter is higher than the former
        configuration: SlotMachineConfig = {
            "combo_events": {
                "lose_wager": {
                    "emoji_name": "",
                    "emoji_id": 0,
                    "emoji_id": 0,
                    "fixed_amount": 0,
                    "wager_multiplier": -1.0
                },
                "small_win": {
                    "emoji_name": "",
                    "emoji_id": 0,
                    "emoji_id": 0,
                    "fixed_amount": 3,
                    "wager_multiplier": 1.0
                },
                "medium_win": {
                    "emoji_name": "",
                    "emoji_id": 0,
                    "fixed_amount": 0,
                    "wager_multiplier": 2.0
                },
                "high_win": {
                    "emoji_name": "",
                    "emoji_id": 0,
                    "fixed_amount": 0,
                    "wager_multiplier": 3.0
                },
                "jackpot": {
                    "emoji_name": "",
                    "emoji_id": 0,
                    "emoji_id": 0,
                    "fixed_amount": 100,
                    "wager_multiplier": 1.0
                }
            },
            "reels": {
                "reel1": {
                    "lose_wager": 2,
                    "small_win": 8,
                    "medium_win": 6,
                    "high_win": 3,
                    "jackpot": 1
                },
                "reel2": {
                    "lose_wager": 2,
                    "small_win": 8,
                    "medium_win": 6,
                    "high_win": 3,
                    "jackpot": 1
                },
                "reel3": {
                    "lose_wager": 2,
                    "small_win": 8,
                    "medium_win": 6,
                    "high_win": 3,
                    "jackpot": 1
                },
            },
            "reel_spin_emojis": {
                "spin1": {
                    "emoji_name": "slot_spin_1",
                    "emoji_id": 0
                },
                "spin2": {
                    "emoji_name": "slot_spin_1",
                    "emoji_id": 0
                },
                "spin3": {
                    "emoji_name": "slot_spin_1",
                    "emoji_id": 0
                }
            },
            "fees": {
                "low_wager_main": 1,
                "medium_wager_main": 0.19,
                "high_wager_main": 0.06,
                "low_wager_jackpot": 1,
                "medium_wager_jackpot": 0.01,
                "high_wager_jackpot": 0.01
            },
            "jackpot_pool": 101,
            "new_bonus_wait_seconds": 86400
        }
        # Save the configuration to the file
        with open(self.file_name, "w") as file:
            file.write(json.dumps(configuration))
        print("Template slot machine configuration file created.")

    def load_config(self) -> SlotMachineConfig:
        """
        Loads the slot machine configuration from a JSON file.
        If the configuration file does not exist, it creates a default
        configuration file.

        Returns:
            SlotMachineConfig: The loaded slot machine configuration.
        """
        if not exists(self.file_name):
            self.create_config()

        with open(self.file_name, "r") as file:
            configuration: SlotMachineConfig = json.loads(file.read())
            return configuration

    def save_config(self) -> None:
        """
        Saves the current slot machine configuration to a file.

        This method writes the current configuration stored in
        the `configuration` attribute to a file specified by
        the `file_name` attribute in JSON format.

        Raises:
            IOError: If the file cannot be opened or written to.
        """
        # print("Saving slot machine configuration...")
        with open(self.file_name, "w") as file:
            file.write(json.dumps(self.configuration))
        # print("Slot machine configuration saved.")
    # endregion

    # region Slot probability

    def calculate_reel_symbol_probability(self,
                                          reel: Literal[
                                              "reel1", "reel2", "reel3"],
                                          symbol: str) -> float:
        """
        Calculate the probability of a specific symbol appearing on a
        given reel.

        Args:
            reel: The reel to check for the symbol.
            symbol: The symbol to calculate the probability for.

        Returns:
            float: The probability of the symbol appearing on
                    the specified reel.
        """
        number_of_symbol_on_reel: int = self.reels[reel][symbol]
        total_reel_symbols: int = sum(self.reels[reel].values())
        if total_reel_symbols != 0 and number_of_symbol_on_reel != 0:
            probability_for_reel: float = (
                number_of_symbol_on_reel / total_reel_symbols)
        else:
            probability_for_reel = 0.0
        return probability_for_reel

    def calculate_event_probability(self, symbol: str) -> Float:
        """
        Calculate the overall probability of a given symbol appearing
        across all reels.

        Args:
            symbol: The symbol to calculate the probability for.
        Returns:
            Float: The overall probability of the symbol appearing across
                    all reels.
        """
        # TODO Ensure it's still working properly
        overall_probability: Float = Float(1.0)
        for r in self.reels:
            r = (
                cast(Literal['reel1', 'reel2', 'reel3'], r))
            probability_for_reel: float = (
                self.calculate_reel_symbol_probability(r, symbol))

            overall_probability = (
                cast(Float, Mul(overall_probability, probability_for_reel)))
        return overall_probability

    def calculate_losing_probabilities(self) -> tuple[Float, Float]:
        """
        Calculate the probabilities of losing the entire wager, and the
        probability of not getting any symbols to match (standard lose).

        Returns:
            tuple[Float, Float]: A tuple containing:
                - any_lose_probability (Float): The probability of losing by
                    either not getting any symbols to match or getting the
                    "lose_wager" symbol combo.
                - standard_lose_probability (Float): The probability of losing
                    by not getting any symbols to match.
        """
        # TODO Ensure it's still working properly
        # print("Calculating chance of losing...")

        # No symbols match
        standard_lose_probability: Float | Mul = Float(1.0)

        # Either lose_wager symbols match or no symbols match
        any_lose_probability: Float | Mul = Float(1.0)

        # Take the symbols from the first reel
        # (expecting all reels to have the same symbols)
        symbols: List[str] = [symbol for symbol in self.reels["reel1"]]
        symbols_no_match_probability: Float | Add
        symbols_match_probability: Float
        for symbol in symbols:
            symbols_match_probability = (
                self.calculate_event_probability(symbol))
            symbols_no_match_probability = (
                Add(Integer(1) - symbols_match_probability))
            standard_lose_probability = (
                Mul(standard_lose_probability, symbols_no_match_probability))
            if symbol != "lose_wager":
                any_lose_probability = (
                    Mul(any_lose_probability, symbols_no_match_probability))
        return (cast(Float, any_lose_probability),
                cast(Float, standard_lose_probability))

    def calculate_all_probabilities(self) -> Dict[str, Float]:
        """
        Calculate the probabilities for all possible outcomes in
        the slot machine.

        This method loads the reels, calculates the probability for each
        symbol on the first reel (presuming all reels will have the same unique
        symbols, whether in the same or different amounts), and then calculates
        the probabilities for losing and winning events.

        Returns:
            Dict: A dictionary where the keys are the event names
                    (i.e., symbol combos, "standard_lose", "any_lose", "win")
                    and the values are their respective probabilities.
        """
        # TODO Ensure it's still working correctly now after using TypedDicts
        self.reels = self.load_reels()
        probabilities: Dict[str, Float] = {}
        for symbol in self.reels["reel1"]:
            probability: Float = self.calculate_event_probability(symbol)
            probabilities[symbol] = probability
        any_lose_probability: Float
        standard_lose_probability: Float
        any_lose_probability, standard_lose_probability = (
            self.calculate_losing_probabilities())
        probabilities["standard_lose"] = standard_lose_probability
        probabilities["any_lose"] = any_lose_probability
        probabilities["win"] = cast(Float, Integer(1) - any_lose_probability)
        return probabilities
    # endregion

    # region Slot count
    def count_symbols(self, reel: str | None = None) -> int:
        """
        Count the total number of symbols in the specified reel or in all reels
        if no reel is specified.

        Args:
            reel: The name of the reel to count symbols from. 
                    If None, counts symbols from all reels. Otherwise it's
                    expected to be 'reel1', 'reel2', or 'reel3'.

        Returns:
            int: The total number of symbols in the specified reel or in
            all reels.
        """
        # TODO Ensure it's still working properly
        symbol_count: int
        all_symbols_lists: List[int] = []
        if reel is None:
            for r in self._reels:
                r = (
                    cast(Literal['reel1', 'reel2', 'reel3'], r))
                all_symbols_lists.append(sum(self._reels[r].values()))
            symbol_count = sum(all_symbols_lists)
        else:
            r = (
                cast(Literal['reel1', 'reel2', 'reel3'], reel))
            all_symbols_lists.append(sum(self._reels[r].values()))
        symbol_count = sum(all_symbols_lists)
        return symbol_count
    # endregion

    # region Slot EV
    def calculate_expected_value(self,
                                 silent: bool = False
                                 ) -> tuple[Piecewise, Piecewise]:
        """
        Calculate the expected total return and expected return for the slot
        machine.

        The player can only decide how many coins to insert into the machine
        each spin, and the fees are subtracted automatically from the player's
        total return (the amount of money they get back).

        Each spin, the player pays two fees (or four, if you count the
        fixed amount and multiplier fees separately), the main fee and the
        jackpot fee.
        If the player gets a combo that multiplies their wager, it multiplies
        their wager, not their wager minus the fees.
        The jackpot fee is money that goes directly to the jackpot pool.
        If a player's wager does not cover the jackpot fee, they get the
        "no jackpot" mode, where they are not eligible for the jackpot. In the
        event that they get the jackpot combo, they don't get the jackpot, it
        just counts as a standard lose (no combo).

        Different wager sizes have different fees,
        which makes the EV different for different wager sizes.
        Therefore, we express EV as a piecewise function.
        Each piece expresses the EV (ETR or ER) for a specific wager range

        Terms:
        - Expected value (EV): The average value of a random variable over
            many trials.
        - Wager (or stake): The amount of coins the player inserts into the
            machine each spin; a number that decides the fee and that the
            multiplier events are based on.
        - Jackpot: A prize that grows with each spin until someone wins it
        - Jackpot seed: The amount that the jackpot starts at (and gets reset
            to after someone wins the jackpot).
        - Total return (TR): The gross return amount that the player gets back
            (this in itself does not tell us if the player made a profit or
            loss).
        - Return (R): The net amount that the player gets back; the gain or loss
            part of the total return money; the total return minus the wager .
        - Expected total return (ETR): The average total return over many plays; 
            the expected value of the total return.
        - Expected return (ER): The average return (gain or loss) over many
            plays; the expected value of the return.
        - Piecewise function: A function that is defined by several subfunctions
            (used here to express ETR and ER with different fees for different
            wager ranges).

        Symbolic representation:
        - W: Wager
        - k: Wager multiplier
        - x: Fixed amount payout
        - f1k: Main fee wager multiplier
        - f1x: Main fee fixed amount
        - f2k: Jackpot fee wager multiplier
        - f2x: Jackpot fee fixed amount
        - j: Jackpot average

        Args:
        - silent: If True, the function will not print anything to the console.
        - standard_fee_fixed_amount: A fixed amount that is subtracted from the
            player's total return for each spin.
        - standard_fee_wager_multiplier: A percentage of the player's wager that
            is subtracted from the player's total return for each spin, and
            added to the jackpot pool.
        - jackpot_fee_fixed_amount: A fixed amount that is subtracted from the
            player's total return for each spin, and added to the jackpot pool.
        """

        def print_if_not_silent(*args: Any, **kwargs: Any) -> None:
            """
            Wrapper for print() that only prints if the "silent" parameter
            is False.
            """
            if not silent:
                print(*args, **kwargs)

        # Load configuration and calculate probabilities
        self.configuration = self.load_config()
        probabilities: Dict[str, Float] = self.calculate_all_probabilities()
        events: KeysView[str] = probabilities.keys()
        combo_events: Dict[str, ReelSymbol] = (
            self.configuration["combo_events"])

        # Symbol
        W: Expr = symbols('W')  # wager

        def calculate_piece_ev(
                standard_fee_fixed_amount: Integer = Integer(0),
                standard_fee_wager_multiplier: Float = Float(0.0),
                jackpot_fee_fixed_amount: Integer = Integer(0),
                jackpot_fee_wager_multiplier: Float = Float(0.0)
        ) -> tuple[Add, Add]:
            """
            Calculate the *expected total return* and *expected return*
            with the fees specified with the parameters.

            Args:
                - standard_fee_fixed_amount: The fixed amount of the
                    standard fee.
                - standard_fee_wager_multiplier: The multiplier for the
                     standard fee based on the wager.
                - jackpot_fee_fixed_amount: The fixed amount of the jackpot fee.
                - jackpot_fee_wager_multiplier: The multiplier for the
                    jackpot fee based on the wager.

                Returns:
                - tuple: A tuple containing the expected total return and
                            the expected return.
            """
            # Initialize variables
            piece_expected_return: Integer | Add = (
                Integer(0))
            piece_expected_total_return: Integer | Add = (
                Integer(0))
            piece_expected_total_return_contribution: Integer | Mul = (
                Integer(0))
            piece_expected_return_contribution: Integer | Mul = (
                Integer(0))
            p_event_float: Float
            fixed_amount_int: int = 0
            fixed_amount: Expr = Integer(fixed_amount_int)
            wager_multiplier_float: float
            wager_multiplier: Expr

            # Mark the start
            print_if_not_silent("--------------------------------")

            # Print the fees
            print_if_not_silent(f"standard_fee_fixed_amount: "
                                f"{standard_fee_fixed_amount}")
            print_if_not_silent(f"standard_fee_wager_multiplier: "
                                f"{standard_fee_wager_multiplier}")
            print_if_not_silent(f"jackpot_fee_fixed_amount: "
                                f"{jackpot_fee_fixed_amount}")
            print_if_not_silent(f"jackpot_fee_wager_multiplier: "
                                f"{jackpot_fee_wager_multiplier}")

            # Determine if it's "no jackpot" mode (jackpot fee not paid)
            no_jackpot_mode: bool = False
            if (Eq(jackpot_fee_fixed_amount, Integer(0)) and
                    Eq(jackpot_fee_wager_multiplier, Float(0.0))):
                no_jackpot_mode = True
                print_if_not_silent(f"no_jackpot_mode: {no_jackpot_mode}")

            for event in events:
                if event in ("any_lose", "win"):
                    continue
                print_if_not_silent(f"----\nEVENT: {event}")
                # Get the probability of this event
                p_event_float: Float = probabilities[event]
                p_event = Float(p_event_float)
                print_if_not_silent(f"Event probability: {p_event_float}")
                if p_event_float == 0.0:
                    continue
                if event == "jackpot" and not no_jackpot_mode:
                    # If the player pays the coin jackpot fee
                    # and wins the jackpot,
                    # he ends up with his wager minus the standard fee minus the
                    # jackpot fee, plus the jackpot
                    #
                    # Variables
                    fixed_amount_int = combo_events[event]["fixed_amount"]
                    jackpot_seed: int = fixed_amount_int
                    print_if_not_silent(f"Jackpot seed: {jackpot_seed}")
                    jackpot_average: Rational = (
                        self.calculate_average_jackpot(
                            seed_int=jackpot_seed))
                    # TODO Add parameter to return RTP with jackpot excluded
                    # jackpot_average: float = 0.0
                    print_if_not_silent(f"Jackpot average: {jackpot_average}")
                    # I expect wager multiplier to be 1.0 for the jackpot,
                    # but let's include it in the calculation anyway,
                    # in case someone wants to use a different value
                    wager_multiplier_float = (
                        combo_events[event]["wager_multiplier"])
                    wager_multiplier = Float(wager_multiplier_float)

                    # Calculations
                    event_total_return = Add(
                        Mul(W, wager_multiplier),
                        jackpot_average,
                        -Mul(W, standard_fee_wager_multiplier),
                        -Mul(W, jackpot_fee_wager_multiplier),
                        -standard_fee_fixed_amount,
                        -jackpot_fee_fixed_amount)
                    print_if_not_silent(f"Event total return: "
                                        f"{event_total_return} "
                                        "["
                                        "(W * k) + j "
                                        "- (W * f1k) - (W * f2k) "
                                        "- f1x - f2x"
                                        "]")
                    event_return = Add(
                        event_total_return,
                        -W)
                    # This event's contributions to the *expected total return*
                    piece_expected_total_return_contribution = (
                        Mul(p_event, event_total_return))
                    message_content: str
                    message_content = (
                        "Expected total return contribution: "
                        f"{piece_expected_total_return_contribution}")
                    print_if_not_silent(message_content)
                    # Remove variables with common names to
                    # prevent accidental use
                    del message_content
                    # This event's contribution to the *expected return*
                    piece_expected_return_contribution = (
                        Mul(p_event, event_return))
                    print_if_not_silent(f"Event return: "
                                        f"{event_return} "
                                        "[total return - W]")
                    # Add the contributions to the totals
                    piece_expected_total_return = Add(
                        piece_expected_total_return,
                        piece_expected_total_return_contribution)
                    piece_expected_return = Add(
                        piece_expected_return,
                        piece_expected_return_contribution)
                    continue
                elif ((event == "standard_lose") or
                      (event == "jackpot" and no_jackpot_mode)):
                    # If the player doesn't pay the jackpot fee and
                    # loses or gets the jackpot combo
                    # he ends up with his wager minus the standard fee
                    wager_multiplier_float = 1.0
                    fixed_amount_int = 0
                else:
                    # "else" includes all remaining win events
                    # plus the lose_wager event
                    #
                    # Variables
                    fixed_amount_int = combo_events[event]["fixed_amount"]
                    wager_multiplier_float = (
                        combo_events[event]["wager_multiplier"])
                wager_multiplier = Float(wager_multiplier_float)
                print_if_not_silent(
                    f"Multiplier (k): {wager_multiplier_float}")
                fixed_amount = Integer(fixed_amount_int)
                print_if_not_silent(f"Fixed amount (x): {fixed_amount_int}")

                # Calculations
                event_total_return = Add(
                    Mul(W, wager_multiplier),
                    fixed_amount,
                    -Mul(W, standard_fee_wager_multiplier),
                    -Mul(W, jackpot_fee_wager_multiplier),
                    -standard_fee_fixed_amount,
                    -jackpot_fee_fixed_amount)
                print_if_not_silent(f"Event total return: "
                                    f"{event_total_return} "
                                    "["
                                    "(W * k) + x "
                                    "- (W * f1k) - (W * f2k) "
                                    "- f1x - f2x"
                                    "]")
                event_return = Add(event_total_return, -W)
                print_if_not_silent(f"Event return: "
                                    f"{event_return} "
                                    "[total return - W]")
                piece_expected_total_return_contribution = (
                    Mul(p_event, event_total_return))
                message_content = ("Expected total return contribution: "
                                   f"{piece_expected_total_return_contribution}")
                print_if_not_silent(message_content)
                del message_content
                piece_expected_return_contribution = (
                    Mul(p_event, event_return))
                print_if_not_silent("Expected return contribution: "
                                    f"{piece_expected_return_contribution}")
                # Add the event's contributions to the final expected returns
                piece_expected_total_return = Add(
                    piece_expected_total_return,
                    piece_expected_total_return_contribution)
                piece_expected_return = Add(
                    piece_expected_return,
                    piece_expected_return_contribution)
            return (
                cast(Add, piece_expected_total_return),
                cast(Add, piece_expected_return))

        # BUG The rounding to nearest integer (for the fees esp.) is not accounted for

        # Fees
        # Refresh config
        self.configuration = self.load_config()
        # Main fee
        low_wager_main_fee: Integer = Integer(self._fees["low_wager_main"])
        medium_wager_main_fee: Float = Float(self._fees["medium_wager_main"])
        high_wager_main_fee: Float = Float(self._fees["high_wager_main"])
        # Jackpot fee
        low_wager_jackpot_fee: Integer = Integer(
            self._fees["low_wager_jackpot"])
        medium_wager_jackpot_fee: Float = Float(
            self._fees["medium_wager_jackpot"])
        high_wager_jackpot_fee: Float = Float(
            self._fees["high_wager_jackpot"])

        # TODO Send expected return for different wager sizes with /reels
        # Calculate expected total return and expected return
        # with different fees
        pieces: Dict[str, tuple[Add, Add]] = {
            "no_jackpot": calculate_piece_ev(
                standard_fee_fixed_amount=low_wager_main_fee),
            "low_wager": calculate_piece_ev(
                standard_fee_fixed_amount=low_wager_main_fee,
                jackpot_fee_fixed_amount=low_wager_jackpot_fee),
            "medium_wager": calculate_piece_ev(
                standard_fee_wager_multiplier=medium_wager_main_fee,
                jackpot_fee_wager_multiplier=medium_wager_jackpot_fee),
            "high_wager": calculate_piece_ev(
                standard_fee_wager_multiplier=high_wager_main_fee,
                jackpot_fee_wager_multiplier=high_wager_jackpot_fee)
        }

        # Remember to also change the help message if you change the conditions
        expected_total_return = Piecewise(
            (pieces["no_jackpot"][0], Eq(W, Integer(1))),
            (pieces["low_wager"][0], Lt(W, Integer(10))),
            (pieces["medium_wager"][0], Lt(W, Integer(100))),
            (pieces["high_wager"][0], Ge(W, Integer(100))))

        expected_return = Piecewise(
            (pieces["no_jackpot"][1], Eq(W, Integer(1))),
            (pieces["low_wager"][1], Lt(W, Integer(10))),
            (pieces["medium_wager"][1], Lt(W, Integer(100))),
            (pieces["high_wager"][1], Ge(W, Integer(100))))

        print_if_not_silent(f"Expected total return:")
        print_if_not_silent(expected_total_return)
        print_if_not_silent(f"Expected return:")
        print_if_not_silent(expected_return)

        return (expected_total_return, expected_return)
    # endregion

    # region Slot avg jackpot
    def calculate_average_jackpot(self, seed_int: int) -> Rational:
        """
        Calculate the average jackpot amount on payout
        based on a given seed (start amount) integer.

        Args:
        seed_int -- The starting amount of the jackpot pool
        """
        seed: Integer = Integer(seed_int)
        # 1 coin is added to the jackpot for every spin
        contribution_per_spin: Integer = Integer(1)
        jackpot_probability: Float = (
            self.calculate_all_probabilities()["jackpot"])
        average_spins_to_win = Rational(Integer(1), jackpot_probability)
        jackpot_cycle_growth = (
            Mul(contribution_per_spin, average_spins_to_win))
        # min + max / 2
        mean_jackpot = Rational(Add(Integer(0) + jackpot_cycle_growth))
        # (0 + jackpot_cycle_growth) / 2
        average_jackpot: Rational = cast(Rational, Add(seed, mean_jackpot))
        return average_jackpot
    # endregion

    # region Slot RTP
    def calculate_rtp(self, wager: Integer) -> Float:
        """
        Calculate the Return to Player (RTP) based on the given wager.

        Args:
            wager: The amount wagered.

        Returns:
            Float: The RTP value as a decimal.
        """
        # IMPROVE Fix error reported by Pylance
        expected_total_return_expression: Piecewise = (
            self.calculate_expected_value(silent=True))[0]
        expected_total_return: Piecewise = (
            cast(Piecewise,
                 expected_total_return_expression.subs(symbols('W'), wager)))
        print(f"Expected total return (W = {wager}): {expected_total_return}")
        rtp = Rational(expected_total_return, wager)
        rtp_decimal: Float = cast(Float, rtp.evalf())
        print(f"RTP: {rtp}")
        print(f"RTP decimal: {rtp_decimal}")
        return rtp_decimal
    # endregion

    # region Slot stop reel
    def stop_reel(self, reel: Literal["reel1", "reel2", "reel3"]) -> str:
        """
        Stops the specified reel and returns the symbol at the
        stopping position.

        Args:
            reel: The reel to stop.

        Returns:
            str: The symbol at the stopping position.
        """
        # Create a list with all units of each symbol type on the reel
        reel_symbols: List[str] = []
        for s in self.reels[reel]:
            reel_symbols.extend([s] * self.reels[reel][s])
        # Randomly select a symbol from the list
        symbol: str = random.choice(reel_symbols)
        return symbol
    # endregion

    # region Slot win money
    def calculate_award_money(self,
                              wager: int,
                              results: ReelResults
                              ) -> tuple[str, str, int]:
        """
        Calculate the award money based on the wager and the results of
        the reels. This does not include the fees. It is only the money
        that a combo event would award the player. It will not return a negative
        value.
        It also returns the internal name of the event and a user-friendly name
        of the event.
        Args:
            wager: The amount of money wagered.
            results: The results of the reels, containing associated
            combo events.
        Returns:
            tuple: A tuple containing:
                - event_name: The internal name of the event.
                - event_name_friendly: A user-friendly name of the event.
                - win_money_rounded: The amount of money won, rounded down to
                    the nearest integer.
        """
        if (not (
            results["reel1"]["associated_combo_event"].keys()
            == results["reel2"]["associated_combo_event"].keys()
                == results["reel3"]["associated_combo_event"].keys())):
            return ("standard_lose", "No win", 0)

        # IMPROVE Code is repeated from slots() function
        fees_dict: Dict[str, int | float] = slot_machine.configuration["fees"]
        low_wager_main_fee: int = (
            cast(int, fees_dict["low_wager_main"]))
        low_wager_jackpot_fee: int = (
            cast(int, fees_dict["low_wager_jackpot"]))
        jackpot_fee_paid: bool = (
            wager >= (low_wager_jackpot_fee + low_wager_main_fee))
        no_jackpot_mode: bool = False if jackpot_fee_paid else True
        # Since associated_combo_event is a dict with only one key,
        # we can get the key name (thus event name) by getting the first key
        event_name: str = next(
            iter(results["reel1"]["associated_combo_event"]))
        # print(f"event_name: {event_name}")
        wager_multiplier: float = (
            results["reel1"]["associated_combo_event"][event_name]
            ["wager_multiplier"])
        fixed_amount_payout: int = (
            results["reel1"]["associated_combo_event"][event_name]
            ["fixed_amount"])
        # print(f"event_multiplier: {wager_multiplier}")
        # print(f"fixed_amount_payout: {fixed_amount_payout}")
        event_name_friendly: str = ""
        win_money: float = 0.0
        win_money_rounded: int = 0
        if event_name == "lose_wager":
            event_name_friendly = "Lose wager"
            return (event_name, event_name_friendly, 0)
        elif event_name == "jackpot":
            if no_jackpot_mode:
                event_name = "jackpot_fail"
                event_name_friendly = "No Jackpot"
                win_money_rounded = 0
            else:
                event_name_friendly = "JACKPOT"
                win_money_rounded = self.jackpot
            return (event_name, event_name_friendly, win_money_rounded)
        win_money = (
            (wager * wager_multiplier) + fixed_amount_payout) - wager
        win_money_rounded: int = math.floor(win_money)
        # Get rid of ".0"
        event_multiplier_friendly: str
        event_multiplier_floored: int = math.floor(wager_multiplier)
        if wager_multiplier == event_multiplier_floored:
            event_multiplier_friendly = str(int(wager_multiplier))
        else:
            event_multiplier_friendly = str(wager_multiplier)
        event_name_friendly += "{}X".format(event_multiplier_friendly)
        if fixed_amount_payout > 0:
            event_name_friendly = "+{}".format(fixed_amount_payout)
        return (event_name, event_name_friendly, win_money_rounded)
    # endregion

    # region Friendly event name
    def make_friendly_event_name(self, event_name: str) -> str:
        """
        Creates a user-friendly name for an event.

        The function handles specific event names such as "lose_wager"
        and "jackpot" with predefined friendly names. For other events, it
        constructs a friendly name based on the wager multiplier
        and fixed amount payout from the configuration.

        This code is copied from calculate_award_money().

        Args:
            event_name: The internal name of the event.

        Returns:
            str: A user-friendly version of the event name.
        """
        combo_events: Dict[str,
                           ReelSymbol] = self.configuration["combo_events"]
        wager_multiplier: float = (
            combo_events[event_name]["wager_multiplier"])
        fixed_amount_payout: int = (
            combo_events[event_name]["fixed_amount"])
        event_name_friendly: str = ""
        if event_name == "lose_wager":
            event_name_friendly = "Lose wager"
            return event_name_friendly
        elif event_name == "jackpot":
            event_name_friendly = "JACKPOT"
            return event_name_friendly
        event_multiplier_friendly: str
        event_multiplier_floored: int = math.floor(wager_multiplier)
        if wager_multiplier == event_multiplier_floored:
            event_multiplier_friendly = str(int(wager_multiplier))
        else:
            event_multiplier_friendly = str(wager_multiplier)
        event_name_friendly += "{}X".format(event_multiplier_friendly)
        if fixed_amount_payout > 0:
            event_name_friendly = "+{}".format(fixed_amount_payout)
        return event_name_friendly
    # endregion

    # region Slot message
    def make_message(self,
                     text_row_1: str | None = None,
                     text_row_2: str | None = None,
                     reels_row: str | None = None) -> str:
        """
        Constructs a message that imitates a slot machine.

        Args:
            text_row_1: The text for the first row.
            text_row_2: The text for the second row.
            reels_row: The text for the reels row.

        Returns:
            str: The formatted message string.
        """
        # Workaround for Discord stripping trailing whitespaces
        empty_space: LiteralString = "\N{HANGUL FILLER}" * 11
        if text_row_1 is None:
            text_row_1 = empty_space
        if text_row_2 is None and reels_row is not None:
            text_row_2 = empty_space

        if reels_row:
            message_content: str = (f"{self.header}\n"
                                    f"{text_row_1}\n"
                                    f"{text_row_2}\n"
                                    f"{empty_space}\n"
                                    f"{reels_row}\n"
                                    f"{empty_space}")
        else:
            if text_row_2 is None:
                message_content = (f"{self.header}\n"
                                   f"{text_row_1}")
            else:
                message_content = (f"{self.header}\n"
                                   f"{text_row_1}\n"
                                   f"{text_row_2}")
        return message_content
    # endregion

# region UserSaveData


class UserSaveData:
    """
    Handles the creation, saving, and loading of user-specific data
    in JSON format.

    ### About `starting_bonus_available` and `when_last_bonus_received`

    The property `starting_bonus_available` can be a unix timestamp that
    signifies when a new bonus will be given out if the command is run, no
    matter what their balance is at that point. It will only become a timestamp
    when the users` account is depleted, effectively starting a timer.

    If it was the case that `starting_bonus_available` was set to a new time
    immediately upon receiving a bonus, then it would become an always recurring
    event, not triggered by the user running out of coins. Therefore, it gets
    set to False after the user has received a bonus.

    Because `starting_bonus_available` is not always a timestamp, we need
    another property - `when_last_bonus_received` - to keep track of when the
    user last received a bonus. This way, we can make sure that the user does
    not receive a bonus too often.

    In short:
    `starting_bonus_available` means: if the user should receive a
    bonus, *or* a point in time when a bonus will be given to them, no matter
    what their balance is at that moment. `when_last_bonus_received` means: the
    point in time when the user last received a bonus.


    Methods:
        __init__(user_id, user_name):
            Initializes the UserSaveData instance with the given user ID
            and name.
        create():
            Creates the necessary directories and files for the user.
        save(key, value):
            Saves a key-value pair to a JSON file. If the file does not exist,
            it creates a new one.
        load(key):
            Loads the value associated with the given key from a JSON file.
            Returns the value associated with the key if it exists,
            otherwise None.
    """

    def __init__(self, user_id: int, user_name: str | None = None) -> None:
        # print("Initializing save data...")
        self.user_id: int = user_id
        self.file_name: str = f"data/save_data/{user_id}/save_data.json"
        self._starting_bonus_available: bool | float
        self._has_visited_casino: bool
        self._reaction_message_received: bool
        self._when_last_bonus_received: float | None
        self._mining_messages_enabled: bool
        self._blocked_from_receiving_coins: bool
        self._blocked_from_receiving_coins_reason: str | None
        self._user_name: str
        file_exists: bool = exists(self.file_name)
        file_empty: bool | None = None
        file_size: int
        if file_exists:
            file_size = os.stat(self.file_name).st_size
            file_empty = file_size == 0
        if file_empty:
            print(f"ERROR: Save data file for {self.user_id} is empty.")
        if (not file_exists or file_empty) and (user_name is None):
            raise ValueError("user_name must be provided if save data "
                             "does not exist for the user.")
        elif (not file_exists or file_empty) and (user_name is not None):
            self._user_name: str = user_name
            self._has_visited_casino = False
            self._starting_bonus_available = True
            self._when_last_bonus_received = None
            self._reaction_message_received = False
            self._mining_messages_enabled = True
            self._blocked_from_receiving_coins = False
            self._blocked_from_receiving_coins_reason = None
            self.create()
        elif (file_exists) and (not file_empty) and (user_name is None):
            self.user_name: str = self._load_value(
                key="user_name",
                expected_type=str, default="")
            self._load_all_properties()
        else:
            self._load_all_properties()
        # print("Save data initialized.")

    def _load_all_properties(self) -> None:
        """
        Load all properties from the disk.
        """
        self._has_visited_casino = self._load_value(
            key="has_visited_casino",
            expected_type=bool, default=False)
        self._starting_bonus_available = self._load_value(
            key="starting_bonus_available",
            expected_type=(bool, float), default=True)
        self._when_last_bonus_received = self._load_value(
            key="when_last_bonus_received",
            expected_type=(float, type(None)), default=None)
        self._reaction_message_received = self._load_value(
            key="reaction_message_received",
            expected_type=bool, default=False)
        self._mining_messages_enabled = self._load_value(
            key="mining_messages_enabled",
            expected_type=bool, default=True)
        self._blocked_from_receiving_coins = self._load_value(
            key="blocked_from_receiving_coins",
            expected_type=bool, default=False)
        self._blocked_from_receiving_coins_reason = self._load_value(
            key="blocked_from_receiving_coins_reason",
            expected_type=(str, type(None)), default=None)

    def _load_value(self,
                    key: str,
                    expected_type: type[T] | tuple[type, ...],
                    default: T) -> T:
        """
        Load a value from the disk.
        """

        value: str | List[int] | bool | float | None = self.load(key)
        if isinstance(value, expected_type):
            return cast(T, value)
        else:
            found_type = type(value)
            found_type_name: str = found_type.__name__
            if isinstance(expected_type, tuple):
                expected_type_name: str = (
                    ', '.join(t.__name__ for t in expected_type))
            else:
                expected_type_name: str = expected_type.__name__
            print(f"ERROR: Value of '{key}' ('{value}') does not match "
                  f"the expected type. Found '{found_type_name}', expected "
                  f"'{expected_type_name}'. "
                  f"Setting to default value {default}.")
            return default

    @property
    def has_visited_casino(self) -> bool:
        """
        Indicates if the user has visited the casino.
        """
        return self._has_visited_casino

    @has_visited_casino.setter
    def has_visited_casino(self, value: bool) -> None:
        """
        Sets the status of the user's visit to the casino.
        """
        self._has_visited_casino = value
        self.save("has_visited_casino", value)

    @property
    def starting_bonus_available(self) -> bool | float:
        """
        Indicates if they can receive a starting bonus.
        """
        return self._starting_bonus_available

    @starting_bonus_available.setter
    def starting_bonus_available(self, value: bool | float) -> None:
        """
        Sets the status of the starting bonus received.
        """
        self._starting_bonus_available = value
        self.save("starting_bonus_available", value)

    @property
    def when_last_bonus_received(self) -> float | None:
        """
        Indicates when the user last received a bonus.
        """
        return self._when_last_bonus_received

    @when_last_bonus_received.setter
    def when_last_bonus_received(self, value: float) -> None:
        """
        Sets the timestamp of the last bonus received.
        """
        self._when_last_bonus_received = value
        self.save("when_last_bonus_received", value)

    @property
    def reaction_message_received(self) -> bool:
        """
        Indicates if the user has received the reaction message.
        """
        return self._reaction_message_received

    @reaction_message_received.setter
    def reaction_message_received(self, value: bool) -> None:
        """
        Sets the status of the user receiving the reaction message.
        """
        self._reaction_message_received = value
        self.save("reaction_message_received", value)

    @property
    def mining_messages_enabled(self) -> bool:
        """
        Indicates if the user has enabled mining messages.
        """
        return self._mining_messages_enabled

    @mining_messages_enabled.setter
    def mining_messages_enabled(self, value: bool) -> None:
        """
        Sets the user's preference for mining messages.
        """
        self._mining_messages_enabled = value
        self.save("mining_messages_enabled", value)

    @property
    def blocked_from_receiving_coins(self) -> bool:
        """
        Indicates if the user is blocked from receiving coins.
        """
        return self._blocked_from_receiving_coins

    @blocked_from_receiving_coins.setter
    def blocked_from_receiving_coins(self, value: bool) -> None:
        """
        Sets the status of the user being blocked from receiving coins.
        """
        self._blocked_from_receiving_coins = value
        self.save("blocked_from_receiving_coins", value)

    @property
    def blocked_from_receiving_coins_reason(self) -> str | None:
        """
        Indicates the reason the user is blocked from receiving coins.
        """
        return self._blocked_from_receiving_coins_reason

    @blocked_from_receiving_coins_reason.setter
    def blocked_from_receiving_coins_reason(self, value: str | None) -> None:
        """
        Sets the reason the user is blocked from receiving coins.
        """
        self._blocked_from_receiving_coins_reason = value
        self.save("blocked_from_receiving_coins_reason", value)

    def create(self) -> None:
        """
        Creates the necessary directories and files for the user.
        This method performs the following actions:
        1. Creates any missing directories based on the file path.
        2. If a directory name matches the user ID, it creates a JSON file 
           containing the user's name, user ID, and starting bonus status.
        3. Creates an empty save data file specified by `self.file_name`.
        Attributes:
            self.file_name: The path to the save data file.
            self.user_name: The name of the user.
            self.user_id: The ID of the user.
            self._starting_bonus_available: Indicates if the user can receive
            free coins.
        """
        # Create missing directories and create save data file
        directories: str = self.file_name[:self.file_name.rfind("/")]
        for i, directory in enumerate(directories.split("/")):
            path: str = "/".join(directories.split("/")[:i+1])
            if not exists(directory):
                makedirs(path, exist_ok=True)
            if directory.isdigit() and int(directory) == self.user_id:
                with open(self.file_name, "w") as file:
                    file_contents: SaveData = {
                        "user_name": self._user_name,
                        "user_id": self.user_id,
                        "has_visited_casino": False,
                        "starting_bonus_available": (
                            self._starting_bonus_available),
                        "when_last_bonus_received": None,
                        "messages_mined": [],
                        "reaction_message_received": False,
                        "mining_messages_enabled": True,
                        "blocked_from_receiving_coins": False,
                        "blocked_from_receiving_coins_reason": None
                    }
                    file_contents_json: str = json.dumps(file_contents)
                    file.write(file_contents_json)

    def save(self, key: str, value: str | List[int] | float | None) -> None:
        """
        Saves a key-value pair to a JSON file. If the file does not exist,
        it creates a new one.

        Args:
            key: The key to be saved.
            value: The value to be saved.
        """

        # Read the existing data
        save_data: SaveData
        with open(self.file_name, "r") as file:
            save_data = json.load(file)
        # Update the data with the new key-value pair
        save_data[key] = value

        # Write the updated data back to the file
        with open(self.file_name, "w") as file:
            json.dump(save_data, file)

    def load(self, key: str) -> str | List[int] | bool | float | None:
        """
        Loads the value associated with the given key from a JSON file.
        Args:
            key: The key whose value needs to be retrieved.
        Returns:
            str | None: The value associated with the key if it exists,
                            otherwise None.
        """
        if not exists(self.file_name):
            return None
        all_data: SaveData
        with open(self.file_name, "r") as file:
            all_data = json.load(file)
        requested_value: str | List[int] | None = all_data.get(key)
        if ((isinstance(requested_value, str)) and
                (requested_value.lower() == "true")):
            return True
        elif (
            (isinstance(requested_value, str)) and
                (requested_value.lower() == "false")):
            return False
        else:
            return requested_value
# endregion

# region Decrypted tx


class DecryptedTransactionsSpreadsheet:
    """
    Decrypts the transactions spreadsheet.
    """

    def __init__(self, time_zone: str | None = None) -> None:
        project_root: Path = get_project_root()
        decrypted_spreadsheet_full_path: Path = (
            project_root / "data" / "transactions_decrypted.tsv")
        self.decrypted_spreadsheet_path: Path = (
            decrypted_spreadsheet_full_path.relative_to(project_root))
        encrypted_spreadsheet_full_path: Path = (
            project_root / "data" / "transactions.tsv")
        self.encrypted_spreadsheet_path: Path = (
            encrypted_spreadsheet_full_path.relative_to(project_root))
        save_data_dir_full_path: Path = (
            project_root / "data" / "save_data")
        self.save_data_dir_path: Path = (
            save_data_dir_full_path.relative_to(project_root))
        self.time_zone: str | None = time_zone

    def decrypt(self,
                user_id: int | None = None,
                user_name: str | None = None) -> None:
        """
        Decrypts the transactions spreadsheet.
        """
        if not exists(self.encrypted_spreadsheet_path):
            print("Encrypted transactions spreadsheet not found.")
            return None
        if not exists(self.save_data_dir_path):
            print("Save data directory not found.")
            return None

        print("Decrypting transactions spreadsheet...")
        user_names: Dict[str, str] = {}
        for subdir, _, _ in os.walk(self.save_data_dir_path):
            try:
                subdir_user_id: int = int(basename(subdir))
                subdir_save_data = UserSaveData(subdir_user_id)
                subdir_user_name: str = subdir_save_data.user_name
                subdir_user_id_hashed: str = (
                    sha256(str(subdir_user_id).encode()).hexdigest())
                user_names[subdir_user_id_hashed] = subdir_user_name
            except Exception as e:
                print(f"ERROR: Error getting save data: {e}")
                continue

        # Load the data from the file
        transactions: pd.DataFrame = pd.read_csv(  # type: ignore
            self.encrypted_spreadsheet_path, sep="\t")

        # IMPROVE if user_id and user_name
        # Only keep transactions that involve the specified user as
        # identified by the ID or name

        if user_id:
            # Only keep transactions that involve the specified user
            user_id_hashed: str = sha256(str(user_id).encode()).hexdigest()
            transactions = transactions[
                (transactions["Sender"] == user_id_hashed) |
                (transactions["Receiver"] == user_id_hashed)]

        # Replace hashed user IDs with user names
        transactions["Sender"] = (
            transactions["Sender"].map(user_names))  # type: ignore
        transactions["Receiver"] = (
            transactions["Receiver"].map(user_names))  # type: ignore
        # Replace unix timestamps
        transactions["Time"] = (
            transactions["Time"].map(format_timestamp))  # type: ignore

        if user_name:
            # Only keep transactions that involve the specified user
            transactions = transactions[
                (transactions["Sender"] == user_name) |
                (transactions["Receiver"] == user_name)]

        # Save the decrypted transactions to a new file
        transactions.to_csv(
            self.decrypted_spreadsheet_path, sep="\t", index=False)

        print("Decrypted transactions spreadsheet saved to file.")
# endregion

# region Bonus die button


class StartingBonusView(View):
    """
    A view for handling the starting bonus die roll interaction for the Casino.
    This view presents a button to the user, allowing them to roll a die to
    receive a starting bonus.
    The view ensures that only the user who invoked the interaction can roll
    the die.

    Methods:
        on_button_click(interaction):
            Handles the event when a button is clicked.
        on_timeout:
            Handles the timeout event for the view. Disables the die button and
            sends a message to the user indicating that they took too long and
            can run the command again when ready.
        """

    def __init__(self,
                 invoker: User | Member,
                 starting_bonus_awards: Dict[int, int],
                 save_data: UserSaveData,
                 log: Log,
                 interaction: Interaction) -> None:
        """
        Initializes the StartingBonusView instance, used for the starting bonus
        die button.

        Args:
            invoker: The user or member who invoked the bot.
            starting_bonus_awards: A dictionary containing
                        the starting bonus awards.
            save_data: The save data for the user.
            log: The log object for logging information.
            interaction: The interaction object.

        Attributes:
            invoker: The user or member who invoked the bot.
            invoker_id: The ID of the invoker.
            starting_bonus_awards: A dictionary containing
                the starting bonus awards.
            save_data: The save data for the user.
            log: The log object for logging information.
            interaction: The interaction object.
            button_clicked: A flag indicating whether the button has
                been clicked.
            die_button: The button for starting the bonus die.
        """
        super().__init__(timeout=starting_bonus_timeout)
        self.invoker: User | Member = invoker
        self.invoker_id: int = invoker.id
        self.starting_bonus_awards: Dict[int, int] = starting_bonus_awards
        self.save_data: UserSaveData = save_data
        self.log: Log = log
        self.interaction: Interaction = interaction
        self.button_clicked: bool = False
        self.die_button: Button[View] = Button(
            disabled=False,
            emoji="🎲",
            custom_id="starting_bonus_die")
        self.die_button.callback = self.on_button_click
        self.add_item(self.die_button)

    async def on_button_click(self, interaction: Interaction) -> None:
        """
        Handles the event when a button is clicked.
        This method checks if the user who clicked the button is the same user
        who invoked the interaction.
        If not, it sends an ephemeral message indicating that the user cannot
        roll the die for someone else.
        If the user is the invoker, it disables the button, rolls a die, awards
        a starting bonus based on the die roll, and sends a follow-up message
        with the result. It then adds a block transaction to the blockchain,
        logs the event, and stops the interaction.
        Args:
            interaction (Interaction): The interaction object.
        """
        clicker: User | Member = interaction.user  # The one who clicked
        clicker_id: int = clicker.id
        if clicker_id != self.invoker_id:
            await interaction.response.send_message(
                "You cannot roll the die for someone else!", ephemeral=True)
        else:
            self.button_clicked = True
            self.die_button.disabled = True
            await interaction.response.edit_message(view=self)
            die_roll: int = random.randint(1, 6)
            starting_bonus: int = self.starting_bonus_awards[die_roll]
            message_content: str = (
                f"You rolled a {die_roll} and won {starting_bonus} {coins}!\n"
                "You may now play on the slot machines. Good luck!")
            await interaction.followup.send(message_content)
            del message_content
            await add_block_transaction(
                blockchain=blockchain,
                sender=casino_house_id,
                receiver=self.invoker,
                amount=starting_bonus,
                method="starting_bonus"
            )
            self.save_data.starting_bonus_available = False
            last_block_timestamp: float | None = get_last_block_timestamp()
            if last_block_timestamp is None:
                print("ERROR: Could not get last block timestamp.")
                await terminate_bot()
            log.log(
                line=(f"{self.invoker} ({self.invoker_id}) won "
                      f"{starting_bonus} {coins} from the starting bonus."),
                timestamp=last_block_timestamp)
            del last_block_timestamp
            self.stop()

    async def on_timeout(self) -> None:
        """
        Handles the timeout event for the view.

        This method is called when the user takes too long to roll the die.
        It disables the die button and sends a message to the user indicating
        that they took too long and can run the command again when ready.
        """
        self.die_button.disabled = True
        message_content = ("You took too long to roll the die. When you're "
                           "ready, you may run the command again.")
        await self.interaction.edit_original_response(
            content=message_content, view=self)
        del message_content

    async def _scheduled_task(self,
                              item: Item[View],
                              interaction: Interaction) -> None:
        try:
            if interaction.data is not None:
                item._refresh_state(  # type: ignore
                    interaction, interaction.data)  # type: ignore

            allow: bool = (await item.interaction_check(interaction) and
                           await self.interaction_check(interaction))
            if not allow:
                return

            # Commented out code that restarts the timeout on click
            # if self.timeout:
            #     self.__timeout_expiry = time.monotonic() + self.timeout

            await item.callback(interaction)
        except Exception as e:
            return await self.on_error(interaction, e, item)

# endregion

# region Grifter Suppliers


class GrifterSuppliers:
    """
    Handels which users are grifter suppliers.
    """

    def __init__(self) -> None:
        self.file_name: str = "data/grifter_suppliers.json"
        # IMPROVE Use hash set instead of list
        self.suppliers: List[int] = self.load()

    def load(self) -> List[int]:
        """
        Loads the grifter suppliers from the JSON file.
        """
        # Create missing directories
        directories: str = self.file_name[:self.file_name.rfind("/")]
        makedirs(directories, exist_ok=True)
        if not exists(self.file_name):
            print("Grifter suppliers file not found.")
            return []

        # Load the data from the file
        with open(self.file_name, "r") as file:
            suppliers_json: Dict[str, List[int]] = json.load(file)
            suppliers: List[int] = suppliers_json.get("suppliers", [])
            if len(suppliers) == 0:
                print("No grifter suppliers found.")
        return suppliers

    async def add(self, user: User | Member) -> None:
        """
        Add user IDs to the list of grifter suppliers.
        """
        user_name: str = user.name
        user_id: int = user.id
        del user
        if user_id not in self.suppliers:
            self.suppliers.append(user_id)
            print(f"User {user_name} ({user_id}) added "
                  "to the grifter suppliers registry.")
        else:
            print(f"User {user_name} ({user_id}) is already in the"
                  "grifter suppliers registry.")
        with open(self.file_name, "w") as file:
            json.dump({"suppliers": self.suppliers}, file)

    async def replace(self, user_ids: List[int]) -> None:
        """
        Replace the list of grifter suppliers with a new list.
        """
        print("Replacing grifter suppliers registry...")
        for user_id in user_ids:
            user: User = await bot.fetch_user(user_id)
            user_name: str = user.name
            print(f"User {user_name} ({user_id}) will be added to the "
                  "grifter suppliers registry.")
        self.suppliers = user_ids
        with open(self.file_name, "w") as file:
            json.dump({"suppliers": self.suppliers}, file)
        print("Grifter suppliers registry replaced.")

    def remove(self, user: User | Member) -> None:
        """
        Remove user ID from the list of grifter suppliers.
        """
        user_id: int = user.id
        user_name: str = user.name
        if user_id in self.suppliers:
            self.suppliers.remove(user_id)
            print(f"User {user_name} ({user_id}) removed from the "
                  "grifter suppliers registry.")
        else:
            print(f"User {user_name} ({user_id}) is not in the "
                  "grifter suppliers registry.")
        with open(self.file_name, "w") as file:
            json.dump({"suppliers": self.suppliers}, file)
# endregion

# region Transfers waiting


class TransfersWaitingApproval:
    """
    Handles transfers waiting for approval.
    """

    def __init__(self) -> None:
        self.file_name: str = "data/transfers_waiting_approval.json"
        self.transfers: List[TransactionRequest] = self.load()

    def load(self) -> List[TransactionRequest]:
        """
        Loads the transfer requests from the JSON file.
        """
        # Create missing directories
        directories: str = self.file_name[:self.file_name.rfind("/")]
        makedirs(directories, exist_ok=True)
        if not exists(self.file_name):
            print("Transfers waiting approval file not found.")
            return []

        # Load the data from the file
        with open(self.file_name, "r") as file:
            transfers_json: Dict[str, List[TransactionRequest]] = (
                json.load(file))
            transfers: List[TransactionRequest] = (
                transfers_json.get("transfers", []))
            if len(transfers) == 0:
                print("No transfers waiting approval found.")
        return transfers

    def add(self, transfer: TransactionRequest) -> None:
        """
        Add a transfer to the list of transfers waiting for approval.
        """
        self.transfers.append(transfer)
        with open(self.file_name, "w") as file:
            json.dump({"transfers": self.transfers}, file)

    def remove(self, transfer: TransactionRequest) -> None:
        """
        Remove a transfer from the list of transfers waiting for approval.
        """
        if transfer in self.transfers:
            self.transfers.remove(transfer)
            with open(self.file_name, "w") as file:
                json.dump({"transfers": self.transfers}, file)
            # print("Transfer removed from the approval list.")

# endregion

# region Slots buttons


class SlotMachineView(View):
    def __init__(self,
                 invoker: User | Member,
                 slot_machine: SlotMachine,
                 text_row_1: str,
                 text_row_2: str,
                 interaction: Interaction) -> None:
        """
        Initialize the SlotMachineView instance.

        Args:
            invoker: The user or member who invoked the slot machine command.
            slot_machine: The slot machine instance.
            wager: The amount of coins wagered.
            fees: The total fees paid this time.
            interaction: The interaction instance.

        Attributes:
            current_reel_number: The current reel number being processed.
            reels_stopped: The number of reels that have stopped.
            invoker: The user or member who invoked the  slot machine command.
            invoker_id: The ID of the invoker.
            slot_machine: The slot machine instance.
            wager: The amount of coins wagered.
            fees: The total fees paid this time.
            empty_space: A string of empty spaces for formatting.
            message_header: The first row of the message.
            message_collect_screen: The message displayed on the collect screen.
            message_results_row: The message displaying the results row.
            message: The complete message to be displayed.
            combo_events: The combination events configuration.
            interaction: The interaction instance.
            reels_results: The results of the reels.
            button_clicked: Indicates if a button has been clicked.
            stop_reel_buttons: A list containing the stop reel buttons.
            TODO Update docstrings
        """
        super().__init__(timeout=20)
        self.current_reel_number: int = 1
        self.reels_stopped: int = 0
        self.invoker: User | Member = invoker
        self.invoker_id: int = invoker.id
        self.slot_machine: SlotMachine = slot_machine
        # TODO Move message variables to global scope
        self.empty_space: LiteralString = "\N{HANGUL FILLER}" * 11
        self.message_header_row: str = slot_machine.header
        self.message_text_row_1: str = text_row_1
        self.message_text_row_2: str = text_row_2
        self.spin_emojis: SpinEmojis = (
            self.slot_machine.configuration["reel_spin_emojis"])
        self.spin_emoji_1_name: str = self.spin_emojis["spin1"]["emoji_name"]
        self.spin_emoji_1_id: int = self.spin_emojis["spin1"]["emoji_id"]
        self.spin_emoji_1 = PartialEmoji(name=self.spin_emoji_1_name,
                                         id=self.spin_emoji_1_id,
                                         animated=True)
        self.message_reels_row: str = (f"{self.spin_emoji_1}\t\t"
                                       f"{self.spin_emoji_1}\t\t"
                                       f"{self.spin_emoji_1}\n")
        self.message_content: str = (
            slot_machine.make_message(text_row_1=self.message_text_row_1,
                                      text_row_2=self.message_text_row_2,
                                      reels_row=self.message_reels_row))
        self.combo_events: Dict[str, ReelSymbol] = (
            self.slot_machine.configuration["combo_events"])
        self.interaction: Interaction = interaction
        self.reels_results: ReelResults
        self.reels_results = {
            "reel1": {
                "associated_combo_event": {
                    "": {
                        "emoji_name": "",
                        "emoji_id": 0,
                        "wager_multiplier": 1.0,
                        "fixed_amount": 0
                    }
                },
                "emoji": self.spin_emoji_1
            },
            "reel2": {
                "associated_combo_event": {
                    "": {
                        "emoji_name": "",
                        "emoji_id": 0,
                        "wager_multiplier": 1.0,
                        "fixed_amount": 0
                    }
                },
                "emoji": self.spin_emoji_1
            },
            "reel3": {
                "associated_combo_event": {
                    "": {
                        "emoji_name": "",
                        "emoji_id": 0,
                        "wager_multiplier": 1.0,
                        "fixed_amount": 0
                    }
                },
                "emoji": self.spin_emoji_1
            }
        }
        self.button_clicked: bool = False
        self.stop_reel_buttons: List[Button[View]] = []
        # Create stop reel buttons
        for i in range(1, 4):
            button: Button[View] = Button(
                disabled=False,
                label="STOP",
                custom_id=f"stop_reel_{i}"
            )
            button.callback = lambda interaction, button_id=f"stop_reel_{i}": (
                self.on_button_click(interaction, button_id)
            )
            self.stop_reel_buttons.append(button)
            self.add_item(button)

    async def invoke_reel_stop(self, button_id: str) -> None:
        """
        Stops a reel and edits the message with the result.

        Args:
            button_id: The ID of the button that was clicked.
        """
        # Map button IDs to reel key names
        reel_stop_button_map: Dict[str, Literal["reel1", "reel2", "reel3"]] = {
            "stop_reel_1": "reel1",
            "stop_reel_2": "reel2",
            "stop_reel_3": "reel3"
        }
        # Pick reel based on button ID
        reel_name: Literal["reel1", "reel2", "reel3"] = (
            reel_stop_button_map[button_id])
        # Stop the reel and get the symbol
        symbol_name: str = self.slot_machine.stop_reel(reel=reel_name)
        # Get the emoji for the symbol (using the combo_events dictionary)
        symbol_emoji_name: str = self.combo_events[symbol_name]["emoji_name"]
        symbol_emoji_id: int = self.combo_events[symbol_name]["emoji_id"]
        # Create a PartialEmoji object (for the message)
        symbol_emoji: PartialEmoji = PartialEmoji(name=symbol_emoji_name,
                                                  id=symbol_emoji_id)
        # Copy keys and values from the appropriate sub-dictionary
        # in combo_events
        combo_event_properties: ReelSymbol = {**self.combo_events[symbol_name]}
        symbol_name: str = symbol_name
        reel_result: ReelResult = {
            "associated_combo_event": {symbol_name: combo_event_properties},
            "emoji": symbol_emoji
        }
        # Add the emoji to the result
        self.reels_results[reel_name] = reel_result
        self.reels_stopped += 1
        self.message_reels_row: str = (
            f"{self.reels_results['reel1']['emoji']}\t\t"
            f"{self.reels_results['reel2']['emoji']}\t\t"
            f"{self.reels_results['reel3']['emoji']}")
        self.message_content = self.slot_machine.make_message(
            text_row_1=self.message_text_row_1,
            text_row_2=self.message_text_row_2,
            reels_row=self.message_reels_row)

    # stop_button_callback
    async def on_button_click(self,
                              interaction: Interaction,
                              button_id: str) -> None:
        """
        Events to occur when a stop reel button is clicked.

        Args:
            interaction: The interaction object.
            button_id: The ID of the button that was clicked.
        """
        clicker_id: int = interaction.user.id
        if clicker_id != self.invoker_id:
            await interaction.response.send_message(
                "Someone else is playing this slot machine. Please take "
                "another one.", ephemeral=True)
        else:
            self.button_clicked = True
            if self.timeout is not None and self.reels_stopped != 3:
                # Increase the timeout
                self.timeout += 1
            # Turn the clickable button into a disabled button,
            # stop the corresponding reel and edit the message with the result
            self.stop_reel_buttons[int(button_id[-1]) - 1].disabled = True
            # print(f"Button clicked: {button_id}")
            # The self.halt_reel() method updates self.message_content
            await self.invoke_reel_stop(button_id=button_id)
            await interaction.response.edit_message(
                content=self.message_content, view=self)
            if self.reels_stopped == 3:
                self.stop()

    async def start_auto_stop(self) -> None:
        """
        Auto-stop the next reel.
        """
        if self.reels_stopped == 3:
            self.stop()
            return

        # Disable all buttons
        unclicked_buttons: List[str] = []
        for button in self.stop_reel_buttons:
            if not button.disabled:
                button_id: str = cast(str, button.custom_id)
                unclicked_buttons.append(button_id)
                button.disabled = True

        # Stop the remaining reels
        for button_id in unclicked_buttons:
            await self.invoke_reel_stop(button_id=button_id)
            await self.interaction.edit_original_response(
                content=self.message_content,
                view=self)
            if self.reels_stopped < 3:
                await asyncio.sleep(1)
        # The self.halt_reel() method stops the view if
        # all reels are stopped
# endregion

# region AML view


class AmlView(View):
    def __init__(self,
                 interaction: Interaction,
                 initial_message: str) -> None:
        """
        Initialize the AmlView instance.

        Args:
            interaction: The interaction instance.

        Attributes:
            interaction: The interaction instance.
        """
        super().__init__(timeout=60)
        invoker: User | Member = interaction.user
        self.invoker_id: int = invoker.id
        self.invoker_id: int = interaction.user.id
        self.interaction: Interaction = interaction
        self.initial_message: str = initial_message
        self.followup_message: Message | None = None
        self.approve_button: Button[View] = Button(
            disabled=False,
            label="Approve",
            custom_id="aml_approve"
        )
        self.approve_button.callback = lambda interaction: (
            self.on_button_click(
                interaction=interaction, button=self.approve_button))
        self.decline_button: Button[View] = Button(
            disabled=False,
            label="Decline",
            custom_id="aml_decline"
        )
        self.decline_button.callback = lambda interaction: (
            self.on_button_click(
                interaction=interaction, button=self.decline_button))
        self.add_item(self.approve_button)
        self.add_item(self.decline_button)
        self.approved: bool = False

    async def on_button_click(self,
                              interaction: Interaction,
                              button: Button[View]) -> None:
        """
        Handles the event when a button is clicked.

        Args:
            interaction: The interaction object.
        """
        clicker: User | Member = interaction.user
        clicker_id: int = clicker.id
        if clicker_id != self.invoker_id:
            await interaction.response.send_message(
                "This is not your AML terminal.",
                ephemeral=True)
        else:
            self.approve_button.disabled = True
            self.decline_button.disabled = True
            await interaction.response.edit_message(view=self)
            message_content: str = f"{self.initial_message}\n"
            if button == self.approve_button:
                message_content += (f"-# The {Coin} Bank has approved "
                                    "the transaction.")
                self.approved = True
            else:
                message_content += (f"-# The {Coin} Bank has declined "
                                    "the transaction.")
            if self.followup_message is None:
                await self.interaction.edit_original_response(
                    content=message_content, view=self,
                    allowed_mentions=AllowedMentions.none())
            else:
                message_id: int = self.followup_message.id
                await self.interaction.followup.edit_message(
                    message_id=message_id,
                    content=message_content, view=self,
                    allowed_mentions=AllowedMentions.none())
            self.stop()

    async def on_timeout(self) -> None:
        """
        Handles the timeout event for the view.

        This method is called when the user takes too long to respond.
        It disables the buttons and sends a message to the user indicating
        that they took too long and can run the command again when ready.
        """
        self.approve_button.disabled = True
        self.decline_button.disabled = True
        message_content: str = ("The AML officer has left the terminal.")
        if self.followup_message is None:
            await self.interaction.edit_original_response(
                content=message_content, view=self)
        else:
            message_id: int = self.followup_message.id
            await self.interaction.followup.edit_message(
                message_id=message_id,
                content=message_content, view=self)
        del message_content
# endregion

# region Flask funcs


def start_flask_app_waitress() -> None:
    """
    Starts a Flask application using Waitress as the WSGI server.
    This function initializes a Waitress subprocess to serve the Flask
    application. It also starts separate threads to stream the standard
    output and error output from the Waitress subprocess.
    Global Variables:
        waitress_process: The subprocess running the Waitress server.
    """
    global waitress_process

    def stream_output(pipe: TextIO, prefix: str) -> None:
        """
        Streams output from a given pipe, prefixing each line with a
        specified string.

        Args:
            pipe: The pipe to read the output from.
            prefix: The string to prefix each line of output with.
        """
        # Receive output from the Waitress subprocess
        for line in iter(pipe.readline, ''):
            # print(f"{prefix}: {line}", end="")
            print(f"{line}", end="")
        if hasattr(pipe, 'close'):
            pipe.close()

    print("Starting Flask app with Waitress...")
    program = "waitress-serve"
    app_name = "blockchain.sbchain"
    host = "*"
    # Use the environment variable or default to 8000
    port: str = os_environ.get("PORT", "8080")
    command: List[str] = [
        program,
        f"--listen={host}:{port}",
        f"{app_name}:app"
    ]
    waitress_process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    print("Flask app started with Waitress.")

    # Start threads to read output from the subprocess
    threading.Thread(
        target=stream_output,
        args=(waitress_process.stdout, "STDOUT"),
        daemon=True
    ).start()
    threading.Thread(
        target=stream_output,
        args=(waitress_process.stderr, "STDERR"),
        daemon=True
    ).start()


def start_flask_app() -> None:
    """
    Starts the Flask application.

    This function initializes and runs the Flask development server.
    If an exception occurs during the startup, it catches the exception and
    prints an error message.

    Raises:
        Exception: If there is an error running the Flask app.
    """
    # For use with the Flask development server
    print("Starting flask app...")
    try:
        sbchain.app.run(port=5000, debug=True, use_reloader=False)
    except Exception as e:
        error_message: str = f"ERROR: Error running Flask app: {e}"
        raise Exception(error_message)
# endregion

# region Config


def invoke_bot_configuration() -> None:
    """
    Updates the global config variables.
    This is necessary because I need to be able to update the config with
    a slash command.
    """
    print("Loading bot configuration...")
    global configuration, coin, Coin, coins, Coins, coin_emoji_id
    global coin_emoji_name, blockchain_name, Blockchain_name, casino_house_id
    global administrator_id, slot_machine, casino_channel_id, grifter_swap_id
    global sbcoin_id
    configuration = BotConfiguration()
    coin = configuration.coin
    Coin = configuration.Coin
    coins = configuration.coins
    Coins = configuration.Coins
    coin_emoji_id = configuration.coin_emoji_id
    coin_emoji_name = configuration.coin_emoji_name
    casino_house_id = configuration.casino_house_id
    administrator_id = configuration.administrator_id
    casino_channel_id = configuration.casino_channel_id
    blockchain_name = configuration.blockchain_name
    Blockchain_name = configuration.Blockchain_name
    grifter_swap_id = configuration.grifter_swap_id
    sbcoin_id = configuration.sbcoin_id
    print("Bot configuration loaded.")


def reinitialize_slot_machine() -> None:
    """
    Initializes the slot machine.
    """
    global slot_machine
    slot_machine = SlotMachine()


def reinitialize_grifter_suppliers() -> None:
    """
    Initializes the grifter suppliers.
    """
    global grifter_suppliers
    grifter_suppliers = GrifterSuppliers()


def reinitialize_transfers_waiting_approval() -> None:
    """
    Initializes the transfers waiting for approval.
    """
    global transfers_waiting_approval
    transfers_waiting_approval = TransfersWaitingApproval()
# endregion

# region CP start


async def start_checkpoints(limit: int = 10) -> Dict[int, ChannelCheckpoints]:
    """
    Initializes checkpoints for all text channels in all guilds the bot is a
    member of; creates instances of ChannelCheckpoints for each channel.

    Args:
        limit: The maximum number of checkpoints to create for each channel.
        Defaults to 10.

    Returns:
        Dict: A dictionary where the keys are channel IDs and the values are
        ChannelCheckpoints objects.
    """
    all_checkpoints: dict[int, ChannelCheckpoints] = {}
    print("Starting checkpoints...")
    channel_id: int = 0
    channel_name: str = ""
    for guild in bot.guilds:
        guild_id: int = guild.id
        guild_name: str = guild.name
        print(f"Guild: {guild_name} ({guild_id})")
        for channel in guild.text_channels:
            channel_id = channel.id
            channel_name = channel.name
            print(f"Channel: {channel_name} ({channel_id})")
            all_checkpoints[channel_id] = ChannelCheckpoints(
                guild_name=guild_name,
                guild_id=guild_id,
                channel_name=channel_name,
                channel_id=channel_id,
                max_checkpoints=limit
            )
    print("Checkpoints started.")
    return all_checkpoints
# endregion


# region Missed msgs


async def process_missed_messages(limit: int | None = None) -> None:
    """
    This function iterates through all guilds and their text channels to fetch
    messages that were sent while the bot was offline. It processes reactions to
    these messages and updates checkpoints to keep track of the last processed
    message in each channel.

    This does not process reactions to messages older than the last checkpoint
    (i.e. older than the last message sent before the bot went offline). That
    would require keeping track of every single message and reactions on the
    server in a database.
    Parameters:
        limit (int, optional): Limit the maximum number of messages to fetch per
        channel. Defaults to None.
    Global Variables:
        all_channel_checkpoints (dict): A dictionary storing checkpoints for

        each channel.
    """
    global all_channel_checkpoints
    missed_messages_processed_message: str = "Missed messages processed."

    print("Processing missed messages...")

    for guild in bot.guilds:
        print("Fetching messages from "
              f"guild: {guild.name} ({guild.id})...")
        for channel in guild.text_channels:
            print("Fetching messages from "
                  f"channel: {channel.name} ({channel.id})...")
            channel_checkpoints: List[Dict[str, int]] | None = (
                all_channel_checkpoints[channel.id].load())
            if channel_checkpoints is not None:
                print(f"Channel checkpoints loaded.")
            else:
                print("No checkpoints could be loaded.")
            new_channel_messages_found: int = 0
            fresh_last_message_id: int | None = None
            checkpoint_reached: bool = False
            # Fetch messages from the channel (reverse chronological order)
            try:
                async for message in channel.history(limit=limit):
                    message_id: int = message.id
                    if new_channel_messages_found == 0:
                        # The first message found will be the last message sent
                        # This will be used as the checkpoint
                        fresh_last_message_id = message_id
                    # print(f"{message.author}: "
                    #       f"{message.content} ({message_id}).")
                    if channel_checkpoints is not None:
                        for checkpoint in channel_checkpoints:
                            if message_id == checkpoint["last_message_id"]:
                                print("Channel checkpoint reached.")
                                checkpoint_reached = True
                                break
                        if checkpoint_reached:
                            break
                        new_channel_messages_found += 1
                        sender: Member | User
                        receiver: User | Member
                        for reaction in message.reactions:
                            async for user in reaction.users():
                                # print("Reaction found: "
                                #       f"{reaction.emoji}: {user}.")
                                # print(f"Message ID: {message_id}.")
                                # print(f"{message.author}: {message.content}")
                                sender = user
                                receiver = message.author
                                emoji: PartialEmoji | Emoji | str = (
                                    reaction.emoji)
                                await process_reaction(message_id=message_id,
                                                       emoji=emoji,
                                                       sender=sender,
                                                       receiver=receiver,)
                    del message_id
            except Exception as e:
                channel_name: str = channel.name
                print("ERROR: Error fetching messages "
                      f"from channel {channel_name} ({channel.id}): {e}")
            print("Messages from "
                  f"channel {channel.name} ({channel.id}) fetched.")
            if fresh_last_message_id is None:
                print("WARNING: No channel messages found.")
            else:
                if new_channel_messages_found > 0:
                    print(f"Saving checkpoint: {fresh_last_message_id}")
                    all_channel_checkpoints[channel.id].save(
                        fresh_last_message_id)
                else:
                    print("Will not save checkpoint for this channel because "
                          "no new messages were found.")
        print(f"Messages from guild {guild.id} ({guild}) fetched.")
    print(missed_messages_processed_message)
    del missed_messages_processed_message

# endregion

# region Coin reaction


async def process_reaction(message_id: int,
                           emoji: PartialEmoji | Emoji | str,
                           sender: Member | User,
                           receiver: Member | User | None = None,
                           receiver_id: int | None = None,
                           channel_id: int | None = None) -> None:
    """
    Processes a reaction event to mine a coin for a receiver.

    Args:
        emoji: The emoji used in the reaction.
        sender: The user who sent the reaction.
        receiver: The user who receives the coin. Defaults to None.
        receiver_id: The ID of the user who receives the coin. Defaults to None.
    """

    emoji_id: int | str | None = 0
    match emoji:
        case Emoji():
            emoji_id = emoji.id
        case PartialEmoji() if emoji.id is not None:
            emoji_id = emoji.id
        case PartialEmoji():
            return
        case str():
            return
    if emoji_id == coin_emoji_id:
        if receiver is None:
            # Get receiver from id
            if receiver_id is not None:
                receiver = await bot.fetch_user(receiver_id)
            else:
                raise ValueError("Receiver is None.")
        else:
            receiver_id = receiver.id
        sender_id: int = sender.id

        if sender_id == receiver_id:
            return

        # Check if the user has mined the message already
        sender_name: str = sender.name
        save_data: UserSaveData = UserSaveData(
            user_id=sender_id, user_name=sender_name)
        message_mined_data: str | List[int] | bool | float | None = (
            save_data.load("messages_mined"))
        message_mined: List[int] = (
            message_mined_data if isinstance(message_mined_data, list) else [])
        if message_id in message_mined:
            return
        # Add the message ID to the list of mined messages
        message_mined.append(message_id)
        save_data.save(key="messages_mined", value=message_mined)

        print(f"{sender} ({sender_id}) is mining 1 {coin} "
              f"for {receiver} ({receiver_id})...")
        await add_block_transaction(
            blockchain=blockchain,
            sender=sender,
            receiver=receiver,
            amount=1,
            method="reaction"
        )

        # Log the mining
        last_block_timestamp: float | None = get_last_block_timestamp()
        if last_block_timestamp is None:
            print("ERROR: Could not get last block timestamp.")
            await terminate_bot()

        try:
            mined_message: str = (f"{sender} ({sender_id}) mined 1 {coin} "
                                  f"for {receiver} ({receiver_id}).")
            log.log(line=mined_message, timestamp=last_block_timestamp)
            # Remove variables with common names to prevent accidental use
            del mined_message
            del last_block_timestamp
        except Exception as e:
            print(f"ERROR: Error logging mining: {e}")
            await terminate_bot()

        chain_validity: bool | None = None
        try:
            print("Validating blockchain...")
            chain_validity = blockchain.is_chain_valid()
        except Exception as e:
            # TODO Revert blockchain to previous state
            print(f"ERROR: Error validating blockchain: {e}")
            chain_validity = False

        if chain_validity is False:
            await terminate_bot()

        # Inform receiver if it's the first time they receive a coin
        # Do not pass the channel_id if you do not want to send message
        # (like perhaps when scraping old messages)
        if channel_id is None:
            return
        if ((coin == "coin") or
            (coin_emoji_id == 0) or
            (coin_emoji_name == "") or
                (casino_channel_id == 0)):
            print("WARNING: Skipping reaction message because "
                  "bot configuration is incomplete.")
            print(f"coin_emoji_id: {coin_emoji_id}")
            print(f"coin_emoji_name: {coin_emoji_name}")
            print(f"casino_channel_id: {casino_channel_id}")
            print(f"casino_channel: {casino_channel_id}")
            return
        save_data: UserSaveData = UserSaveData(
            user_id=sender_id, user_name=sender_name)
        mining_messages_enabled: bool = save_data.mining_messages_enabled
        if about_command_mention is None:
            error_message = ("ERROR: `about_command_mention` is None. This "
                             "usually means that the commands have not been ")
            raise ValueError(error_message)
        if not mining_messages_enabled:
            return
        receiver_name: str = receiver.name
        save_data_receiver: UserSaveData = UserSaveData(
            user_id=receiver_id, user_name=receiver_name)
        del receiver_name
        informed_about_coin_reactions: bool = (
            save_data_receiver.reaction_message_received)
        if informed_about_coin_reactions:
            return
        channel: (VoiceChannel | StageChannel | ForumChannel | TextChannel |
                  CategoryChannel | Thread | PrivateChannel | None) = (
            bot.get_channel(channel_id))
        if not isinstance(channel, (VoiceChannel, TextChannel, Thread)):
            return
        casino_channel: (VoiceChannel | StageChannel | ForumChannel |
                         TextChannel | CategoryChannel | Thread |
                         PrivateChannel |
                         None) = bot.get_channel(casino_channel_id)
        user_message: Message = await channel.fetch_message(message_id)
        if isinstance(casino_channel, PrivateChannel):
            raise ValueError("ERROR: casino_channel is a private channel.")
        elif casino_channel is None:
            raise ValueError("ERROR: casino_channel is None.")
        sender_mention: str = sender.mention
        message_content: str = (f"-# {sender_mention} has "
                                f"mined a {coin} for you! "
                                f"Enter {about_command_mention} "
                                "in the chat box to learn more.")
        await user_message.reply(message_content,
                                 allowed_mentions=AllowedMentions.none())
        del user_message
        del message_content
        del channel
        del channel_id
        del sender_mention
        save_data_receiver.reaction_message_received = True
# endregion

# region Get timestamp


def get_last_block_timestamp() -> float | None:
    """
    Retrieves the timestamp of the last block in the blockchain.

    Returns:
        float | None: The timestamp of the last block if available,
        otherwise None.

    Raises:
        Exception: If there is an error retrieving the last block.
    """
    last_block_timestamp: float | None = None
    try:
        # Get the last block's timestamp for logging
        last_block: None | sbchain.Block = blockchain.get_last_block()
        if last_block is not None:
            last_block_timestamp = last_block.timestamp
            del last_block
        else:
            print("ERROR: Last block is None.")
            return None
    except Exception as e:
        print(f"ERROR: Error getting last block: {e}")
        return None
    return last_block_timestamp
# endregion

# region Add tx block


async def add_block_transaction(
        blockchain: sbchain.Blockchain,
        sender: Member | User | int,
        receiver: Member | User | int,
        amount: int,
        method: str) -> None:
    """
    Adds a transaction to the blockchain.

    Args:
        blockchain: The blockchain instance to which the transaction will
            be added.
        sender: The sender of the transaction. Can be a Member, User,
            or an integer User ID.
        receiver: The receiver of the transaction. Can be a Member, User,
            or an integer ID.
        amount: The amount of the transaction.
        method: The method of the transaction; "reaction", "slot_machine",
            "transfer".

    Raises:
        Exception: If there is an error adding the transaction to
            the blockchain.
    """
    if isinstance(sender, int):
        sender_id = sender
    else:
        sender_id: int = sender.id
    if isinstance(receiver, int):
        receiver_id = receiver
    else:
        receiver_id: int = receiver.id
    sender_id_unhashed: int = sender_id
    receiver_id_unhashed: int = receiver_id
    sender_id_hash: str = (
        sha256(str(sender_id_unhashed).encode()).hexdigest())
    del sender_id
    del sender_id_unhashed
    receiver_id_hash: str = (
        sha256(str(receiver_id_unhashed).encode()).hexdigest())
    del receiver_id
    del receiver_id_unhashed
    print("Adding transaction to blockchain...")
    try:
        data: List[Dict[str, sbchain.TransactionDict]] = (
            [{"transaction": {
                "sender": sender_id_hash,
                "receiver": receiver_id_hash,
                "amount": amount,
                "method": method
            }}])
        data_casted: List[str | Dict[str, sbchain.TransactionDict]] = (
            cast(List[str | Dict[str, sbchain.TransactionDict]], data))
        blockchain.add_block(data=data_casted, difficulty=0)
    except Exception as e:
        print(f"ERROR: Error adding transaction to blockchain: {e}")
        await terminate_bot()
    print("Transaction added to blockchain.")
# endregion

# region Transfer


async def transfer_coins(sender: Member | User,
                         receiver: Member | User,
                         amount: int,
                         method: str,
                         channel_id: int,
                         purpose: str | None = None,
                         interaction: Interaction | None = None) -> None:
    """
    Transfers coins from one user to another.
    Only pass the interaction parameter if the transfer is immediately initiated
    by the one who wishes to make a transfer.
    """
    if interaction:
        channel = interaction.channel
    else:
        channel: (VoiceChannel | StageChannel | ForumChannel | TextChannel |
                  CategoryChannel | Thread | PrivateChannel | None) = (
            bot.get_channel(channel_id))

    async def send_message(message_text: str,
                           ephemeral: bool = False,
                           allowed_mentions: AllowedMentions = MISSING) -> None:
        if interaction is None:
            if channel is None:
                print("ERROR: channel is None.")
                return
            elif isinstance(channel,
                            (PrivateChannel, ForumChannel, CategoryChannel)):
                # [ ] Test
                print(f"ERROR: channel is a {type(channel).__name__}.")
                return
            await channel.send(content=message_text)
        else:
            if not has_responded:
                await interaction.response.send_message(
                    content=message_text,
                    ephemeral=ephemeral,
                    allowed_mentions=allowed_mentions)
            else:
                await interaction.followup.send(
                    content=message_text,
                    ephemeral=ephemeral,
                    allowed_mentions=allowed_mentions)

    has_responded: bool = False
    sender_id: int = sender.id
    receiver_id: int = receiver.id
    coin_label_a: str = format_coin_label(amount)
    sender_mention: str = sender.mention
    if not interaction:
        await send_message(f"{sender_mention} Your transfer request "
                           "has been approved.")
        has_responded = True
    print(f"User {sender_id} is attempting to transfer "
          f"{amount} {coin_label_a} to user {receiver_id}...")
    balance: int | None = None
    if amount == 0:
        message_content = "You cannot transfer 0 coins."
        await send_message(message_content, ephemeral=True)
        del message_content
        return
    elif amount < 0:
        message_content = "You cannot transfer a negative amount of coins."
        await send_message(message_content, ephemeral=True)
        del message_content
        return

    try:
        balance = blockchain.get_balance(user_unhashed=sender_id)
    except Exception as e:
        administrator: str = (await bot.fetch_user(administrator_id)).mention
        await send_message(f"Error getting balance. {administrator} pls fix.")
        error_message: str = ("ERROR: Error getting balance "
                              f"for user {sender} ({sender_id}): {e}")
        raise Exception(error_message)
    if balance is None:
        print(f"Balance is None for user {sender} ({sender_id}).")
        await send_message(f"You have 0 {coins}.")
        return
    if balance < amount:
        print(f"{sender} ({sender_id}) does not have enough {coins} to "
              f"transfer {amount} {coin_label_a} to {sender} ({sender_id}). "
              f"Balance: {balance}.")
        coin_label_b: str = format_coin_label(balance)
        await send_message(
            f"You do not have enough {coins}. "
            f"You have {balance} {coin_label_b}.", ephemeral=True)
        del coin_label_b
        return
    del balance

    if interaction:
        receiver_name: str = receiver.name
        recipient_account_data = UserSaveData(
            user_id=receiver_id, user_name=receiver_name)
        recipient_receive_blocked: bool = (
            recipient_account_data.blocked_from_receiving_coins)
        if recipient_receive_blocked:
            receiver_mention: str = receiver.mention
            aml_role: None | Role = get_aml_officer_role(interaction)
            if aml_role is None:
                raise Exception("aml_role is None.")
            aml_mention: str = aml_role.mention
            message_content = (f"{receiver_mention} has been blocked from "
                               f"receiving {coins}.\n"
                               "-# If you believe this is a "
                               "mistake, please contact "
                               "an anti-money-laundering officer by "
                               f"mentioning {aml_mention}.")
            await interaction.response.send_message(
                message_content, allowed_mentions=AllowedMentions.none())
            del message_content
            return
        auto_approve_transfer_limit: int = (
            configuration.auto_approve_transfer_limit)
        if ((amount > auto_approve_transfer_limit) and
            (sender_id != grifter_swap_id) and
                (receiver_id != grifter_swap_id)):
            # Unhindered transfers between GrifterSwap (abuse is mitigated by
            # the GrifterSwap supplier check in the /slots command)
            print(f"Transfer amount exceeds auto-approval limit of "
                  f"{auto_approve_transfer_limit}.")
            receiver_mention: str = receiver.mention
            if purpose is None:
                message_content: str = (
                    f"Anti-money laundering policies (AML) requires us to "
                    "manually approve this transaction. "
                    "Please state your purpose of transferring "
                    f"{amount} {coin_label_a} to {receiver_mention}.")
                await interaction.response.send_message(message_content)
                del message_content

                def check(message: Message) -> bool:
                    message_author: User | Member = message.author
                    return message_author == sender
                try:
                    purpose_message: Message = await bot.wait_for(
                        "message", timeout=60, check=check)
                except asyncio.TimeoutError:
                    message_content = "Come back when you have a purpose."
                    await interaction.followup.send(message_content)
                    del message_content
                    return
                purpose = purpose_message.content
            else:
                # Need to defer to get a message id
                # (used to make a message link in /aml)
                await interaction.response.defer()
            request_timestamp: float = time()
            interaction_message: InteractionMessage = (
                await interaction.original_response())
            interaction_message_id: int = interaction_message.id
            del interaction_message
            if channel is None:
                raise Exception("channel is None.")
            transaction_request: TransactionRequest = {
                "sender_id": sender_id,
                "receiver_id": receiver_id,
                "amount": amount,
                "request_timestamp": request_timestamp,
                "channel_id": channel_id,
                "message_id": interaction_message_id,
                "purpose": purpose
            }
            try:
                transfers_waiting_approval.add(transaction_request)
                awaiting_approval_message_content: str = (
                    f"A request for transferring {amount} {coin_label_a} "
                    f"to {receiver_mention} has been sent for approval.")
                await interaction.followup.send(
                    awaiting_approval_message_content,
                    allowed_mentions=AllowedMentions.none())
                log_message: str = (
                    f"A request for transferring {amount} {coin_label_a} "
                    f"to {receiver_mention} for the purpose of \"{purpose}\" has "
                    "been sent for approval.")
                log.log(log_message, request_timestamp)
                del log_message
            except Exception as e:
                administrator: str = (
                    (await bot.fetch_user(administrator_id)).mention)
                message_content = ("Error sending transfer request.\n"
                                   f"{administrator} pls fix.")
                await interaction.followup.send(message_content)
                del message_content
                error_message = ("ERROR: Error adding transaction request "
                                 f"to queue: {e}")
                raise Exception(error_message)
            try:
                aml_office_thread_id: int = configuration.aml_office_thread_id
                aml_office_thread: (
                    VoiceChannel | StageChannel | ForumChannel | TextChannel |
                    CategoryChannel | PrivateChannel |
                    Thread) = await bot.fetch_channel(aml_office_thread_id)
                if isinstance(aml_office_thread, Thread):
                    guild: Guild | None = interaction.guild
                    if guild is None:
                        print("ERROR: Guild is None.")
                        return
                    aml_officer: Role | None = get_aml_officer_role(
                        interaction)
                    if aml_officer is None:
                        raise Exception("aml_officer is None.")
                    aml_officer_mention: str = aml_officer.mention
                    aml_office_message: str = (aml_officer_mention +
                                               awaiting_approval_message_content)

                    await aml_office_thread.send(
                        aml_office_message,
                        allowed_mentions=AllowedMentions.none())
            except Exception as e:
                administrator: str = (
                    (await bot.fetch_user(administrator_id)).mention)
                message_content = (
                    "There was an error notifying the AML office.\n"
                    f"{administrator} pls fix.")
                await interaction.followup.send(message_content)
                del message_content
                error_message = ("ERROR: Error sending transfer request "
                                 f"to AML office: {e}")
                raise Exception(error_message)
            return

    await add_block_transaction(
        blockchain=blockchain,
        sender=sender,
        receiver=receiver,
        amount=amount,
        method=method
    )
    last_block: sbchain.Block | None = blockchain.get_last_block()
    if last_block is None:
        print("ERROR: Last block is None.")
        administrator: str = (await bot.fetch_user(administrator_id)).mention
        await send_message(f"Error transferring {coins}. "
                           f"{administrator} pls fix.")
        await terminate_bot()
    timestamp: float = last_block.timestamp
    log.log(line=f"{sender} ({sender_id}) transferred {amount} {coin_label_a} "
            f"to {receiver} ({receiver_id}).",
            timestamp=timestamp)
    sender_mention: str = sender.mention
    receiver_mention: str = receiver.mention
    allowed_pings = AllowedMentions(users=[receiver])
    await send_message(
        f"{sender_mention} transferred "
        f"{amount} {coin_label_a} "
        f"to {receiver_mention}'s account.",
        allowed_mentions=allowed_pings)
    del sender
    del sender_id
    del receiver
    del receiver_id
    del amount
    del coin_label_a
# endregion

# region AML Officer


def get_aml_officer_role(interaction: Interaction):
    guild: Guild | None = interaction.guild
    if guild is None:
        print("ERROR: Guild is None.")
        return
    aml_officer: Role | None = None
    role_names: List[str] = [
        "Anti-Money Laundering Officer",
        "Anti-money laundering officer",
        "anti_money_laundering_officer",
        "AML Officer", "AML officer" "aml_officer"]
    for role_name in role_names:
        aml_officer = utils.get(guild.roles, name=role_name)
        if aml_officer is not None:
            break
    return aml_officer


def test_invoker_is_aml_officer(interaction: Interaction) -> bool:
    invoker: User | Member = interaction.user
    invoker_roles: List[Role] = cast(Member, invoker).roles
    role_names: List[str] = [
        "Anti-Money Laundering Officer",
        "Anti-money laundering officer",
        "anti_money_laundering_officer",
        "AML Officer", "AML officer" "aml_officer"]
    aml_officer_role: Role | None = None
    for role_name in role_names:
        aml_officer_role = utils.get(invoker_roles, name=role_name)
        if aml_officer_role is not None:
            break
    del invoker, invoker_roles
    if aml_officer_role is None:
        return False
    else:
        return True
# endregion

# region Terminate bot


async def terminate_bot() -> NoReturn:
    """
    Closes the bot, shuts down the blockchain server, and exits the script.

    Returns:
        NoReturn: This function does not return any value.
    """
    print("Closing bot...")
    await bot.close()
    print("Bot closed.")
    print("Shutting down the blockchain app...")
    waitress_process.send_signal(signal.SIGTERM)
    waitress_process.wait()
    # print("Shutting down blockchain flask app...")
    # try:
    #     requests.post("http://127.0.0.1:5000/shutdown")
    # except Exception as e:
    #     print(e)
    await asyncio.sleep(1)  # Give time for all tasks to finish
    print("The script will now exit.")
    sys_exit(1)
# endregion

# region Guild list


# def load_guild_ids(file_name: str = "data/guild_ids.txt") -> List[int]:
#     """
#     Loads guild IDs from a specified file and updates the file with any
#     new guild IDs.

#     Args:
#         file_name: The path to the file containing the guild IDs. Defaults
#             to "data/guild_ids.txt".

#     Returns:
#         List[int]: A list of guild IDs.
#     """
#     print("Loading guild IDs...")
#     # Create missing directories
#     directories: str = file_name[:file_name.rfind("/")]
#     makedirs(directories, exist_ok=True)
#     guild_ids: List[int] = []
#     read_mode: str = "a+"
#     if not exists(file_name):
#         read_mode = "w+"
#     else:
#         read_mode = "r+"
#     with open(file_name, read_mode) as file:
#         for line in file:
#             guild_id = int(line.strip())
#             print(f"Adding guild ID {guild_id} from file to the list...")
#             guild_ids.append(guild_id)
#         for guild in bot.guilds:
#             guild_id: int = guild.id
#             if not guild_id in guild_ids:
#                 print(f"Adding guild ID {guild_id} "
#                       "to the list and the file...")
#                 file.write(f"{guild_id}\n")
#                 guild_ids.append(guild_id)
#     print("Guild IDs loaded.")
#     return guild_ids
# endregion

# region Format timestamp
def format_timestamp(timestamp: float, time_zone: str | None = None) -> str:
    """
    Formats a Unix timestamp to a localized human-readable format.

    Args:
        timestamp: The Unix timestamp to format.
    Returns:
        str: The formatted timestamp.
    """
    timestamp_friendly: str
    if time_zone is None:
        # Use local time zone
        timestamp_friendly = (
            datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"))
    else:
        # Convert Unix timestamp to datetime object
        timestamp_dt: datetime = (
            datetime.fromtimestamp(timestamp, pytz.utc))

        # Adjust for time zone
        timestamp_dt = (
            timestamp_dt.astimezone(pytz.timezone(time_zone)))

        # Format the timestamp
        timestamp_friendly = (
            timestamp_dt.strftime("%Y-%m-%d %H:%M:%S"))

    return timestamp_friendly
# endregion

# region Coin label


def format_coin_label(number: int) -> str:
    """
    Returns the appropriate label for the given number of coins.

    Args:
        number (int): The number of coins.

    Returns:
        str: "coin" if the number is 1 or -1, otherwise "coins".
    """
    if number == 1 or number == -1:
        return coin
    else:
        return coins
# endregion


# region Global variables
coin: str = ""
Coin: str = ""
coins: str = ""
Coins: str = ""
coin_emoji_id: int = 0
coin_emoji_name: str = ""
casino_house_id: int = 0
administrator_id: int = 0
all_channel_checkpoints: Dict[int, ChannelCheckpoints] = {}
casino_channel_id: int = 0
blockchain_name: str = ""
Blockchain_name: str = ""
about_command_mention: str | None = ""
grifter_swap_id: int = 0
sbcoin_id: int = 0
decrypted_transactions_spreadsheet = None
# endregion

# region Flask
if __name__ == "__main__":
    print("Starting blockchain flask app thread...")
    try:
        flask_thread = threading.Thread(target=start_flask_app_waitress)
        flask_thread.daemon = True  # Set the thread as a daemon thread
        flask_thread.start()
        print("Flask app thread started.")
    except Exception as e:
        print(f"ERROR: Error starting Flask app thread: {e}")
    sleep(1)

    print(f"Initializing blockchain...")
    try:
        blockchain_path = "data/blockchain.json"
        transactions_path = "data/transactions.tsv"
        blockchain = sbchain.Blockchain(blockchain_path, transactions_path)
        print(f"Blockchain initialized.")
    except Exception as e:
        print(f"ERROR: Error initializing blockchain: {e}")
        print("This script will be terminated.")
        sys_exit(1)
# endregion

# region Init
print("Starting bot...")
time_zone = "Canada/Central"
invoke_bot_configuration()

slot_machine = SlotMachine()
grifter_suppliers = GrifterSuppliers()
aml_group = app_commands.Group(name="aml",
                               description="Anti-money laundering workstation")
transfers_waiting_approval = TransfersWaitingApproval()
decrypted_transactions_spreadsheet = (
    DecryptedTransactionsSpreadsheet(time_zone=time_zone))

log = Log(time_zone=time_zone)


@bot.event
async def on_ready() -> None:
    """
    Event handler that is called when the bot is ready.
    This function performs the following actions:
    - Prints a message indicating that the bot has started.
    - Initializes global checkpoints for all channels.
    - Attempts to sync the bot's commands with Discord and prints the result.
    If an error occurs during the command sync process, it catches the exception
    and prints an error message.
    """
    global all_channel_checkpoints
    global about_command_mention

    print("Bot started.")

    all_channel_checkpoints = (
        await start_checkpoints(limit=per_channel_checkpoint_limit))
    await process_missed_messages(limit=50)

    bot.tree.add_command(aml_group)

    # global guild_ids
    # guild_ids = load_guild_ids()
    # print(f"Guild IDs: {guild_ids}")
    for guild in bot.guilds:
        print(f"- {guild.name} ({guild.id})")

    # Sync the commands to Discord
    print("Syncing global commands...")
    try:
        global_commands: List[app_commands.AppCommand] = await bot.tree.sync()
        print(f"Synced commands for bot {bot.user}.")
        print(f"Fetching command IDs...")
        about_command: AppCommand | None = None
        command_name: str
        for command in global_commands:
            command_name = command.name
            if command_name == f"about_{coin.lower()}":
                about_command = command
                break
        print("Command IDs fetched.")
        if about_command is None:
            print("ERROR: Could not find the about command. "
                  "Using string instead.")
            about_command_mention = f"about_{coin.lower()}"
        else:
            about_command_mention = about_command.mention
        print(f"Bot is ready!")
    except Exception as e:
        raise Exception(f"ERROR: Error syncing commands: {e}")
# endregion


# region Message
@bot.event
async def on_message(message: Message) -> None:
    """
    Handles incoming messages and saves channel checkpoints.
    If the channel ID of the incoming message is already in the global
    `all_channel_checkpoints` dictionary, it saves the message ID to the
    corresponding checkpoint. If the channel ID is not in the dictionary,
    it creates a new `ChannelCheckpoints` instance for the channel and adds
    it to the dictionary.
    Args:
        message (Message): The incoming message object.
    Returns:
        None
    """
    global all_channel_checkpoints
    channel_id: int = message.channel.id

    if channel_id in all_channel_checkpoints:
        message_id: int = message.id
        all_channel_checkpoints[channel_id].save(message_id)
        del message_id
    else:
        # If a channel is created while the bot is running, we will likely end
        # up here.
        # Add a new instance of ChannelCheckpoints to
        # the all_channel_checkpoints dictionary for this new channel.
        guild: Guild | None = message.guild
        if guild is None:
            # TODO Ensure checkpoints work threads
            # print("ERROR: Guild is None.")
            # administrator: str = (
            #     (await bot.fetch_user(administrator_id)).mention)
            # await message.channel.send("An error occurred. "
            #                            f"{administrator} pls fix.")
            raise Exception("Guild is None.")
        guild_name: str = guild.name
        guild_id: int = guild.id
        channel = message.channel
        if ((isinstance(channel, TextChannel)) or
                isinstance(channel, VoiceChannel)):
            channel_name: str = channel.name
            all_channel_checkpoints[channel_id] = ChannelCheckpoints(
                guild_name=guild_name,
                guild_id=guild_id,
                channel_name=channel_name,
                channel_id=channel_id
            )
        else:
            # print("ERROR: Channel is not a text channel or voice channel.")
            # administrator: str = (
            #     (await bot.fetch_user(ADMINISTRATOR_ID)).mention)
            # await message.channel.send("An error occurred. "
            #                            f"{administrator} pls fix.")
            return

    # Look for GrifterSwap messages
    message_author: User | Member = message.author
    message_author_id: int = message_author.id
    del message_author
    if message_author_id != grifter_swap_id:
        return
    if message.reference is None:
        return
    referenced_message_id: int | None = message.reference.message_id
    if referenced_message_id is None:
        return
    referenced_message: Message = await message.channel.fetch_message(
        referenced_message_id)
    referenced_message_text: str = referenced_message.content
    if referenced_message_text.startswith("!suppliers"):
        users_mentioned: List[int] = message.raw_mentions
        await grifter_suppliers.replace(users_mentioned)
        del users_mentioned
        return
    referenced_message_author: User | Member = referenced_message.author
    referenced_message_author_id: int = referenced_message_author.id
    message_text: str = message.content
    user_supplied_grifter_sbcoin: bool = (
        "Added" in message_text and
        "sent" in referenced_message_text and
        referenced_message_author_id == sbcoin_id)

    user_supplied_grifter_this_coin: bool = (
        "Added" in message_text and
        "transferred" in referenced_message_text and
        referenced_message_author_id == casino_house_id)

    if user_supplied_grifter_sbcoin or user_supplied_grifter_this_coin:
        # get the cached message in order to get the command invoker
        referenced_message_full: Message = (
            await message.channel.fetch_message(referenced_message_id))
        del referenced_message_id
        referenced_message_full_interaction: MessageInteraction | None = (
            referenced_message_full.interaction)
        if referenced_message_full_interaction is None:
            return
        referenced_message_full_invoker: User | Member = (
            referenced_message_full_interaction.user)
        await grifter_suppliers.add(referenced_message_full_invoker)
# endregion

# region Reaction


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


# region /transfer
@bot.tree.command(name="transfer",
                  description=f"Transfer {coins} to another user")
@app_commands.describe(amount=f"Amount of {coins} to transfer",
                       user=f"User to transfer the {coins} to",
                       purpose="Purpose of the transfer")
async def transfer(interaction: Interaction,
                   amount: int,
                   user: Member,
                   purpose: str | None = None) -> None:
    """
    Transfer a specified amount of coins to another user.

    Args:
        interaction: The interaction object representing the command invocation.
    """
    sender: User | Member = interaction.user
    sender_id: int = sender.id
    receiver: Member = user
    receiver_id: int = receiver.id
    channel: (
        VoiceChannel | StageChannel | TextChannel | ForumChannel |
        CategoryChannel | Thread | DMChannel | GroupChannel |
        None) = interaction.channel
    if channel is None:
        raise Exception("ERROR: channel is None.")
    channel_id: int = channel.id
    await transfer_coins(sender=sender,
                         receiver=receiver,
                         amount=amount,
                         purpose=purpose,
                         method="transfer",
                         channel_id=channel_id,
                         interaction=interaction,)
    del sender, sender_id, receiver, receiver_id, amount
# endregion

# region /balance


@bot.tree.command(name="balance", description="Check your balance")
@app_commands.describe(user="User to check the balance")
@app_commands.describe(incognito="Do not display the balance publicly")
async def balance(interaction: Interaction,
                  user: Member | None = None,
                  incognito: bool = False) -> None:
    """
    Check the balance of a user. If no user is specified, the balance of the
    user who invoked the command is checked.

    Args:
        interaction: The interaction object representing the command invocation.

        user: The user to check the balance. Defaults to None.
    """
    user_to_check: str
    if user is None:
        user_to_check = interaction.user.mention
        user_id: int = interaction.user.id
    else:
        user_to_check = user.mention
        user_id: int = user.id

    # print(f"Getting balance for user {user_to_check} ({user_id})...")
    user_id_hash: str = sha256(str(user_id).encode()).hexdigest()
    balance: int | None = blockchain.get_balance(user=user_id_hash)
    message_content: str = ""
    if balance is None and user is None:
        message_content = f"You have 0 {coins}."
    elif balance is None:
        message_content = f"{user_to_check} has 0 " f"{coins}."
    elif user is None:
        coin_label: str = format_coin_label(balance)
        message_content = f"You have {balance} {coin_label}."
    else:
        coin_label: str = format_coin_label(balance)
        message_content = f"{user_to_check} has {balance} {coin_label}."
    await interaction.response.send_message(
        message_content,
        ephemeral=incognito, allowed_mentions=AllowedMentions.none())
    del user_id
    del balance
    del message_content
# endregion

# region /reels


@bot.tree.command(name="reels",
                  description="Design the slot machine reels")
@app_commands.describe(add_symbol="Add a symbol to the reels")
@app_commands.describe(amount="Amount of symbols to add")
@app_commands.describe(remove_symbol="Remove a symbol from the reels")
@app_commands.describe(reel="The reel to modify")
@app_commands.describe(inspect="Inspect the reels")
@app_commands.describe(close_off="Close off the area so that others cannot "
                       "see the reels")
async def reels(interaction: Interaction,
                add_symbol: str | None = None,
                remove_symbol: str | None = None,
                amount: int | None = None,
                reel: str | None = None,
                close_off: bool = True,
                inspect: bool | None = None) -> None:
    """
    Design the slot machine reels by adding and removing symbols.
    After saving the changes, various statistics are calculated and displayed,
    namely:
    - The symbols and their amounts in each reel.
    - The total amount of symbol units in each reel.
    - The total amount of symbol units across all reels.
    - Probabilities of all possible outcomes in the game.
    - Expected total return.
    - Expected return.
    - RTP for different wagers.
    Only users with the "Administrator" or "Slot Machine Technician" role
    can utilize this command.

    Args:
        interaction: The interaction object representing the
        command invocation.

        add_symbol: add_symbol a symbol to the reels.
        Defaults to None.

        remove_symbol: Remove a symbol from the reels.
        Defaults to None.

        inspect: Doesn't do anything.
    """
    await interaction.response.defer(ephemeral=close_off)
    # Check if user has the necessary role
    invoker: User | Member = interaction.user
    invoker_roles: List[Role] = cast(Member, invoker).roles
    administrator_role: Role | None = (
        utils.get(invoker_roles, name="Administrator"))
    technician_role: Role | None = (
        utils.get(invoker_roles, name="Slot Machine Technician"))
    if technician_role is None and administrator_role is None:
        # TODO Maybe let other users see the reels
        message_content: str = ("Only slot machine technicians "
                                "may look at the reels.")
        await interaction.followup.send(message_content, ephemeral=True)
        del message_content
        return
    if amount is None:
        if reel is None:
            amount = 3
        else:
            amount = 1
    # BUG Refreshing the reels config from file is not working (have to restart instead)
    # Refresh reels config from file
    slot_machine.reels = slot_machine.load_reels()
    new_reels: Reels = slot_machine.reels
    if add_symbol and remove_symbol:
        await interaction.followup.send("You can only add or remove a "
                                        "symbol at a time.",
                                        ephemeral=True)
        return
    if add_symbol and reel is None:
        if amount % 3 != 0:
            await interaction.followup.send("The amount of symbols to "
                                            "add must be a multiple "
                                            "of 3.",
                                            ephemeral=True)
            return
    elif add_symbol and reel:
        print(f"Adding symbol: {add_symbol}")
        print(f"Amount: {amount}")
        print(f"Reel: {reel}")
        if (reel in slot_machine.reels and
                add_symbol in slot_machine.reels[reel]):
            slot_machine.reels[reel][add_symbol] += amount
        else:
            print(f"ERROR: Invalid reel or symbol '{reel}' or '{add_symbol}'")
    if add_symbol:
        print(f"Adding symbol: {add_symbol}")
        print(f"Amount: {amount}")
        if add_symbol in slot_machine.reels['reel1']:
            per_reel_amount: int = int(amount / 3)
            new_reels['reel1'][add_symbol] += per_reel_amount
            new_reels['reel2'][add_symbol] += per_reel_amount
            new_reels['reel3'][add_symbol] += per_reel_amount

            slot_machine.reels = new_reels
            print(f"Added {per_reel_amount} {add_symbol} to each reel.")
        else:
            print(f"ERROR: Invalid symbol '{add_symbol}'")
        print(slot_machine.reels)
        # if amount
    elif remove_symbol and reel:
        print(f"Removing symbol: {remove_symbol}")
        print(f"Amount: {amount}")
        print(f"Reel: {reel}")
        if (reel in slot_machine.reels and
                remove_symbol in slot_machine.reels[reel]):
            slot_machine.reels[reel][remove_symbol] -= amount
        else:
            print(f"ERROR: Invalid reel '{reel}' or symbol '{remove_symbol}'")
    elif remove_symbol:
        print(f"Removing symbol: {remove_symbol}")
        print(f"Amount: {amount}")
        if remove_symbol in slot_machine.reels['reel1']:
            per_reel_amount: int = int(amount / 3)
            new_reels['reel1'][remove_symbol] -= per_reel_amount
            new_reels['reel2'][remove_symbol] -= per_reel_amount
            new_reels['reel3'][remove_symbol] -= per_reel_amount

            slot_machine.reels = new_reels
            print(f"Removed {per_reel_amount} {remove_symbol} from each reel.")
        else:
            print(f"ERROR: Invalid symbol '{remove_symbol}'")
        print(slot_machine.reels)

    print("Saving reels...")

    slot_machine.reels = new_reels
    new_reels = slot_machine.reels
    # print(f"Reels: {slot_machine.configuration}")
    print(f"Probabilities saved.")

    # TODO Report payouts
    amount_of_symbols: int = slot_machine.count_symbols()
    reel_amount_of_symbols: int
    reels_table: str = "### Reels\n"
    for reel_name, symbols in new_reels.items():
        reel_symbols: Dict[str, int] = cast(Dict[str, int], symbols)
        symbols_table: str = ""
        symbols_and_amounts: dict_items[str, int] = reel_symbols.items()
        for symbol, amount in symbols_and_amounts:
            symbols_table += f"{symbol}: {amount}\n"
        symbols_dict: Dict[str, int] = cast(Dict[str, int], symbols)
        reel_amount_of_symbols = sum(symbols_dict.values())
        reels_table += (f"**Reel {reel_name}**\n"
                        f"**Symbol**: **Amount**\n"
                        f"{symbols_table}"
                        "**Total**\n"
                        f"{reel_amount_of_symbols}\n\n")
    probabilities: Dict[str, Float] = slot_machine.probabilities
    probabilities_table: str = "**Outcome**: **Probability**\n"
    lowest_number_float = 0.0001
    lowest_number: Float = Float(lowest_number_float)
    probability_display: str = ""
    for symbol, probability in probabilities.items():
        if Eq(probability, round(probability, Integer(4))):
            probability_display = f"{probability:.4%}"
        elif Gt(probability, lowest_number):
            probability_display = f"~{probability:.4%}"
        else:
            probability_display = f"<{lowest_number_float}%"
        probabilities_table += f"{symbol}: {probability_display}\n"

    ev: tuple[Piecewise, Piecewise] = slot_machine.calculate_expected_value()
    expected_return_ugly: Piecewise = ev[0]
    expected_return: str = (
        cast(str, pretty(expected_return_ugly))).replace("⋅", "")
    expected_total_return_ugly: Piecewise = ev[1]
    expected_total_return: str = (
        cast(str, pretty(expected_total_return_ugly,))).replace("⋅", "")
    wagers: List[int] = [
        1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11,
        25, 50, 75, 99, 100, 500, 1000, 10000, 100000, 1000000]
    rtp_dict: Dict[int, str] = {}
    rtp_display: str | None = None
    rtp: Float
    for wager in wagers:
        rtp = (
            slot_machine.calculate_rtp(Integer(wager)))
        rtp_simple: Float = cast(Float, simplify(rtp))
        if rtp == round(rtp, Integer(4)):
            rtp_display = f"{rtp:.4%}"
        else:
            if Gt(rtp_simple, lowest_number):
                rtp_display = f"~{rtp:.4%}"
            else:
                rtp_display = f"<{str(lowest_number_float)}%"
        rtp_dict[wager] = rtp_display

    rtp_table: str = "**Wager**: **RTP**\n"
    for wager_sample, rtp_sample in rtp_dict.items():
        rtp_table += f"{wager_sample}: {rtp_sample}\n"

    message_content: str = ("### Reels\n"
                            f"{reels_table}\n"
                            "### Symbols total\n"
                            f"{amount_of_symbols}\n\n\n"
                            "### Probabilities\n"
                            f"{probabilities_table}\n\n"
                            "### Expected values\n"
                            "**Expected total return**\n"
                            f"{expected_total_return}\n\n"
                            "**Expected return**\n"
                            f"{expected_return}\n"
                            '-# "W" means wager\n\n'
                            "### RTP\n"
                            f"{rtp_table}")
    print(message_content)
    await interaction.followup.send(message_content, ephemeral=close_off)
    del message_content
# endregion

# region /slots


@bot.tree.command(name="slots",
                  description="Play on a slot machine")
@app_commands.describe(insert_coins="Insert coins into the slot machine")
@app_commands.describe(private_room="Play in a private room")
@app_commands.describe(jackpot="Check the current jackpot amount")
@app_commands.describe(reboot="Reboot the slot machine")
@app_commands.describe(show_help="Show help")
@app_commands.describe(rtp="Show the return to player percentage for "
                       "a given wager")
async def slots(interaction: Interaction,
                insert_coins: int | None = None,
                private_room: bool | None = None,
                jackpot: bool = False,
                reboot: bool = False,
                show_help: bool = False,
                rtp: int | None = False) -> None:
    """
    Command to play a slot machine.

    If it's the first time the user plays, they will be offered a
    starting bonus of an amount that is decided by a die.

    Three blank emojis are displayed and then the reels will stop in a few
    seconds, or the user can stop them manually by hitting the stop buttons that
    appear. The message containing the blank emojis are updated each time a reel
    is stopped.
    If they get a net positive outcome, the amount will be added to their
    balance. If they get a net negative outcome, the loss amount will be
    transferred to the casino's account.
    See the "show_help" parameter for more information about the game.

    See the UserSaveData documentation for more information
    about 'starting_bonus_available' and 'when_last_bonus_received'. 

    Args:
    interaction  -- The interaction object representing the
                    command invocation.
    insert_coins -- Sets the stake/wager (default 1)
    private_room -- Makes the bot's messages ephemeral
                    (only visible to the invoker) (default False)
    jackpot      -- Reports the current jackpot pool (default False)
    reboot       -- Removes the invoker from active_slot_machine_players
                    (default False)
    show_help   -- Sends information about the command/game (default False)
    """
    # TODO Add TOS parameter
    # TODO Add service parameter
    # IMPROVE Make incompatible parameters not selectable together
    def grifter_supplier_check() -> bool:
        """
        Checks if the invoker is a Grifter Supplier and sends a message if they
        are.
        """
        # Check if the user has coins in GrifterSwap
        all_grifter_suppliers: List[int] = grifter_suppliers.suppliers
        is_grifter_supplier: bool = user_id in all_grifter_suppliers
        if is_grifter_supplier:
            return True
        else:
            return False

    if private_room:
        should_use_ephemeral = True
    else:
        should_use_ephemeral = False
    wager_int: int | None = insert_coins
    if wager_int is None:
        wager_int = 1
    if wager_int < 0:
        message_content = "Thief!"
        await interaction.response.send_message(
            message_content, ephemeral=False)
        return
    elif wager_int == 0:
        message_content = "Insert coins to play!"
        await interaction.response.send_message(
            message_content, ephemeral=should_use_ephemeral)
        return
    # TODO Log/stat outcomes (esp. wager amounts)
    user: User | Member = interaction.user
    user_id: int = user.id

    if show_help:
        pay_table: str = ""
        combo_events: Dict[str, ReelSymbol] = (
            slot_machine.configuration["combo_events"])
        combo_event_count: int = len(combo_events)
        for event in combo_events:
            event_name: str = event
            event_name_friendly: str = (
                slot_machine.make_friendly_event_name(event_name))
            emoji_name: str = combo_events[event]['emoji_name']
            emoji_id: int = combo_events[event]['emoji_id']
            emoji: PartialEmoji = PartialEmoji(name=emoji_name, id=emoji_id)
            row: str = (
                f"> {emoji} {emoji} {emoji}    {event_name_friendly}\n> \n")
            pay_table += row
        # strip the last ">"
        pay_table = pay_table[:pay_table.rfind("\n> ")]
        jackpot_seed: int = (
            slot_machine.configuration["combo_events"]
            ["jackpot"]["fixed_amount"])
        administrator: str = (await bot.fetch_user(administrator_id)).name
        help_message_1: str = (
            f"## {Coin} Slot Machine Help\n"
            f"Win big by playing the {Coin} Slot Machine!*\n\n"
            "### Pay table\n"
            f"{pay_table}\n"
            "\n"
            "### Fees\n"
            "> Coins inserted: Fee\n"
            f"> 1:             1 {coin}\n"
            f"> <10:        2 {coins}\n"
            "> <100:     20%\n"
            "> ≥100:     7%\n"
            "\n"
            "Fees are calculated from your total stake (the amount of coins "
            "you insert), and are deducted from your total return (your "
            "gross return.). For example, if you insert 100 coins, and win "
            "a 2X award, you get 200 coins, and then 2 coins are deducted, "
            "leaving you with 198 coins.\n"
            "\n"
            "### Rules\n"
            "You must be 18 years or older to play.\n\n"
            "### How to play\n"
            "To play, insert coins with the `insert_coin` parameter of the \n"
            "`/slots` command. Then wait for the reels to stop, or stop them "
            "yourself by hitting the stop buttons. Your goal is to get a "
            "winning combination of three symbols illustrated on the "
            "pay table.\n"
            "\n"
            "### Overview\n"
            f"The {Coin} Slot Machine has 3 reels.\n"
            f"Each reel has {combo_event_count} unique symbols.\n"
            "If three symbols match, you get an award based on the symbol, "
            "or, if you're unlucky, you lose your entire stake (see the pay "
            "table).\n"
            "\n")
        help_message_2: str = (
            "### Stake\n"
            "The amount of coins you insert is your stake. This includes the "
            "fees. The stake is the amount of coins you are willing to risk. "
            "It will determine the amount you can win, and how high the fees "
            "will be.\n"
            "\n"
            "Multiplier awards multiply your total stake before fees are "
            "deducted.\n"
            "\n"
            "If you do not specify a stake, it means you insert 1 coin and "
            "that will be your stake.\n"
            "\n"
            f"A perhaps counter-intuitive feature of the {Coin} Slot Machine "
            "is that if you do not strike a combination, you do not lose "
            "your entire stake, but only the fees. But if you get Lose wager "
            "combination, you do lose your entire stake.\n"
            "\n"
            "Any net positive outcome will be immediately added to your "
            "balance. Similarly, if you get a net negative outcome, the "
            f"loss amount will be transferred to the {Coin} Casino's "
            "account.\n"
            "\n"
            "### Jackpot\n"
            "The jackpot is a pool of coins that grows as people play the "
            "slot machine.\n"
            "If you get a jackpot-winning combination, you win the "
            "entire jackpot pool.\n"
            "\n"
            "To check the current jackpot amount, "
            "use the `jackpot` parameter.\n"
            "\n"
            f"To be eligible for the jackpot, you must insert "
            f"at least 2 {coins}. Then, a small portion of your stake will "
            "be added to the jackpot pool as a jackpot fee. For stakes "
            "between 2 and 10 coins, the jackpot fee is 1 coin. Above that, it "
            "is 1%. The jackpot fees are included in in the fees you see on "
            "the fees table.\n\n"
            f"When someone wins the jackpot, the pool is reset "
            f"to {jackpot_seed} {coins}.\n"
            "\n")
        help_message_3: str = (
            "### Fairness\n"
            "The outcome of a play is never predetermined. The slot machine "
            "uses a random number generator to determine the outcome of each "
            "reel each time you play. Some symbols are however more likely "
            "to appear than others, because each reel has a set amount of "
            "each symbol.\n"
            "\n"
            "To check the RTP (return to player) for a given stake, use "
            "the `rtp` parameter.\n"
            "\n"
            "### Contact\n"
            "If you are having issues, you can reboot the slot machine by "
            "using the reboot parameter. If you have any other issues, "
            f"please contact the {Coin} Casino staff or a Slot Machine "
            "Technician (ping Slot Machine Technician). If you need to "
            f"contact the {Coin} Casino CEO, ping {administrator}.\n"
            "\n"
            "-# *Not guaranteed. Actually, for legal reasons, nothing about "
            "this game is guaranteed.\n")
        # Use ephemeral messages unless explicitly set to False
        if private_room is False:
            should_use_ephemeral = False
        else:
            should_use_ephemeral = True
        await interaction.response.send_message(help_message_1,
                                                ephemeral=should_use_ephemeral)
        await interaction.followup.send(help_message_2,
                                        ephemeral=should_use_ephemeral)
        await interaction.followup.send(help_message_3,
                                        ephemeral=should_use_ephemeral)
        return
    elif rtp:
        wager_int = rtp
        wager = Integer(rtp)
        rtp_fraction: Float = slot_machine.calculate_rtp(wager)
        rtp_simple: Float = cast(Float, simplify(rtp_fraction))
        lowest_number_float = 0.0001
        lowest_number: Float = Float(lowest_number_float)
        rtp_display: str
        if rtp_fraction == round(rtp_fraction, Integer(4)):
            rtp_display = f"{rtp_fraction:.4%}"
        else:
            if rtp_simple > lowest_number:
                rtp_display = f"~{rtp_fraction:.4%}"
            else:
                rtp_display = f"<{lowest_number_float}%"
        coin_label = format_coin_label(wager_int)
        message_content = slot_machine.make_message(
            f"-# RTP (stake={wager_int} {coin_label}): {rtp_display}")
        if private_room is False:
            should_use_ephemeral = False
        else:
            should_use_ephemeral = True
        await interaction.response.send_message(message_content,
                                                ephemeral=should_use_ephemeral)
        return
    elif reboot:
        message_content = slot_machine.make_message(
            f"-# The {Coin} Slot Machine is restarting...")
        await interaction.response.send_message(message_content,
                                                ephemeral=should_use_ephemeral)
        del message_content
        await asyncio.sleep(4)
        # Re-initialize slot machine (reloads configuration from file)
        reinitialize_slot_machine()
        # Also update the bot configuration
        invoke_bot_configuration()
        # Also reload the other files
        reinitialize_grifter_suppliers()
        reinitialize_transfers_waiting_approval()
        # Remove invoker from active players in case they are stuck in it
        # Multiple checks are put in place to prevent cheating
        bootup_message: str = f"-# Welcome to the {Coin} Casino!"
        current_time: float = time()
        when_player_added_to_active_players: float | None = (
            active_slot_machine_players.get(user_id))
        if when_player_added_to_active_players is not None:
            seconds_since_added: float = (
                current_time - when_player_added_to_active_players)
            del current_time
            min_wait_time_to_unstuck: int = starting_bonus_timeout * 2 - 3
            print(f"User {user_id} has been in active players for "
                  f"{seconds_since_added} seconds. Minimum wait time to "
                  f"unstuck: {min_wait_time_to_unstuck} seconds.")
            if seconds_since_added < min_wait_time_to_unstuck:
                wait_time: int = (
                    math.ceil(min_wait_time_to_unstuck - seconds_since_added))
                print(f"Waiting for {wait_time} seconds "
                      f"to unstuck user {user_id}.")
                await asyncio.sleep(wait_time)
            when_player_added_double_check: float | None = (
                active_slot_machine_players.get(user_id))
            if when_player_added_double_check is not None:
                when_added_unchanged: bool = (
                    when_player_added_double_check ==
                    when_player_added_to_active_players)
                if when_added_unchanged:
                    # If the timestamp has changed, that means that the user
                    # has run /slots while the machine is "rebooting",
                    # which could indicate that they are trying to cheat.
                    # If their ID is still in the dictionary and the timestamp
                    # hasn't changed,
                    # remove the user from the dictionary
                    user_name: str = user.name
                    active_slot_machine_players.pop(user_id)
                    print(f"User {user_name} ({user_id}) removed from "
                          "active players.")
                    del user_name
                else:
                    print("Timestamp changed. "
                          "Will not remove user from active players.")
                    bootup_message = (f"Cheating is illegal.\n"
                                      f"-# Do not use the {Coin} Slot Machine "
                                      "during reboot.")
            else:
                print("User not in active players anymore.")
        else:
            print("User not in active players.")
        message_content = slot_machine.make_message(bootup_message)
        await interaction.edit_original_response(content=message_content)
        del message_content
        return
    elif jackpot:
        # Check the jackpot amount
        jackpot_pool: int = slot_machine.jackpot
        coin_label: str = format_coin_label(jackpot_pool)
        message_header: str = slot_machine.header
        message_content = (f"{message_header}\n"
                           f"-# JACKPOT: {jackpot_pool} {coin_label}.")
        del coin_label
        await interaction.response.send_message(message_content,
                                                ephemeral=should_use_ephemeral)
        return

    # Check if user is already playing on a slot machine
    wait_seconds_left: int = 2
    while user_id in active_slot_machine_players and wait_seconds_left > 0:
        await asyncio.sleep(1)
        wait_seconds_left -= 1
    # If the user is still in the active players list, send a message and return
    if user_id in active_slot_machine_players:
        await interaction.response.send_message(
            "You are only allowed to play "
            "on one slot machine at a time.\n"
            "-# If you're having issues, please try rebooting the slot machine "
            f"before contacting the {Coin} Casino staff.",
            ephemeral=True)
        return
    else:
        start_play_timestamp: float = time()
        active_slot_machine_players[user_id] = start_play_timestamp
        del start_play_timestamp

    user_name: str = user.name
    save_data: UserSaveData = (
        UserSaveData(user_id=user_id, user_name=user_name))
    starting_bonus_available: bool | float = save_data.starting_bonus_available

    # Check balance
    user_id_hash: str = sha256(str(user_id).encode()).hexdigest()
    user_balance: int | None = blockchain.get_balance(user=user_id_hash)
    if user_balance is None:
        user_balance = 0

    has_played_before: bool = save_data.has_visited_casino
    new_bonus_wait_complete: bool = (
        (isinstance(starting_bonus_available, float)) and
        (time() >= starting_bonus_available))
    is_grifter_supplier = False
    if not has_played_before:
        starting_bonus_available = True
    elif (user_balance <= 0):
        is_grifter_supplier = grifter_supplier_check()
        if is_grifter_supplier:
            message_content: str = (
                f"Welcome back! We give free coins to customers who do not "
                "have any. However, we request that you first delete "
                "your GrifterSwap account.\n"
                "Here's how you can do it:\n"
                "See your GrifterSwap balance with `!balance`, withdraw all "
                "your coins with \n"
                "`!withdraw <currency> <amount>`, and then use `!suppliers` to "
                "prove you're no longer a supplier.")
            await interaction.response.send_message(
                message_content, ephemeral=should_use_ephemeral)
            del message_content
            active_slot_machine_players.pop(user_id)
            return

    if ((user_balance <= 0) and
        (isinstance(starting_bonus_available, bool)) and
            (starting_bonus_available is False)):
        # The `isinstance()` check is technically unnecessary,
        # but is included for clarity

        # See the UserSaveData documentation for information
        # about `starting_bonus_available` and `when_last_bonus_received`.
        when_last_bonus_received: float | None = (
            save_data.when_last_bonus_received)
        if when_last_bonus_received is None:
            starting_bonus_available = True
        else:
            min_seconds_between_bonuses: int = (
                slot_machine.next_bonus_wait_seconds)
            when_eligible_for_bonus: float = (
                when_last_bonus_received + min_seconds_between_bonuses)
            is_eligible_for_bonus: bool = time() >= when_eligible_for_bonus
            if is_eligible_for_bonus:
                starting_bonus_available = True
            else:
                starting_bonus_available = when_eligible_for_bonus
                save_data.starting_bonus_available = when_eligible_for_bonus
                min_time_between_bonuses: str = format_timespan(
                    min_seconds_between_bonuses)
                message_content = (
                    f"Come back in {min_time_between_bonuses} and "
                    "we will give you some coins to play with.")
                await interaction.response.send_message(
                    message_content, ephemeral=should_use_ephemeral)
                del message_content
                active_slot_machine_players.pop(user_id)
                return
    elif ((user_balance <= 0) and
          (isinstance(starting_bonus_available, float)) and
          (time() < starting_bonus_available)):
        seconds_left = int(starting_bonus_available - time())
        time_left: str = format_timespan(seconds_left)
        message_content: str = (f"You are out of {coins}. Come back "
                                f"in {time_left} to get some coins.")
        # Use ephemeral unless explicitly set to False
        if private_room is False:
            should_use_ephemeral = False
        else:
            should_use_ephemeral = True
        await interaction.response.send_message(
            message_content, ephemeral=should_use_ephemeral)
        del message_content
        active_slot_machine_players.pop(user_id)
        return

    main_bonus_requirements_passed: bool = (
        new_bonus_wait_complete or
        starting_bonus_available == True)
    if main_bonus_requirements_passed:
        is_grifter_supplier = grifter_supplier_check()
    should_give_bonus: bool = (
        main_bonus_requirements_passed and not is_grifter_supplier)
    if should_give_bonus:
        # Send message to inform user of starting bonus
        starting_bonus_awards: Dict[int, int] = {
            1: 50, 2: 100, 3: 200, 4: 300, 5: 400, 6: 500}
        starting_bonus_table: str = "> **Die roll**\t**Amount**\n"
        for die_roll, amount in starting_bonus_awards.items():
            starting_bonus_table += f"> {die_roll}\t\t\t\t{amount}\n"
        message_preamble: str
        if has_played_before:
            message_preamble = (f"Welcome back! You spent all your {coins} "
                                "and we want to give you another chance.\n"
                                f"Roll the die and we will give you a bonus.")
        else:
            message_preamble = (f"Welcome to the {Coin} Casino! This seems "
                                "to be your first time here.\n"
                                "A standard 6-sided die will decide your "
                                "starting bonus.")
        # TODO Move the table to a separate message
        message_content: str = (f"{message_preamble}\n"
                                "The possible outcomes are displayed below.\n\n"
                                f"{starting_bonus_table}")

        starting_bonus_view = (
            StartingBonusView(invoker=user,
                              starting_bonus_awards=starting_bonus_awards,
                              save_data=save_data,
                              log=log,
                              interaction=interaction))
        await interaction.response.send_message(content=message_content,
                                                view=starting_bonus_view)
        wait: bool = await starting_bonus_view.wait()
        timed_out: bool = wait is True
        if not timed_out:
            save_data.has_visited_casino = True
            current_time: float = time()
            save_data.when_last_bonus_received = current_time
        active_slot_machine_players.pop(user_id)
        return

    del has_played_before

    if user_balance < wager_int:
        coin_label_w: str = format_coin_label(wager_int)
        coin_label_b: str = format_coin_label(user_balance)
        message_content = (f"You do not have enough {coins} "
                           f"to stake {wager_int} {coin_label_w}.\n"
                           f"Your current balance is {user_balance} {coin_label_b}.")
        await interaction.response.send_message(
            content=message_content, ephemeral=True)
        del coin_label_w
        del coin_label_b
        del message_content
        if user_id in active_slot_machine_players:
            active_slot_machine_players.pop(user_id)
        return

    fees_dict: Dict[str, int | float] = slot_machine.configuration["fees"]
    low_wager_main_fee: int = (
        cast(int, fees_dict["low_wager_main"]))
    medium_wager_main_fee: float = (
        cast(float, fees_dict["medium_wager_main"]))
    high_wager_main_fee: float = (
        cast(float, fees_dict["high_wager_main"]))
    low_wager_jackpot_fee: int = (
        cast(int, fees_dict["low_wager_jackpot"]))
    medium_wager_jackpot_fee: float = (
        cast(float, fees_dict["medium_wager_jackpot"]))
    high_wager_jackpot_fee: float = (
        cast(float, fees_dict["high_wager_jackpot"]))

    jackpot_fee_paid: bool = (
        wager_int >= (low_wager_main_fee + low_wager_jackpot_fee))
    no_jackpot_mode: bool = False if jackpot_fee_paid else True
    jackpot_fee: int
    main_fee: int
    if no_jackpot_mode:
        # IMPROVE Make min_wager config keys
        main_fee = low_wager_main_fee
        jackpot_fee = 0
    elif wager_int < 10:
        main_fee = low_wager_main_fee
        jackpot_fee = low_wager_jackpot_fee
    elif wager_int < 100:
        main_fee_unrounded: float = wager_int * medium_wager_main_fee
        main_fee = round(main_fee_unrounded)
        jackpot_fee_unrounded: float = wager_int * medium_wager_jackpot_fee
        jackpot_fee = round(jackpot_fee_unrounded)
    else:
        main_fee_unrounded: float = wager_int * high_wager_main_fee
        main_fee = round(main_fee_unrounded)
        jackpot_fee_unrounded: float = wager_int * high_wager_jackpot_fee
        jackpot_fee = round(jackpot_fee_unrounded)
    fees: int = jackpot_fee + main_fee

    spin_emojis: SpinEmojis = slot_machine.configuration["reel_spin_emojis"]
    spin_emoji_1_name: str = spin_emojis["spin1"]["emoji_name"]
    spin_emoji_1_id: int = spin_emojis["spin1"]["emoji_id"]
    spin_emoji_1 = PartialEmoji(name=spin_emoji_1_name,
                                id=spin_emoji_1_id,
                                animated=True)
    reels_row: str = f"{spin_emoji_1}\t\t{spin_emoji_1}\t\t{spin_emoji_1}"
    wager_row: str = f"-# Coin: {wager_int}"
    fees_row: str = f"-# Fee: {fees}"
    slots_message: str = slot_machine.make_message(text_row_1=wager_row,
                                                   text_row_2=fees_row,
                                                   reels_row=reels_row)

    slot_machine_view = SlotMachineView(invoker=user,
                                        slot_machine=slot_machine,
                                        text_row_1=wager_row,
                                        text_row_2=fees_row,
                                        interaction=interaction)
    await interaction.response.send_message(content=slots_message,
                                            view=slot_machine_view,
                                            ephemeral=should_use_ephemeral)
    del slots_message
    # Auto-stop reel timer
    # Views have built-in timers that you can wait for with the wait() method,
    # but since we have tasks to upon the timer running out, that won't work
    # There is probably a way to do it with just the view, but I don't know how
    previous_buttons_clicked_count = 0
    let_the_user_stop = True
    user_irresonsive: bool
    user_stopped_clicking: bool
    all_buttons_clicked: bool
    while let_the_user_stop:
        buttons_clicked_count = 0
        await asyncio.sleep(3.0)
        for button in slot_machine_view.stop_reel_buttons:
            button_clicked: bool = button.disabled
            if button_clicked:
                buttons_clicked_count += 1
        user_irresonsive = buttons_clicked_count == 0
        all_buttons_clicked = buttons_clicked_count == 3
        user_stopped_clicking = (
            buttons_clicked_count == previous_buttons_clicked_count)
        if (user_irresonsive or all_buttons_clicked or user_stopped_clicking):
            let_the_user_stop = False
        previous_buttons_clicked_count: int = buttons_clicked_count
    await slot_machine_view.start_auto_stop()

    # Get results
    results: ReelResults = slot_machine_view.reels_results

    # Create some variables for the outcome messages
    slot_machine_reels_row: str = slot_machine_view.message_reels_row
    del slot_machine_view

    # Calculate win amount
    event_name: str
    event_name_friendly: str
    # Win money is the amount of money that the event will award
    # (not usually the same as net profit or net return)
    win_money: int
    event_name, event_name_friendly, win_money = (
        slot_machine.calculate_award_money(wager=wager_int,
                                           results=results))

    # Generate outcome messages
    event_message: str | None = None
    # print(f"event_name: '{event_name}'")
    # print(f"event_name_friendly: '{event_name_friendly}'")
    # print(f"win money: '{win_money}'")
    coin_label_wm: str = format_coin_label(win_money)
    if event_name == "jackpot_fail":
        jackpot_pool: int = slot_machine.jackpot
        coin_label_fee: str = format_coin_label(jackpot_pool)
        coin_label_jackpot: str = format_coin_label(jackpot_pool)
        event_message = (f"{event_name_friendly}! Unfortunately, you did "
                         "not pay the jackpot fee of "
                         f"{jackpot_fee} {coin_label_fee}, meaning "
                         "that you did not win the jackpot of "
                         f"{jackpot_pool} {coin_label_jackpot}. "
                         "Better luck next time!")
        del coin_label_fee
        del coin_label_jackpot
    elif event_name == "standard_lose":
        event_message = None
    else:
        # The rest of the possible events are win events
        event_message = (f"{event_name_friendly}! "
                         f"You won {win_money} {coin_label_wm}!")

    # Calculate net return to determine who should get money (house or player)
    # and to generate collect screen message and an informative log line
    # Net return is the loss or profit of the player (wager excluded)
    net_return: int
    # Total return is the total amount of money that the player will get
    # get back (wager included)
    total_return: int
    log_line: str = ""
    if event_name == "lose_wager":
        event_message = (f"You lost your entire "
                         f"stake of {wager_int} {coin_label_wm}. "
                         "Better luck next time!")
        net_return = -wager_int
        total_return = 0
    net_return = win_money - main_fee - jackpot_fee
    total_return = wager_int + win_money - main_fee - jackpot_fee
    # print(f"wager: {wager_int}")
    # print(f"standard_fee: {main_fee}")
    # print(f"jackpot_fee: {jackpot_fee}")
    # print(f"jackpot_fee_paid: {jackpot_fee_paid}")
    # print(f"jackpot_mode: {jackpot_mode}")
    # print(f"win_money: {win_money}")
    # print(f"net_return: {net_return}")
    # print(f"total_return: {total_return}")
    coin_label_nr: str = format_coin_label(net_return)
    if net_return > 0:
        log_line = (f"{user_name} ({user_id}) won the {event_name} "
                    f"({event_name_friendly}) reward "
                    f"of {win_money} {coin_label_wm} and profited "
                    f"{net_return} {coin_label_nr} on the {Coin} Slot Machine.")
    elif net_return == 0:
        if event_name == "jackpot_fail":
            # This should not happen with default config
            log_line = (f"{user_name} ({user_id}) got the {event_name} "
                        f"({event_name_friendly}) event without paying the "
                        "jackpot fee, so they did not win the jackpot, "
                        "yet they neither lost any coins nor profited.")
        elif event_name == "lose_wager":
            # This should not happen with default config
            log_line = (f"{user_name} ({user_id}) got "
                        f"the {event_name} event ({event_name_friendly}) "
                        "and lost their entire wager of "
                        f"{wager_int} {coin_label_nr} on "
                        f"the {Coin} Slot Machine, "
                        "yet they neither lost any coins nor profited.")
        elif win_money > 0:
            # With the default config, this will happen if the fees are higher
            # than the win money
            log_line = (f"{user_name} ({user_id}) won the {event_name} "
                        f"({event_name_friendly}) reward "
                        f"of {win_money} {coin_label_wm} on the {Coin} "
                        "slot machine, but made no profit.")
        else:
            # This should not happen without win money with the default config
            # (because of the fees)
            log_line = (f"{user_name} ({user_id}) made no profit on the "
                        f"{Coin} Slot Machine.")
    else:
        # if net return is negative, the user lost money
        if event_name == "lose_wager":
            log_line = (f"{user_name} ({user_id}) got the {event_name} event "
                        f"({event_name_friendly}) and lost their entire wager "
                        f"of {wager_int} {coin_label_nr} on the "
                        f"{Coin} Slot Machine.")
        if event_name == "jackpot_fail":
            log_line = (f"{user_name} ({user_id}) lost {-net_return} "
                        f"{coin_label_nr} on the {Coin} Slot Machine by "
                        f"getting the {event_name} ({event_name_friendly}) "
                        "event without paying the jackpot fee.")
        elif win_money > 0:
            # turn -net_return into a positive number
            log_line = (f"{user_name} ({user_id}) won "
                        f"{win_money} {coin_label_wm} on "
                        f"the {event_name} ({event_name_friendly}) reward, "
                        f"but lost {-net_return} {coin_label_nr} in net return "
                        f"on the {Coin} Slot Machine.")
        else:
            log_line = (f"{user_name} ({user_id}) lost "
                        f"{-net_return} {coin_label_nr} on "
                        f"the {Coin} Slot Machine.")
    del coin_label_wm

    # Generate collect message
    coin_label_tr: str = format_coin_label(total_return)
    collect_message: str | None = None
    if (total_return > 0):
        collect_message = (f"-# You collect {total_return} {coin_label_tr}.")
    else:
        # collect_message = None
        collect_message = "So close!"
    del coin_label_nr

    # TODO Move code to SlotMachine.make_message
    if event_message or collect_message:
        # Display outcome messages
        outcome_message_line_1: str | None = None
        outcome_message_line_2: str | None = None
        if event_message and not collect_message:
            outcome_message_line_1 = event_message
        elif collect_message and not event_message:
            outcome_message_line_1 = collect_message
        elif event_message and collect_message:
            outcome_message_line_1 = event_message
            outcome_message_line_2 = collect_message
        del event_message
        del collect_message

        # edit original message
        slots_message_outcome: str = slot_machine.make_message(
            text_row_1=outcome_message_line_1,
            text_row_2=outcome_message_line_2,
            reels_row=slot_machine_reels_row)
        del outcome_message_line_1
        del outcome_message_line_2
        del slot_machine_reels_row
        await interaction.edit_original_response(content=slots_message_outcome)
        del slots_message_outcome

    # Transfer and log
    last_block_error = False
    if net_return != 0:
        sender: User | Member | int
        receiver: User | Member | int
        log_timestamp: float = 0.0
        transfer_amount: int
        if net_return > 0:
            transfer_amount = net_return
            sender = casino_house_id
            receiver = user
        else:
            sender = user
            receiver = casino_house_id
            # flip to positive value (transferring a negative amount would mean
            # reducing the receiver's balance)
            transfer_amount = -net_return
        await add_block_transaction(
            blockchain=blockchain,
            sender=sender,
            receiver=receiver,
            amount=transfer_amount,
            method="slot_machine"
        )
        del sender
        del receiver
        del transfer_amount
        last_block_timestamp: float | None = get_last_block_timestamp()
        if last_block_timestamp is None:
            print("ERROR: Could not get last block timestamp.")
            log_timestamp = time()
            log_line += ("(COULD NOT GET LAST BLOCK TIMESTAMP; "
                         "USING CURRENT TIME; WILL NOT RESET JACKPOT)")
            last_block_error = True
        else:
            log_timestamp = last_block_timestamp
        del last_block_timestamp
    else:
        log_timestamp = time()
    log.log(line=log_line, timestamp=log_timestamp)
    del log_timestamp
    del log_line

    coins_left: int = user_balance + net_return
    if coins_left <= 0 and starting_bonus_available is False:
        next_bonus_time_left: str = format_timespan(
            slot_machine.next_bonus_wait_seconds)
        invoker: str = user.mention
        all_grifter_suppliers: List[int] = grifter_suppliers.suppliers
        is_grifter_supplier: bool = user_id in all_grifter_suppliers
        if is_grifter_supplier:
            message_content = (f"{invoker} You're all out of {coins}!\n"
                               "To customers who run out of coins, we usually give "
                               "some for free. However, we request that you please "
                               "delete your GrifterSwap account first.\n"
                               "Here's how you can do it:\n"
                               "See your GrifterSwap balance with `!balance`, "
                               "withdraw all your coins with\n"
                               "`!withdraw <currency> <amount>`, "
                               "and then use `!suppliers` to prove you're no longer "
                               "a supplier.")
            await interaction.followup.send(content=message_content,
                                            ephemeral=should_use_ephemeral)
            del message_content
        else:
            message_content: str = (f"{invoker} You're all out of {coins}!\n"
                                    f"Come back in {next_bonus_time_left} "
                                    "for a new starting bonus.")
            del next_bonus_time_left
            await interaction.followup.send(content=message_content,
                                            ephemeral=should_use_ephemeral)
            del message_content
            next_bonus_point_in_time: float = (
                time() + slot_machine.next_bonus_wait_seconds)
            save_data.starting_bonus_available = next_bonus_point_in_time
            del next_bonus_point_in_time

    if user_id in active_slot_machine_players:
        active_slot_machine_players.pop(user_id)

    if last_block_error:
        # send message to admin
        administrator: str = (await bot.fetch_user(administrator_id)).name
        await interaction.response.send_message("An error occurred. "
                                                f"{administrator} pls fix.")
        await terminate_bot()
    del last_block_error

    if event_name == "jackpot":
        # Reset the jackpot
        combo_events: Dict[str, ReelSymbol] = (
            slot_machine.configuration["combo_events"])
        jackpot_seed: int = combo_events["jackpot"]["fixed_amount"]
        slot_machine.jackpot = jackpot_seed
    else:
        slot_machine.jackpot += 1
# endregion

# region /mining


@bot.tree.command(name="mining",
                  description="Configure mining settings")
@app_commands.describe(disable_reaction_messages="Stop the bot from messaging "
                       "new players when you mine their messages")
@app_commands.describe(stats="Show your mining stats")
@app_commands.describe(user="User to display mining stats for")
@app_commands.describe(incognito="Set whether the output of this command "
                       "should be visible only to you")
async def mining(interaction: Interaction,
                 disable_reaction_messages: bool | None = None,
                 stats: bool | None = None,
                 user: User | Member | None = None,
                 incognito: bool | None = None) -> None:
    """
    Command to configure mining settings.

    Args:
    interaction              -- The interaction object representing the
                                command invocation.
    disable_reaction_messages -- Disable reaction messages
    """
    should_use_ephemeral: bool
    invoker: User | Member = interaction.user
    if ((disable_reaction_messages is not None) and
        (user is not None) and
            (user != invoker)):
        message_content: str = ("You cannot set the mining settings for "
                                "someone else.")
        await interaction.response.send_message(
            message_content, ephemeral=True)
        del message_content
        return
    if (disable_reaction_messages is not None) and (stats is not None):
        message_content: str = ("You cannot set the mining settings and "
                                "view stats at the same time.")
        await interaction.response.send_message(
            message_content, ephemeral=True)
        return
    if disable_reaction_messages is not None:
        invoker_id: int = invoker.id
        invoker_name: str = invoker.name
        save_data: UserSaveData = UserSaveData(user_id=invoker_id,
                                               user_name=invoker_name)
        save_data.mining_messages_enabled = not disable_reaction_messages
        del save_data
        message_content: str
        if disable_reaction_messages is True:
            message_content = ("I will no longer message new players "
                               "when you mine their messages.")
        else:
            message_content: str = ("I will message new players when you mine "
                                    "their messages. Thank you for "
                                    f"helping the {Coin} network grow!")
        if incognito is False:
            should_use_ephemeral = False
        else:
            should_use_ephemeral = True
        await interaction.response.send_message(
            message_content, ephemeral=should_use_ephemeral)
        del message_content
        return
    elif stats:
        user_to_check: User | Member
        user_parameter_used: bool = user is not None
        if user_parameter_used:
            user_to_check = user
        else:
            invoker: User | Member = interaction.user
            user_to_check = invoker
        user_to_check_id: int = user_to_check.id
        user_to_check_name: str = user_to_check.name
        user_to_check_mention: str = user_to_check.mention
        save_data: UserSaveData = UserSaveData(user_id=user_to_check_id,
                                               user_name=user_to_check_name)
        messages_mined: List[int] = (
            cast(List[int], save_data.load("messages_mined")))
        messages_mined_count: int = len(messages_mined)
        message_content: str
        coin_emoji = PartialEmoji(
            name=coin_emoji_name, id=coin_emoji_id)
        coin_label: str = format_coin_label(messages_mined_count)
        if messages_mined_count == 0 and user_parameter_used:
            message_content = (
                f"{user_to_check_mention} has not mined any {coins} yet.")
        elif messages_mined_count == 0:
            message_content = (f"You have not mined any {coins} yet. "
                               f"To mine a {coins} for someone, "
                               f"react {coin_emoji} to their message.")
        elif user_parameter_used:
            message_content = (
                f"{user_to_check_mention} has mined {messages_mined_count} "
                f"{coin_label} for others.")
        else:
            message_content = (
                f"You have mined {messages_mined_count} {coin_label} "
                "for others. Keep up the good work!")
        if incognito is True:
            should_use_ephemeral = True
        else:
            should_use_ephemeral = False
        await interaction.response.send_message(
            message_content, ephemeral=should_use_ephemeral,
            allowed_mentions=AllowedMentions.none())
        del message_content
        return
    elif user:
        message_content: str = ("The `user` parameter is meant to be used "
                                "with the `stats` parameter.")
        await interaction.response.send_message(
            message_content, ephemeral=True)
        del message_content
        return
    elif incognito:
        message_content: str = ("The `incognito` parameter is meant to be used "
                                "with the `stats` "
                                "or `disable_reaction_messages` parameter.")
        await interaction.response.send_message(
            message_content, ephemeral=True)
        return
    else:
        message_content: str = (
            "You must provide a parameter to this command.")
        await interaction.response.send_message(message_content, ephemeral=True)
        del message_content
        return
# endregion

# region /about_coin


@bot.tree.command(name=f"about_{coin.lower()}",
                  description=f"About {coin}")
async def about_coin(interaction: Interaction) -> None:
    """
    Command to display information about the coin.

    Args:
    interaction -- The interaction object representing the
                     command invocation.
     """
    coin_emoji = PartialEmoji(name=coin_emoji_name, id=coin_emoji_id)
    casino_channel: (VoiceChannel | StageChannel | ForumChannel |
                     TextChannel | CategoryChannel | Thread |
                     PrivateChannel |
                     None) = bot.get_channel(casino_channel_id)
    if isinstance(casino_channel, PrivateChannel):
        raise ValueError("casino_channel is a private channel.")
    elif casino_channel is None:
        raise ValueError("casino_channel is None.")
    casino_channel_mention: str = casino_channel.mention
    message_content: str = (f"## {Coin}\n"
                            f"{Coin} is a proof-of-yapping cryptocurrency "
                            f"that lives on the {blockchain_name}.\n"
                            f"To mine a {coin} for someone, react {coin_emoji} "
                            "to their message.\n"
                            "Check your balance by typing `/balance` in "
                            "the chat.\n"
                            "\n"
                            f"New players will be informed only once about {coin}. "
                            "But if you prefer that the bot does not reply to "
                            "new players when you mine their messages, type\n"
                            "`/mining disable_reaction_messages: True`.\n"
                            "\n"
                            f"You should come visit the {casino_channel_mention} "
                            "some time. You can play on the slot machines "
                            "there with the `/slots` command.\n"
                            "If you want to know more about the slot machines, "
                            "type `/slots show_help: True`.")
    await interaction.response.send_message(message_content, ephemeral=True)
    del message_content
# endregion

# region /aml approve


@aml_group.command(name="approve",
                   description="Approve transactions that require "
                   "manual approval")
async def approve(interaction: Interaction) -> None:
    """
    Command to approve or decline large transactions.
    """
    invoker_has_aml_role: bool = test_invoker_is_aml_officer(interaction)
    if not invoker_has_aml_role:
        message_content: str = "You are not an AML officer."
        await interaction.response.send_message(message_content)
        del message_content
        return

    invoker: User | Member = interaction.user
    invoker_name: str = invoker.name
    invoker_id: int = invoker.id
    transfers_list: List[TransactionRequest] = transfers_waiting_approval.load()
    has_sent_message = False
    for transfer in transfers_list:
        sender_id: int = transfer["sender_id"]
        sender: User | None = bot.get_user(sender_id)
        if sender is None:
            print(f"ERROR: Could not get user with ID {transfer['sender_id']}")
            continue
        sender_mention: str = sender.mention
        sender_id: int = transfer["sender_id"]
        receiver_id: int = transfer["receiver_id"]
        receiver: User | None = bot.get_user(receiver_id)
        if receiver is None:
            print("ERROR: Could not get user "
                  f"with ID {transfer['receiver_id']}")
            continue
        receiver_mention: str = receiver.mention
        amount: int = transfer["amount"]
        channel_id: int = transfer["channel_id"]
        channel: (VoiceChannel | StageChannel | ForumChannel | TextChannel |
                  CategoryChannel | Thread | PrivateChannel
                  | None) = bot.get_channel(channel_id)
        if channel is None:
            print("ERROR: channel is None.")
            continue
        elif isinstance(channel,
                        (PrivateChannel, ForumChannel, CategoryChannel)):
            # [ ] Test
            print(f"ERROR: channel is a {type(channel).__name__}.")
            continue
        transfer_message_id: int = transfer["message_id"]
        transfer_message: Message = (
            await channel.fetch_message(transfer_message_id))
        if not isinstance(transfer_message, Message):
            print(f"ERROR: Could not get message "
                  f"with ID {transfer_message_id}")
            continue
        purpose: str = transfer["purpose"]
        request_timestamp: float = transfer["request_timestamp"]
        log_timestamp: float = time()
        time_elapsed: float = log_timestamp - request_timestamp
        time_elapsed_friendly: str = format_timespan(time_elapsed)
        transfer_message_link: str = transfer_message.jump_url
        message_content = (f"Sender: {sender_mention}\n"
                           f"Receiver: {receiver_mention}\n"
                           f"Amount: {amount} {coins}\n"
                           f"When: {time_elapsed_friendly} ago\n"
                           f"Purpose: \"{purpose}\"\n"
                           f"{transfer_message_link}")
        if not has_sent_message:
            # Use interaction.response.send_message
            aml_view = AmlView(
                interaction=interaction,
                initial_message=message_content)
            await interaction.response.send_message(
                content=message_content,
                view=aml_view,
                allowed_mentions=AllowedMentions.none())
            has_sent_message = True
        else:
            # Requires interaction.followup.send
            aml_view = AmlView(
                interaction=interaction,
                initial_message=message_content)
            followup_message: Message | None = await interaction.followup.send(
                content=message_content,
                view=aml_view,
                allowed_mentions=AllowedMentions.none())
            aml_view.followup_message = followup_message
        wait: bool = await aml_view.wait()
        timed_out: bool = True if wait else False
        if timed_out:
            return
        transaction_approved: bool = aml_view.approved
        request_timestamp_friendly: str = (
            format_timestamp(request_timestamp, time_zone))
        log_timestamp = time()
        action: str
        if transaction_approved:
            action = "approved"
        else:
            action = "declined"
        log_message: str = (f"AML officer {invoker_name} ({invoker_id}) "
                            f"{action} {sender} ({sender_id})'s transfer "
                            f"of {amount} {coins} "
                            f"to {receiver} ({receiver_id}) "
                            f"dated {request_timestamp_friendly}.")
        del action
        log.log(log_message, log_timestamp)
        del log_message
        if transaction_approved:
            await transfer_coins(
                sender=sender, receiver=receiver, amount=amount,
                method="transfer_aml", channel_id=channel_id)
        else:
            # TODO Let AML officer provide a reason for declining the transaction
            coin_label: str = format_coin_label(amount)
            message_content = (
                f"{sender_mention} Your transfer of {amount} {coin_label} "
                f"to {receiver_mention} has been declined by an AML officer.\n"
                f"{transfer_message_link}")
            await channel.send(message_content)
            del message_content
        transfers_waiting_approval.remove(transfer)
    message_content = "All transactions have been processed."
    if not has_sent_message:
        await interaction.response.send_message(message_content)
    else:
        await interaction.followup.send(message_content)
    del message_content
# endregion

# region /aml block


@aml_group.command(name="block_receivals",
                   description=f"Block a user from receiving {coins}")
@app_commands.describe(user=(f"User to block from receiving {coins}"))
@app_commands.describe(blocked=(f"Set whether the user should be blocked "
                                f"from receiving {coins}"))
@app_commands.describe(reason="Reason for blocking user from "
                       f"receiving {coins}")
async def block_receivals(interaction: Interaction,
                          user: User | Member,
                          blocked: bool | None = None,
                          reason: str | None = None) -> None:
    """
    Command to approve large transactions.
    """
    # TODO Add parameter to check reason for block
    if blocked and not reason:
        message_content: str = ("You must provide a reason for blocking "
                                "the user from receiving coins.")
        await interaction.response.send_message(message_content, ephemeral=True)
        del message_content
        return

    invoker_has_aml_role: bool = test_invoker_is_aml_officer(interaction)
    if not invoker_has_aml_role:
        message_content: str = "You are not an AML officer."
        await interaction.response.send_message(message_content)
        del message_content
        return

    user_id: int = user.id
    user_name: str = user.name
    user_mention: str = user.mention
    user_save_data = UserSaveData(user_id=user_id, user_name=user_name)
    message_content: str
    if blocked is None:
        is_blocked: bool = user_save_data.blocked_from_receiving_coins
        blocked_or_not_blocked: (
            Literal['blocked'] | Literal['not blocked']) = (
            "blocked" if is_blocked else "not blocked")
        message_content = (f"User {user_mention} is currently "
                           f"{blocked_or_not_blocked} from receiving {coins}.")
    else:
        blocked_or_unblocked: Literal['blocked'] | Literal['unblocked'] = (
            "blocked" if blocked else "unblocked")
        user_save_data.blocked_from_receiving_coins = blocked
        if blocked:
            user_save_data.blocked_from_receiving_coins_reason = reason
        else:
            user_save_data.blocked_from_receiving_coins_reason = None
        message_content = (f"User {user_mention} has been "
                           f"{blocked_or_unblocked} from receiving {coins}.")
    await interaction.response.send_message(
        message_content, allowed_mentions=AllowedMentions.none())
    del message_content
    return
# endregion

# region /aml decrpyt tx


@aml_group.command(name="decrypt_spreadsheet",
                   description=f"Block a user from receiving {coins}")
@app_commands.describe(user="Filter transactions by user",
                       user_name="Filter transactions by user name")
async def decrypt_spreadsheet(interaction: Interaction,
                              user: User | Member | None = None,
                              user_name: str | None = None) -> None:
    if decrypted_transactions_spreadsheet is None:
        message_content: str = (
            "Could not make a decrypted transactions spreadsheet.")
        await interaction.response.send_message(
            message_content, ephemeral=True)
        del message_content
        raise ValueError("decrypted_transactions_spreadsheet is None.")
    user_id: int | None = None
    message_content: str
    if user or user_name:
        user_formatted: str
        if user and user_name:
            user_user_name: str = user.name
            if user_name != user_user_name:
                message_content = (
                    "Using both the `user` and the `user_name` parameter "
                    "is not supported.")
                await interaction.response.send_message(
                    message_content, ephemeral=True)
                del message_content
                return

        if user:
            user_id = user.id
            user_formatted = user.mention
        else:
            user_name = cast(str, user_name)
            user_formatted = user_name
        message_content = ("Here is the decrypted transactions history "
                           f"for {user_formatted}.")
    else:
        message_content = (
            "The transactions spreadsheet has been decrypted.")
    try:
        decrypted_transactions_spreadsheet.decrypt(user_id, user_name)
        spreadsheet_path: Path = (
            decrypted_transactions_spreadsheet.decrypted_spreadsheet_path)
        with open(spreadsheet_path, 'rb') as f:
            decrypted_transactions_spreadsheet_file = File(f)
            await interaction.response.send_message(message_content,
                                                    file=decrypted_transactions_spreadsheet_file,
                                                    allowed_mentions=AllowedMentions.none())
    except Exception as e:
        error_message: str = ("An error occurred while decrypting the "
                              f"transactions spreadsheet: {e}")
        print(f"ERROR: {error_message}")
        await interaction.response.send_message(
            error_message, ephemeral=True)
        del error_message
        raise e
    del message_content
    return
# endregion

# region Main
# TODO Track reaction removals
# TODO Leaderboard
# TODO Add casino jobs
# TODO Add more games

if DISCORD_TOKEN:
    bot.run(DISCORD_TOKEN)
else:
    error_message: str = ("ERROR: DISCORD_TOKEN is not set "
                          "in the environment variables.")
    raise ValueError(error_message)
# endregion
