"""
WebStreamServer — стриминг рендера через WebSocket.

Рендерит сцену в offscreen буфер и отправляет кадры в браузер.
Получает события мыши/клавиатуры обратно через WebSocket.

Использование:
    from termin.visualization.streaming import WebStreamServer

    # Создаём сервер
    server = WebStreamServer(world, width=1280, height=720)

    # Запускаем (блокирующий вызов)
    server.run(host="localhost", port=8765)

    # Или async
    await server.run_async(host="localhost", port=8765)
"""

from __future__ import annotations

import asyncio
import base64
import io
import json
import time
import threading
from typing import TYPE_CHECKING, Optional, Set, Callable
from weakref import WeakSet

from termin.visualization.core.input_events import (
    MouseButtonEvent,
    MouseMoveEvent,
    ScrollEvent,
    KeyEvent,
)

if TYPE_CHECKING:
    from termin.visualization.core.world import VisualizationWorld
    from termin.visualization.core.scene import Scene
    from termin.visualization.core.camera import CameraComponent


class WebStreamServer:
    """
    WebSocket сервер для стриминга рендера в браузер.

    Архитектура:
    - Рендерит через HeadlessContext + OffscreenRenderSurface
    - Отправляет JPEG кадры через WebSocket
    - Принимает mouse/keyboard события и передаёт в сцену
    """

    def __init__(
        self,
        world: "VisualizationWorld",
        scene: Optional["Scene"] = None,
        camera: Optional["CameraComponent"] = None,
        width: int = 1280,
        height: int = 720,
        fps: int = 30,
        quality: int = 80,
    ):
        """
        Инициализирует стриминг сервер.

        Параметры:
            world: VisualizationWorld для рендеринга.
            scene: Сцена для рендеринга (по умолчанию первая из world).
            camera: Камера (по умолчанию первая из сцены).
            width: Ширина кадра.
            height: Высота кадра.
            fps: Целевой FPS.
            quality: Качество JPEG (1-100).
        """
        self.world = world
        self.scene = scene or (world.scenes[0] if world.scenes else None)
        self._camera = camera
        self.width = width
        self.height = height
        self.target_fps = fps
        self.quality = quality

        self._clients: Set = set()
        self._running = False
        self._render_thread: Optional[threading.Thread] = None
        self._frame_queue: asyncio.Queue = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

        # Для обработки ввода
        self._mouse_x = 0
        self._mouse_y = 0
        self._mouse_buttons = set()

        # Callback для кастомной обработки сообщений
        self.on_message: Optional[Callable[[dict], None]] = None

    @property
    def camera(self) -> Optional["CameraComponent"]:
        """Возвращает камеру для рендеринга."""
        if self._camera is not None:
            return self._camera
        if self.scene is not None:
            # Ищем первую камеру в сцене
            from termin.visualization.core.camera import CameraComponent
            for entity in self.scene.entities:
                cam = entity.get_component(CameraComponent)
                if cam is not None:
                    return cam
        return None

    def _init_render_context(self):
        """Инициализирует OpenGL контекст и offscreen surface."""
        from termin.visualization.render.headless import HeadlessContext
        from termin.visualization.render.surface import OffscreenRenderSurface
        from termin.visualization.render import RenderEngine, RenderView, ViewportRenderState
        from termin.visualization.render.framegraph import RenderPipeline, ResourceSpec
        from termin.visualization.render.framegraph.passes.color import ColorPass
        from termin.visualization.render.framegraph.passes.present import PresentToScreenPass

        self._headless = HeadlessContext()
        self._headless.make_current()

        self._surface = OffscreenRenderSurface(
            self.world.graphics,
            self.width,
            self.height,
        )

        self._engine = RenderEngine(self.world.graphics)

        # Pipeline для offscreen рендера
        color_pass = ColorPass(
            input_res="empty",
            output_res="color",
            shadow_res=None,
            pass_name="Color",
        )
        present_pass = PresentToScreenPass(
            input_res="color",
            output_res="DISPLAY",
            pass_name="Present",
        )

        self._pipeline = RenderPipeline(
            passes=[color_pass, present_pass],
            pipeline_specs=[
                ResourceSpec(
                    resource="empty",
                    clear_color=(0.1, 0.1, 0.15, 1.0),
                    clear_depth=1.0,
                ),
            ],
        )
        self._state = ViewportRenderState(pipeline=self._pipeline)

    def _render_frame(self) -> bytes:
        """
        Рендерит один кадр и возвращает JPEG байты.

        Возвращает:
            JPEG изображение в виде bytes.
        """
        from termin.visualization.render import RenderView
        from PIL import Image

        if self.scene is None or self.camera is None:
            # Возвращаем пустой чёрный кадр
            img = Image.new("RGB", (self.width, self.height), (0, 0, 0))
            buffer = io.BytesIO()
            img.save(buffer, format="JPEG", quality=self.quality)
            return buffer.getvalue()

        # Обновляем сцену
        self.scene.update(1.0 / self.target_fps)

        # Создаём RenderView
        view = RenderView(
            scene=self.scene,
            camera=self.camera,
            rect=(0, 0, 1, 1),
            canvas=None,
        )

        # Рендерим
        self._engine.render_single_view(
            surface=self._surface,
            view=view,
            state=self._state,
            present=False,
        )

        # Читаем пиксели
        pixels = self._surface.read_pixels()

        # Конвертируем в JPEG
        img = Image.fromarray(pixels[:, :, :3])  # RGB без альфы
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=self.quality)
        return buffer.getvalue()

    def _render_loop(self):
        """Фоновый поток рендеринга."""
        self._init_render_context()

        frame_time = 1.0 / self.target_fps

        while self._running:
            start = time.perf_counter()

            try:
                frame_data = self._render_frame()

                # Отправляем кадр в очередь
                if self._loop is not None and self._frame_queue is not None:
                    asyncio.run_coroutine_threadsafe(
                        self._frame_queue.put(frame_data),
                        self._loop,
                    )
            except Exception as e:
                print(f"Render error: {e}")

            # Ждём до следующего кадра
            elapsed = time.perf_counter() - start
            sleep_time = frame_time - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

        # Освобождаем ресурсы
        self._surface.delete()
        self._headless.destroy()

    async def _broadcast_frames(self):
        """Рассылает кадры всем подключённым клиентам."""
        while self._running:
            try:
                frame_data = await asyncio.wait_for(
                    self._frame_queue.get(),
                    timeout=1.0,
                )

                if not self._clients:
                    continue

                # Кодируем в base64 для отправки
                frame_b64 = base64.b64encode(frame_data).decode("ascii")
                message = json.dumps({
                    "type": "frame",
                    "data": frame_b64,
                })

                # Отправляем всем клиентам
                disconnected = set()
                for client in self._clients:
                    try:
                        await client.send(message)
                    except Exception:
                        disconnected.add(client)

                self._clients -= disconnected

            except asyncio.TimeoutError:
                continue
            except Exception as e:
                print(f"Broadcast error: {e}")

    async def _handle_client(self, websocket):
        """Обрабатывает подключение клиента."""
        self._clients.add(websocket)
        print(f"Client connected. Total: {len(self._clients)}")

        try:
            async for message in websocket:
                await self._process_message(message)
        except Exception as e:
            print(f"Client error: {e}")
        finally:
            self._clients.discard(websocket)
            print(f"Client disconnected. Total: {len(self._clients)}")

    async def _process_message(self, raw_message: str):
        """Обрабатывает входящее сообщение от клиента."""
        try:
            msg = json.loads(raw_message)
        except json.JSONDecodeError:
            return

        msg_type = msg.get("type")

        if msg_type == "mousemove":
            self._mouse_x = msg.get("x", 0)
            self._mouse_y = msg.get("y", 0)
            dx = msg.get("dx", 0)
            dy = msg.get("dy", 0)
            self._dispatch_mouse_move(self._mouse_x, self._mouse_y, dx, dy)

        elif msg_type == "mousedown":
            button = msg.get("button", 0)
            self._mouse_buttons.add(button)
            self._dispatch_mouse_button(button, "press")

        elif msg_type == "mouseup":
            button = msg.get("button", 0)
            self._mouse_buttons.discard(button)
            self._dispatch_mouse_button(button, "release")

        elif msg_type == "wheel":
            delta_y = msg.get("deltaY", 0)
            self._dispatch_scroll(0, -delta_y / 100)

        elif msg_type == "keydown":
            key = msg.get("key", "")
            self._dispatch_key(key, "press")

        elif msg_type == "keyup":
            key = msg.get("key", "")
            self._dispatch_key(key, "release")

        elif msg_type == "resize":
            new_width = msg.get("width", self.width)
            new_height = msg.get("height", self.height)
            self._resize(new_width, new_height)

        # Вызываем кастомный callback если есть
        if self.on_message is not None:
            self.on_message(msg)

    def _dispatch_mouse_move(self, x: float, y: float, dx: float, dy: float):
        """Передаёт событие движения мыши в сцену."""
        if self.scene is None:
            return
        event = MouseMoveEvent(viewport=None, x=x, y=y, dx=dx, dy=dy)
        self.scene.dispatch_input("on_mouse_move", event)

    def _dispatch_mouse_button(self, button: int, action: str):
        """Передаёт событие кнопки мыши в сцену."""
        if self.scene is None:
            return
        from termin.visualization.platform.backends.base import MouseButton, Action

        # Маппинг browser button -> MouseButton
        button_map = {
            0: MouseButton.LEFT,
            1: MouseButton.MIDDLE,
            2: MouseButton.RIGHT,
        }
        mb = button_map.get(button, MouseButton.LEFT)
        act = Action.PRESS if action == "press" else Action.RELEASE

        # Для streaming нет viewport, передаём x=0, y=0
        event = MouseButtonEvent(viewport=None, x=0, y=0, button=mb, action=act, mods=0)
        self.scene.dispatch_input("on_mouse_button", event)

    def _dispatch_scroll(self, x_offset: float, y_offset: float):
        """Передаёт событие скролла в сцену."""
        if self.scene is None:
            return
        event = ScrollEvent(viewport=None, x=0, y=0, xoffset=x_offset, yoffset=y_offset)
        self.scene.dispatch_input("on_scroll", event)

    def _dispatch_key(self, key: str, action: str):
        """Передаёт событие клавиатуры в сцену."""
        if self.scene is None:
            return
        from termin.visualization.platform.backends.base import Key, Action

        # Базовый маппинг клавиш
        key_map = {
            "ArrowUp": Key.UP,
            "ArrowDown": Key.DOWN,
            "ArrowLeft": Key.LEFT,
            "ArrowRight": Key.RIGHT,
            "Enter": Key.ENTER,
            "Escape": Key.ESCAPE,
            " ": Key.SPACE,
        }

        k = key_map.get(key)
        if k is None:
            # Пробуем по первой букве
            if len(key) == 1 and key.isalpha():
                k = getattr(Key, key.upper(), None)

        if k is None:
            return

        act = Action.PRESS if action == "press" else Action.RELEASE
        event = KeyEvent(viewport=None, key=k, scancode=0, action=act, mods=0)
        self.scene.dispatch_input("on_key", event)

    def _resize(self, width: int, height: int):
        """Изменяет размер рендера."""
        self.width = width
        self.height = height
        if hasattr(self, "_surface"):
            self._surface.resize(width, height)

    async def run_async(self, host: str = "localhost", port: int = 8765):
        """
        Запускает сервер асинхронно.

        Параметры:
            host: Хост для прослушивания.
            port: Порт для прослушивания.
        """
        import websockets

        self._running = True
        self._loop = asyncio.get_event_loop()
        self._frame_queue = asyncio.Queue(maxsize=2)

        # Запускаем рендер-поток
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._render_thread.start()

        # Запускаем broadcast корутину
        broadcast_task = asyncio.create_task(self._broadcast_frames())

        print(f"WebStream server starting at ws://{host}:{port}")
        print(f"Open http://{host}:{port + 1} in browser (serve HTML separately)")

        async with websockets.serve(self._handle_client, host, port):
            try:
                await asyncio.Future()  # Бесконечное ожидание
            except asyncio.CancelledError:
                pass

        self._running = False
        broadcast_task.cancel()
        self._render_thread.join(timeout=2.0)

    def run(self, host: str = "localhost", port: int = 8765):
        """
        Запускает сервер (блокирующий вызов).

        Параметры:
            host: Хост для прослушивания.
            port: Порт для прослушивания.
        """
        asyncio.run(self.run_async(host, port))

    async def run_with_http_async(self, host: str = "localhost", ws_port: int = 8765, http_port: int = 8080):
        """
        Запускает WebSocket сервер вместе с HTTP сервером для HTML клиента.

        Параметры:
            host: Хост для прослушивания.
            ws_port: Порт для WebSocket.
            http_port: Порт для HTTP (HTML страница).
        """
        import websockets
        from http.server import HTTPServer, SimpleHTTPRequestHandler
        import threading

        self._running = True
        self._loop = asyncio.get_event_loop()
        self._frame_queue = asyncio.Queue(maxsize=2)

        # HTML страница
        html_content = self._generate_html_client(host, ws_port)

        class ClientHandler(SimpleHTTPRequestHandler):
            def do_GET(handler_self):
                handler_self.send_response(200)
                handler_self.send_header("Content-type", "text/html")
                handler_self.end_headers()
                handler_self.wfile.write(html_content.encode("utf-8"))

            def log_message(handler_self, format, *args):
                pass  # Отключаем логи

        # HTTP сервер в отдельном потоке
        http_server = HTTPServer((host, http_port), ClientHandler)
        http_thread = threading.Thread(target=http_server.serve_forever, daemon=True)
        http_thread.start()

        # Запускаем рендер-поток
        self._render_thread = threading.Thread(target=self._render_loop, daemon=True)
        self._render_thread.start()

        # Запускаем broadcast корутину
        broadcast_task = asyncio.create_task(self._broadcast_frames())

        print(f"WebStream server running:")
        print(f"  WebSocket: ws://{host}:{ws_port}")
        print(f"  HTTP:      http://{host}:{http_port}")
        print(f"\nOpen http://{host}:{http_port} in your browser")

        async with websockets.serve(self._handle_client, host, ws_port):
            try:
                await asyncio.Future()
            except asyncio.CancelledError:
                pass

        self._running = False
        broadcast_task.cancel()
        http_server.shutdown()
        self._render_thread.join(timeout=2.0)

    def run_with_http(self, host: str = "localhost", ws_port: int = 8765, http_port: int = 8080):
        """
        Запускает сервер с HTTP (блокирующий вызов).

        Параметры:
            host: Хост.
            ws_port: WebSocket порт.
            http_port: HTTP порт.
        """
        asyncio.run(self.run_with_http_async(host, ws_port, http_port))

    def _generate_html_client(self, ws_host: str, ws_port: int) -> str:
        """Генерирует HTML/JS клиент для браузера."""
        # Браузер не может подключиться к 0.0.0.0, используем window.location.hostname
        if ws_host == "0.0.0.0":
            ws_url = f"'ws://' + window.location.hostname + ':{ws_port}'"
        else:
            ws_url = f"'ws://{ws_host}:{ws_port}'"

        return f'''<!DOCTYPE html>
<html>
<head>
    <title>termin WebStream</title>
    <style>
        body {{
            margin: 0;
            padding: 0;
            background: #1a1a1a;
            display: flex;
            justify-content: center;
            align-items: center;
            height: 100vh;
            overflow: hidden;
        }}
        #canvas {{
            border: 1px solid #333;
            cursor: crosshair;
        }}
        #status {{
            position: fixed;
            top: 10px;
            left: 10px;
            color: #0f0;
            font-family: monospace;
            font-size: 14px;
            background: rgba(0,0,0,0.7);
            padding: 5px 10px;
            border-radius: 4px;
        }}
        #fps {{
            position: fixed;
            top: 10px;
            right: 10px;
            color: #0f0;
            font-family: monospace;
            font-size: 14px;
            background: rgba(0,0,0,0.7);
            padding: 5px 10px;
            border-radius: 4px;
        }}
    </style>
</head>
<body>
    <div id="status">Connecting...</div>
    <div id="fps">FPS: --</div>
    <canvas id="canvas" width="{self.width}" height="{self.height}"></canvas>

    <script>
        const canvas = document.getElementById('canvas');
        const ctx = canvas.getContext('2d');
        const status = document.getElementById('status');
        const fpsDisplay = document.getElementById('fps');

        let ws = null;
        let frameCount = 0;
        let lastFpsTime = performance.now();
        let lastMouseX = 0;
        let lastMouseY = 0;

        function connect() {{
            ws = new WebSocket({ws_url});

            ws.onopen = () => {{
                status.textContent = 'Connected';
                status.style.color = '#0f0';
            }};

            ws.onclose = () => {{
                status.textContent = 'Disconnected. Reconnecting...';
                status.style.color = '#f00';
                setTimeout(connect, 2000);
            }};

            ws.onerror = (e) => {{
                console.error('WebSocket error:', e);
            }};

            ws.onmessage = (event) => {{
                const msg = JSON.parse(event.data);
                if (msg.type === 'frame') {{
                    const img = new Image();
                    img.onload = () => {{
                        ctx.drawImage(img, 0, 0);
                        frameCount++;

                        // Обновляем FPS каждую секунду
                        const now = performance.now();
                        if (now - lastFpsTime >= 1000) {{
                            const fps = Math.round(frameCount * 1000 / (now - lastFpsTime));
                            fpsDisplay.textContent = 'FPS: ' + fps;
                            frameCount = 0;
                            lastFpsTime = now;
                        }}
                    }};
                    img.src = 'data:image/jpeg;base64,' + msg.data;
                }}
            }};
        }}

        // Mouse events
        canvas.addEventListener('mousemove', (e) => {{
            const rect = canvas.getBoundingClientRect();
            const x = e.clientX - rect.left;
            const y = e.clientY - rect.top;
            const dx = x - lastMouseX;
            const dy = y - lastMouseY;
            lastMouseX = x;
            lastMouseY = y;

            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'mousemove',
                    x: x,
                    y: y,
                    dx: dx,
                    dy: dy
                }}));
            }}
        }});

        canvas.addEventListener('mousedown', (e) => {{
            e.preventDefault();
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'mousedown',
                    button: e.button,
                    x: e.offsetX,
                    y: e.offsetY
                }}));
            }}
        }});

        canvas.addEventListener('mouseup', (e) => {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'mouseup',
                    button: e.button,
                    x: e.offsetX,
                    y: e.offsetY
                }}));
            }}
        }});

        canvas.addEventListener('wheel', (e) => {{
            e.preventDefault();
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'wheel',
                    deltaX: e.deltaX,
                    deltaY: e.deltaY
                }}));
            }}
        }});

        // Keyboard events
        document.addEventListener('keydown', (e) => {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'keydown',
                    key: e.key,
                    code: e.code
                }}));
            }}
        }});

        document.addEventListener('keyup', (e) => {{
            if (ws && ws.readyState === WebSocket.OPEN) {{
                ws.send(JSON.stringify({{
                    type: 'keyup',
                    key: e.key,
                    code: e.code
                }}));
            }}
        }});

        // Prevent context menu on right click
        canvas.addEventListener('contextmenu', (e) => e.preventDefault());

        // Start connection
        connect();
    </script>
</body>
</html>'''
