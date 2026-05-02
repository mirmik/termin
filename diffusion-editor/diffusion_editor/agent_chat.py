"""Experimental agent chat panel for OpenAI-compatible APIs."""

from __future__ import annotations

from dataclasses import dataclass
import json
from queue import Empty, Queue
import threading
from typing import Any
from urllib import error, request

from tcgui.widgets.button import Button
from tcgui.widgets.hstack import HStack
from tcgui.widgets.label import Label
from tcgui.widgets.panel import Panel
from tcgui.widgets.text_area import TextArea
from tcgui.widgets.text_input import TextInput
from tcgui.widgets.units import pct, px
from tcgui.widgets.vstack import VStack

from .settings import Settings


DEFAULT_AGENT_BASE_URL = "https://api.openai.com/v1"
DEFAULT_AGENT_MODEL = "gpt-4o-mini"

SYSTEM_PROMPT = (
    "You are a built-in agent of Diffusion Editor — a node-based image and texture "
    "generation tool. You are currently in early prototype / test mode, so your "
    "capabilities are very limited: you cannot access the editor canvas, layers, "
    "nodes, or any project data. Be upfront about this when asked to do anything "
    "beyond general conversation."
)


@dataclass
class AgentChatConfig:
    base_url: str = DEFAULT_AGENT_BASE_URL
    api_key: str = ""
    model: str = DEFAULT_AGENT_MODEL
    temperature: float = 0.7
    max_tokens: int = 1024
    timeout_seconds: float = 60.0
    stream: bool = True


class OpenAICompatibleChatClient:
    """Small async chat-completions client.

    The UI thread calls ``submit()`` and then drains events through ``poll()``.
    """

    def __init__(self):
        self._events: Queue[tuple[str, Any]] = Queue()
        self._thread: threading.Thread | None = None
        self._cancel = threading.Event()

    @property
    def is_busy(self) -> bool:
        return self._thread is not None and self._thread.is_alive()

    def submit(self, config: AgentChatConfig, messages: list[dict[str, str]]) -> None:
        if self.is_busy:
            return
        self._cancel.clear()
        self._thread = threading.Thread(
            target=self._run,
            args=(config, messages),
            daemon=True,
        )
        self._thread.start()

    def cancel(self) -> None:
        self._cancel.set()

    def poll(self) -> list[tuple[str, Any]]:
        events: list[tuple[str, Any]] = []
        while True:
            try:
                events.append(self._events.get_nowait())
            except Empty:
                break
        return events

    def shutdown(self, timeout: float = 0.25) -> None:
        self.cancel()
        thread = self._thread
        if thread is not None and thread.is_alive():
            thread.join(timeout=timeout)

    def _run(self, config: AgentChatConfig, messages: list[dict[str, str]]) -> None:
        try:
            if not config.base_url.strip():
                raise ValueError("Agent API base URL is empty")
            if not config.model.strip():
                raise ValueError("Agent model is empty")

            payload: dict[str, Any] = {
                "model": config.model.strip(),
                "messages": [{"role": "system", "content": SYSTEM_PROMPT}] + messages,
                "temperature": float(config.temperature),
                "stream": bool(config.stream),
            }
            if config.max_tokens > 0:
                payload["max_tokens"] = int(config.max_tokens)

            url = config.base_url.rstrip("/") + "/chat/completions"
            headers = {"Content-Type": "application/json"}
            if config.api_key:
                headers["Authorization"] = f"Bearer {config.api_key}"
            req = request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )

            with request.urlopen(req, timeout=config.timeout_seconds) as response:
                if config.stream:
                    self._read_stream(response)
                else:
                    raw = response.read().decode("utf-8")
                    if self._cancel.is_set():
                        self._events.put(("cancelled", None))
                        return
                    data = json.loads(raw)
                    content = (
                        data.get("choices", [{}])[0]
                        .get("message", {})
                        .get("content", "")
                    )
                    self._events.put(("message", content))
            if self._cancel.is_set():
                self._events.put(("cancelled", None))
            else:
                self._events.put(("done", None))
        except error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            self._events.put(("error", f"HTTP {exc.code}: {body[:500]}"))
        except Exception as exc:
            self._events.put(("error", str(exc)))

    def _read_stream(self, response) -> None:
        for raw_line in response:
            if self._cancel.is_set():
                return
            line = raw_line.decode("utf-8", errors="replace").strip()
            if not line or line.startswith(":"):
                continue
            if line.startswith("data:"):
                line = line[5:].strip()
            if line == "[DONE]":
                return
            try:
                data = json.loads(line)
            except json.JSONDecodeError:
                continue
            choices = data.get("choices") or []
            if not choices:
                continue
            delta = choices[0].get("delta") or {}
            content = delta.get("content") or ""
            if content:
                self._events.put(("delta", content))


