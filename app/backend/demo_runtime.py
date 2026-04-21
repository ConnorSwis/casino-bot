import asyncio
import hashlib
import logging
import mimetypes
from contextlib import suppress
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import discord
from discord.ext import commands
from discord.ext.commands.view import StringView

from app.config import config
from app.discord_bot.bot import register_cogs

logger = logging.getLogger(__name__)

DEMO_ALLOWED_COMMANDS = ("help", "money", "blackjack", "war", "slots")
DEMO_ALLOWED_COMMAND_SET = set(DEMO_ALLOWED_COMMANDS)


REACTION_ACTIONS: dict[str, tuple[str, str]] = {
    "🇭": ("Hit", "primary"),
    "🇸": ("Stand", "secondary"),
    "🇩": ("Double", "primary"),
    "✂️": ("Split", "secondary"),
    "🏳️": ("Surrender", "danger"),
    "✅": ("Buy Insurance", "primary"),
    "❌": ("Skip", "secondary"),
}


def _button_style_name(style: discord.ButtonStyle) -> str:
    if style is discord.ButtonStyle.primary:
        return "primary"
    if style is discord.ButtonStyle.danger:
        return "danger"
    return "secondary"


def _guess_content_type(filename: str) -> str:
    guessed, _ = mimetypes.guess_type(filename)
    return guessed or "application/octet-stream"


class InMemoryEconomy:
    def __init__(self) -> None:
        self._entries: dict[int, list[int]] = {}

    def _ensure_entry(self, user_id: int) -> None:
        self._entries.setdefault(user_id, [user_id, 0, 0])

    def get_entry(self, user_id: int) -> tuple[int, int, int]:
        self._ensure_entry(user_id)
        entry = self._entries[user_id]
        return (entry[0], entry[1], entry[2])

    def new_entry(self, user_id: int) -> tuple[int, int, int]:
        return self.get_entry(user_id)

    def remove_entry(self, user_id: int) -> None:
        self._entries.pop(user_id, None)

    def set_money(self, user_id: int, money: int) -> tuple[int, int, int]:
        self._ensure_entry(user_id)
        self._entries[user_id][1] = max(0, int(money))
        return self.get_entry(user_id)

    def set_credits(self, user_id: int, credits: int) -> tuple[int, int, int]:
        self._ensure_entry(user_id)
        self._entries[user_id][2] = max(0, int(credits))
        return self.get_entry(user_id)

    def add_money(self, user_id: int, money_to_add: int) -> tuple[int, int, int]:
        self._ensure_entry(user_id)
        self._entries[user_id][1] = max(
            0,
            self._entries[user_id][1] + int(money_to_add),
        )
        return self.get_entry(user_id)

    def add_credits(self, user_id: int, credits_to_add: int) -> tuple[int, int, int]:
        self._ensure_entry(user_id)
        self._entries[user_id][2] = max(
            0,
            self._entries[user_id][2] + int(credits_to_add),
        )
        return self.get_entry(user_id)

    def top_entries(self, n: int = 0) -> list[tuple[int, int, int]]:
        entries = sorted(
            (tuple(values) for values in self._entries.values()),
            key=lambda entry: entry[1],
            reverse=True,
        )
        if n:
            return entries[:n]
        return entries

    def close(self) -> None:
        return


class DemoUser:
    def __init__(self, *, user_id: int, name: str, avatar_url: str):
        self.id = user_id
        self.name = name
        self.display_avatar = type("Avatar", (), {"url": avatar_url})()

    def __eq__(self, other: object) -> bool:
        return isinstance(other, DemoUser) and self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)


class DemoGuild:
    def __init__(self, guild_id: int):
        self.id = guild_id

    def get_member(self, _: int) -> None:
        return None

    def get_member_named(self, _: str) -> None:
        return None


class DemoSentMessage:
    def __init__(
        self,
        *,
        session: "DemoSession",
        message_id: int,
        content: str | None,
        embeds: list[discord.Embed],
        attachment_urls: dict[str, str],
        view: discord.ui.View | None,
    ):
        self._session = session
        self.id = message_id
        self.content = content
        self.embeds = embeds
        self.attachment_urls = attachment_urls
        self.view = view
        self.reactions: list[str] = []

    async def add_reaction(self, emoji: str) -> None:
        value = str(emoji)
        if value not in self.reactions:
            self.reactions.append(value)
        # Track only the currently actionable reaction prompt.
        self._session.reaction_messages = {self.id: self}
        self._session.active_reaction_message_id = self.id

    async def delete(self) -> None:
        return

    async def edit(self, **kwargs: Any) -> "DemoSentMessage":
        if "view" in kwargs:
            self.view = kwargs["view"]
        return self