class AgentChatPanel(Panel):
    """Bottom chat panel. Tool access will be layered on top later."""

    def __init__(self, settings: Settings):
        super().__init__()
        self.preferred_width = pct(100)
        self.preferred_height = px(220)
        self.padding = 8
        self._settings = settings
        self._client = OpenAICompatibleChatClient()
        self._messages: list[dict[str, str]] = []
        self._assistant_buffer = ""
        self._assistant_active = False

        root = VStack()
        root.spacing = 6
        root.preferred_width = pct(100)
        root.preferred_height = pct(100)

        header = HStack()
        header.spacing = 8

        title = Label()
        title.text = "Agent Chat"
        title.font_size = 13
        header.add_child(title)

        self._status = Label()
        self._status.text = "Not connected"
        self._status.font_size = 11
        self._status.stretch = True
        header.add_child(self._status)

        self._clear_btn = Button()
        self._clear_btn.text = "Clear"
        self._clear_btn.preferred_width = px(70)
        self._clear_btn.on_click = self.clear
        header.add_child(self._clear_btn)
        root.add_child(header)

        self._transcript = TextArea()
        self._transcript.read_only = True
        self._transcript.word_wrap = True
        self._transcript.preferred_width = pct(100)
        self._transcript.stretch = True
        self._transcript.text = "Configure the Agent Chat API in Edit -> Settings."
        root.add_child(self._transcript)

        input_row = HStack()
        input_row.spacing = 6

        self._input = TextInput()
        self._input.placeholder = "Ask the agent..."
        self._input.stretch = True
        self._input.on_submit = lambda _: self.submit()
        input_row.add_child(self._input)

        self._send_btn = Button()
        self._send_btn.text = "Send"
        self._send_btn.preferred_width = px(70)
        self._send_btn.on_click = self.submit
        input_row.add_child(self._send_btn)

        self._stop_btn = Button()
        self._stop_btn.text = "Stop"
        self._stop_btn.preferred_width = px(70)
        self._stop_btn.enabled = False
        self._stop_btn.on_click = self.cancel
        input_row.add_child(self._stop_btn)
        root.add_child(input_row)

        self.add_child(root)

    def layout(self, x: float, y: float, width: float, height: float,
               viewport_w: float, viewport_h: float):
        self.x = x
        self.y = y
        self.width = width
        self.height = height

        inner_x = x + self.padding
        inner_y = y + self.padding
        inner_w = max(0.0, width - self.padding * 2)
        inner_h = max(0.0, height - self.padding * 2)
        for child in self.children:
            child.layout(inner_x, inner_y, inner_w, inner_h, viewport_w, viewport_h)

    def submit(self) -> None:
        text = self._input.text.strip()
        if not text or self._client.is_busy:
            return

        config = self._load_config()
        if not config.api_key:
            self._status.text = "Missing API key"
            return

        self._input.text = ""
        self._input.cursor_pos = 0
        self._messages.append({"role": "user", "content": text})
        self._assistant_buffer = ""
        self._assistant_active = True
        self._sync_transcript()
        self._set_busy(True, "Waiting for agent...")
        self._client.submit(config, list(self._messages))

    def cancel(self) -> None:
        if not self._client.is_busy:
            return
        self._client.cancel()
        self._status.text = "Stopping..."

    def clear(self) -> None:
        if self._client.is_busy:
            return
        self._messages.clear()
        self._assistant_buffer = ""
        self._assistant_active = False
        self._transcript.text = ""
        self._status.text = "Cleared"

    def poll(self) -> None:
        for kind, value in self._client.poll():
            if kind == "delta":
                self._assistant_buffer += value
                self._status.text = "Receiving..."
                self._sync_transcript()
            elif kind == "message":
                self._assistant_buffer = value or ""
                self._sync_transcript()
            elif kind == "done":
                self._finish_assistant()
            elif kind == "cancelled":
                self._status.text = "Stopped"
                self._assistant_active = False
                self._set_busy(False)
                self._sync_transcript()
            elif kind == "error":
                self._status.text = f"Error: {str(value)[:120]}"
                self._assistant_active = False
                self._set_busy(False)

    def shutdown(self) -> None:
        self._client.shutdown()

    def _finish_assistant(self) -> None:
        content = self._assistant_buffer.strip()
        if content:
            self._messages.append({"role": "assistant", "content": content})
        self._assistant_buffer = ""
        self._assistant_active = False
        self._set_busy(False, "Ready")
        self._sync_transcript()

    def _set_busy(self, busy: bool, status: str | None = None) -> None:
        self._send_btn.enabled = not busy
        self._clear_btn.enabled = not busy
        self._stop_btn.enabled = busy
        if status is not None:
            self._status.text = status

    def _sync_transcript(self) -> None:
        lines: list[str] = []
        for msg in self._messages:
            role = "You" if msg["role"] == "user" else "Agent"
            lines.append(f"{role}: {msg['content']}")
        if self._assistant_active:
            lines.append(f"Agent: {self._assistant_buffer}")
        self._transcript.text = "\n\n".join(lines)
        self._transcript.cursor_line = max(0, len(self._transcript._lines) - 1)
        self._transcript.cursor_col = len(self._transcript._lines[-1])
        if self._transcript.height > 0:
            self._transcript._ensure_cursor_visible()

    def _load_config(self) -> AgentChatConfig:
        return AgentChatConfig(
            base_url=str(self._settings.get("agent_api_base_url", DEFAULT_AGENT_BASE_URL)),
            api_key=str(self._settings.get("agent_api_key", "")),
            model=str(self._settings.get("agent_model", DEFAULT_AGENT_MODEL)),
            temperature=float(self._settings.get("agent_temperature", 0.7)),
            max_tokens=int(self._settings.get("agent_max_tokens", 1024)),
            timeout_seconds=float(self._settings.get("agent_timeout_seconds", 60.0)),
            stream=bool(self._settings.get("agent_stream", True)),
        )