class DemoChannel:
    def __init__(self, session: "DemoSession"):
        self._session = session
        self.id = 2000

    async def send(self, *args: Any, **kwargs: Any) -> DemoSentMessage:
        content: str | None = None
        if args:
            content = args[0]
        if content is None:
            content = kwargs.get("content")

        embeds: list[discord.Embed] = []
        embed = kwargs.get("embed")
        if embed is not None:
            embeds.append(embed)
        extra_embeds = kwargs.get("embeds")
        if extra_embeds:
            embeds.extend(extra_embeds)

        attachment_urls: dict[str, str] = {}
        file = kwargs.get("file")
        if file is not None:
            attachment_urls[file.filename] = self._session.store_asset(file)
        files = kwargs.get("files")
        if files:
            for extra_file in files:
                attachment_urls[extra_file.filename] = self._session.store_asset(extra_file)

        message = DemoSentMessage(
            session=self._session,
            message_id=self._session.next_outbound_message_id(),
            content=content,
            embeds=embeds,
            attachment_urls=attachment_urls,
            view=kwargs.get("view"),
        )
        self._session.outbound_messages.append(message)
        return message


class DemoInboundMessage:
    def __init__(
        self,
        *,
        content: str,
        bot: commands.Bot,
        author: DemoUser,
        channel: DemoChannel,
        guild: DemoGuild,
    ):
        self._state = bot._connection
        self.content = content
        self.clean_content = content
        self.author = author
        self.channel = channel
        self.guild = guild
        self.attachments: list[Any] = []
        self.mentions: list[Any] = []
        self.created_at = datetime.now(UTC)
        self.id = int(datetime.now(UTC).timestamp() * 1_000_000)


class DemoContext(commands.Context):
    async def send(self, content: str | None = None, **kwargs: Any) -> DemoSentMessage:
        return await self.channel.send(content, **kwargs)


class DemoCommandBot(commands.Bot):
    def __init__(self, session: "DemoSession"):
        super().__init__(
            command_prefix=config.bot.prefix,
            owner_ids=set(config.bot.owner_ids),
            intents=discord.Intents.none(),
        )
        self.session = session
        self.economy = InMemoryEconomy()
        self.remove_command("help")

    async def wait_for(
        self,
        event: str,
        *,
        check: Any = None,
        timeout: float | None = None,
    ) -> Any:
        return await self.session.wait_for(event, check=check, timeout=timeout)


@dataclass
class DemoAsset:
    data: bytes
    content_type: str
    filename: str
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class DemoRuntimeManager:
    def __init__(self):
        self.sessions: dict[str, "DemoSession"] = {}
        self.assets: dict[str, DemoAsset] = {}
        self._lock = asyncio.Lock()

    async def get_session(self, session_id: str) -> "DemoSession":
        async with self._lock:
            session = self.sessions.get(session_id)
            if session is None:
                session = DemoSession(session_id=session_id, manager=self)
                self.sessions[session_id] = session
        await session.ensure_initialized()
        return session

    def store_asset(self, data: bytes, filename: str) -> str:
        asset_id = uuid4().hex
        self.assets[asset_id] = DemoAsset(
            data=data,
            content_type=_guess_content_type(filename),
            filename=filename,
        )
        return f"/api/demo/assets/{asset_id}"

    def get_asset(self, asset_id: str) -> DemoAsset | None:
        return self.assets.get(asset_id)


class DemoSession:
    def __init__(self, *, session_id: str, manager: DemoRuntimeManager):
        self.session_id = session_id
        self.manager = manager
        self._init_lock = asyncio.Lock()
        self._command_lock = asyncio.Lock()
        self.initialized = False

        self.bot: DemoCommandBot | None = None
        self.channel: DemoChannel | None = None
        self.user: DemoUser | None = None
        self.guild: DemoGuild | None = None

        self.outbound_messages: list[DemoSentMessage] = []
        self._delivered_outbound_index = 0
        self._next_outbound_id = 1
        self.reaction_messages: dict[int, DemoSentMessage] = {}
        self.reaction_queue: asyncio.Queue[str] = asyncio.Queue()
        self.awaiting_reaction = False
        self.active_reaction_message_id: int | None = None
        self._active_task: asyncio.Task | None = None
        self.last_highcard_command = f"{config.bot.prefix}highcard"

    async def ensure_initialized(self) -> None:
        if self.initialized:
            return

        async with self._init_lock:
            if self.initialized:
                return

            self.user = DemoUser(
                user_id=self._session_user_id(),
                name="Visitor",
                avatar_url="/static/demo/assets/user-avatar.svg",
            )
            self.guild = DemoGuild(guild_id=5000)
            self.bot = DemoCommandBot(self)
            self.channel = DemoChannel(self)
            await register_cogs(self.bot)
            self._seed_wallet()
            self.initialized = True

    def _session_user_id(self) -> int:
        digest = hashlib.sha256(self.session_id.encode("utf-8")).digest()
        # Keep ids in a stable positive range and avoid tiny values.
        return 1_000_000 + int.from_bytes(digest[:8], byteorder="big") % 9_000_000_000

    def _seed_wallet(self) -> None:
        assert self.bot is not None
        assert self.user is not None
        self.bot.economy.set_money(self.user.id, config.bot.default_bet * 10)
        self.bot.economy.set_credits(self.user.id, 10)

    def next_outbound_message_id(self) -> int:
        value = self._next_outbound_id
        self._next_outbound_id += 1
        return value

    def store_asset(self, file: discord.File) -> str:
        if hasattr(file.fp, "seek"):
            file.fp.seek(0)
        data = file.fp.read()
        if isinstance(data, str):
            data = data.encode("utf-8")
        if not isinstance(data, bytes):
            data = bytes(data)
        return self.manager.store_asset(data, file.filename)

    async def wait_for(
        self,
        event: str,
        *,
        check: Any = None,
        timeout: float | None = None,
    ) -> Any:
        if event != "reaction_add":
            raise asyncio.TimeoutError()

        assert self.user is not None
        self.awaiting_reaction = True
        deadline = None if timeout is None else asyncio.get_running_loop().time() + timeout

        try:
            while True:
                wait_timeout: float | None
                if deadline is None:
                    wait_timeout = None
                else:
                    wait_timeout = deadline - asyncio.get_running_loop().time()
                    if wait_timeout <= 0:
                        raise asyncio.TimeoutError()

                emoji = await asyncio.wait_for(self.reaction_queue.get(), timeout=wait_timeout)
                candidates = list(self.reaction_messages.values())
                if not candidates:
                    continue
                for candidate in reversed(candidates):
                    reaction = type("Reaction", (), {"emoji": emoji, "message": candidate})()
                    user = self.user
                    if check is None or check(reaction, user):
                        self.active_reaction_message_id = None
                        return reaction, user
                fallback = candidates[-1]
                reaction = type("Reaction", (), {"emoji": emoji, "message": fallback})()
                self.active_reaction_message_id = None
                return reaction, self.user
        finally:
            self.awaiting_reaction = False

    async def reset(self) -> dict[str, Any]:
        await self.ensure_initialized()
        async with self._command_lock:
            if self._active_task and not self._active_task.done():
                self._active_task.cancel()
                with suppress(asyncio.CancelledError):
                    await self._active_task
            self._active_task = None
            self.awaiting_reaction = False
            self.active_reaction_message_id = None
            self.reaction_messages.clear()
            while not self.reaction_queue.empty():
                try:
                    self.reaction_queue.get_nowait()
                except asyncio.QueueEmpty:
                    break
            self.outbound_messages.clear()
            self._delivered_outbound_index = 0
            self._next_outbound_id = 1
            self._seed_wallet()
            return self._response_payload(messages=[])

    async def run_command(self, command_text: str) -> dict[str, Any]:
        await self.ensure_initialized()
        assert self.bot is not None
        assert self.user is not None
        assert self.channel is not None
        assert self.guild is not None

        async with self._command_lock:
            if self._active_task and not self._active_task.done():
                return self._response_payload(messages=[], error="Command already running.")

            normalized = command_text.strip()
            if not normalized:
                return self._response_payload(messages=[], error="Empty command.")

            self._track_highcard_command(normalized)
            self._active_task = asyncio.create_task(
                self._invoke_command(normalized),
                name=f"demo-command-{self.session_id}",
            )
            await self._wait_for_task_pause_or_finish()
            return self._response_payload(messages=self._collect_new_messages())

    async def run_action(self, action: dict[str, Any]) -> dict[str, Any]:
        await self.ensure_initialized()

        async with self._command_lock:
            action_type = action.get("type")
            if action_type == "reaction":
                emoji = action.get("emoji")
                if not isinstance(emoji, str) or not emoji:
                    return self._response_payload(messages=[], error="Invalid reaction action.")
                action_message_id = action.get("message_id")
                if action_message_id is not None:
                    try:
                        action_message_id = int(action_message_id)
                    except (TypeError, ValueError):
                        return self._response_payload(messages=[], error="Invalid reaction action.")
                if self._active_task is None or self._active_task.done() or not self.awaiting_reaction:
                    return self._response_payload(messages=[], error="No active prompt.")
                if (
                    action_message_id is not None
                    and self.active_reaction_message_id is not None
                    and action_message_id != self.active_reaction_message_id
                ):
                    return self._response_payload(messages=[], error="Prompt expired. Use latest buttons.")
                previous_count = len(self.outbound_messages)
                was_waiting_for_reaction = self.awaiting_reaction
                await self.reaction_queue.put(emoji)
                await self._wait_for_action_progress(
                    previous_count,
                    was_waiting_for_reaction=was_waiting_for_reaction,
                )
                return self._response_payload(messages=self._collect_new_messages())

            if action_type == "command":
                command = action.get("command")
                if not isinstance(command, str) or not command.strip():
                    return self._response_payload(messages=[], error="Invalid command action.")
            else:
                return self._response_payload(messages=[], error="Unsupported action.")

        return await self.run_command(command)

    async def _invoke_command(self, command_text: str) -> None:
        assert self.bot is not None
        assert self.user is not None
        assert self.channel is not None
        assert self.guild is not None

        message = DemoInboundMessage(
            content=command_text,
            bot=self.bot,
            author=self.user,
            channel=self.channel,
            guild=self.guild,
        )
        view = StringView(message.content)
        prefix = config.bot.prefix
        if not view.skip_string(prefix):
            await self._send_demo_help_embed()
            return

        invoked_with = view.get_word().lower()
        if not invoked_with:
            await self._send_demo_help_embed()
            return

        if invoked_with not in DEMO_ALLOWED_COMMAND_SET:
            await self._send_demo_help_embed()
            return

        if invoked_with == "help":
            requested = view.read_rest().strip().split(" ", 1)[0].lower() if not view.eof else None
            await self._send_demo_help_embed(requested)
            return

        command = self.bot.get_command(invoked_with)
        ctx = DemoContext(
            message=message,
            bot=self.bot,
            view=view,
            prefix=prefix,
            command=command,
            invoked_with=invoked_with,
        )

        try:
            if command is None:
                await self._send_demo_help_embed()
                return
            await command.invoke(ctx)
        except Exception as exc:
            handlers = self.bot.get_cog("handlers")
            if handlers is not None:
                await handlers.on_command_error(ctx, exc)
            else:
                logger.exception("Demo command error without handlers.", exc_info=exc)
                raise

    async def _wait_for_task_pause_or_finish(self) -> None:
        if self._active_task is None:
            return
        deadline = asyncio.get_running_loop().time() + 30.0
        while True:
            task = self._active_task
            if task.done():
                try:
                    await task
                except Exception as exc:
                    logger.exception("Demo command task failed.", exc_info=exc)
                self._active_task = None
                self.active_reaction_message_id = None
                return
            if self.awaiting_reaction:
                return
            if asyncio.get_running_loop().time() >= deadline:
                return
            await asyncio.sleep(0.01)

    async def _wait_for_action_progress(
        self,
        previous_count: int,
        *,
        was_waiting_for_reaction: bool,
    ) -> None:
        if self._active_task is None:
            return
        consumed_previous_reaction_wait = not was_waiting_for_reaction
        deadline = asyncio.get_running_loop().time() + 30.0
        while True:
            task = self._active_task
            if task.done():
                try:
                    await task
                except Exception as exc:
                    logger.exception("Demo command task failed during action.", exc_info=exc)
                self._active_task = None
                self.active_reaction_message_id = None
                return

            if not self.awaiting_reaction:
                consumed_previous_reaction_wait = True

            if (
                consumed_previous_reaction_wait
                and self.awaiting_reaction
                and len(self.outbound_messages) > previous_count
            ):
                # Prompt message exists and command is now waiting for the next reaction.
                return
            if asyncio.get_running_loop().time() >= deadline:
                return
            await asyncio.sleep(0.01)

    async def _send_demo_help_embed(self, requested: str | None = None) -> None:
        assert self.channel is not None
        assert self.bot is not None

        if requested and requested in DEMO_ALLOWED_COMMAND_SET and requested != "help":
            command = self.bot.get_command(requested)
            if command is None:
                command = self.bot.get_command("highcard") if requested == "war" else None

            if command is not None:
                usage = command.usage or command.name
                if requested == "war" and usage.startswith("highcard"):
                    usage = usage.replace("highcard", "war", 1)
                usage_prefix = config.bot.prefix
                embed = discord.Embed(
                    title=requested,
                    description=command.brief or "Command help.",
                    color=discord.Color.blurple(),
                )
                embed.add_field(name="Usage:", value=f"`{usage_prefix}{usage}`")
                aliases = [
                    alias
                    for alias in command.aliases
                    if alias in DEMO_ALLOWED_COMMAND_SET
                ]
                if aliases:
                    alias_value = ", ".join(f"`{usage_prefix}{alias}`" for alias in aliases)
                    embed.add_field(name="Aliases:", value=alias_value)
                embed.set_footer(text="* optional")
                await self.channel.send(embed=embed)
                return

        prefix = config.bot.prefix
        embed = discord.Embed(title="Commands", color=discord.Color.blurple())
        lines = [f"{prefix}{name}" for name in DEMO_ALLOWED_COMMANDS]
        embed.add_field(name="Demo", value="\n".join(lines), inline=False)
        embed.set_footer(text=datetime.now().strftime("%m/%d/%Y %H:%M:%S"))
        await self.channel.send(embed=embed)

    def _collect_new_messages(self) -> list[dict[str, Any]]:
        new_messages = self.outbound_messages[self._delivered_outbound_index :]
        self._delivered_outbound_index = len(self.outbound_messages)
        return [self._serialize_message(message) for message in new_messages]

    def _serialize_message(self, message: DemoSentMessage) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "id": message.id,
            "content": message.content,
            "embeds": [self._serialize_embed(embed, message.attachment_urls) for embed in message.embeds],
            "components": self._serialize_components(message),
        }
        return payload

    def _serialize_embed(
        self,
        embed: discord.Embed,
        attachment_urls: dict[str, str],
    ) -> dict[str, Any]:
        image_url: str | None = None
        if embed.image and embed.image.url:
            image_url = embed.image.url
            if image_url.startswith("attachment://"):
                filename = image_url.split("attachment://", 1)[1]
                image_url = attachment_urls.get(filename)

        color = None
        if embed.color is not None:
            color = f"#{embed.color.value:06x}"

        description_lines = embed.description.split("\n") if embed.description else []
        fields = [{"name": field.name, "value": field.value} for field in embed.fields]
        footer = embed.footer.text if embed.footer else None

        return {
            "title": embed.title,
            "description_lines": description_lines,
            "fields": fields,
            "footer": footer,
            "color": color,
            "image_url": image_url,
        }

    def _serialize_components(self, message: DemoSentMessage) -> list[dict[str, Any]]:
        components: list[dict[str, Any]] = []

        if message.reactions:
            for emoji in message.reactions:
                label, style = REACTION_ACTIONS.get(emoji, (emoji, "secondary"))
                components.append(
                    {
                        "label": label,
                        "style": style,
                        "action": {
                            "type": "reaction",
                            "emoji": emoji,
                            "message_id": message.id,
                        },
                    }
                )

        if message.view is not None and getattr(message.view, "children", None):
            for child in message.view.children:
                if not isinstance(child, discord.ui.Button):
                    continue
                if (child.label or "").lower() == "redraw same bet":
                    action = {"type": "command", "command": self.last_highcard_command}
                else:
                    action = None
                components.append(
                    {
                        "label": child.label or "Action",
                        "style": _button_style_name(child.style),
                        "action": action,
                        "disabled": action is None,
                    }
                )

        return components

    def _track_highcard_command(self, command_text: str) -> None:
        normalized = command_text.strip()
        if not normalized.startswith(config.bot.prefix):
            return
        body = normalized[len(config.bot.prefix) :].strip()
        if not body:
            return
        command_name = body.split(" ", 1)[0].lower()
        if command_name in {"highcard", "war"}:
            self.last_highcard_command = normalized

    def _response_payload(
        self,
        *,
        messages: list[dict[str, Any]],
        error: str | None = None,
    ) -> dict[str, Any]:
        assert self.bot is not None
        assert self.user is not None
        entry = self.bot.economy.get_entry(self.user.id)
        active_task_running = self._active_task is not None and not self._active_task.done()
        return {
            "messages": messages,
            "wallet": {"money": entry[1], "credits": entry[2]},
            "awaiting_action": bool(active_task_running and self.awaiting_reaction),
            "error": error,
        }
