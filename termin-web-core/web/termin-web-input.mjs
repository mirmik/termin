export const TerminInputAction = Object.freeze({Release: 0, Press: 1, Repeat: 2});
export const TerminPointerDevice = Object.freeze({Mouse: 0, Touch: 1, Pen: 2});
export const TerminPointerPhase = Object.freeze({Down: 0, Move: 1, Up: 2, Cancel: 3});

const SPECIAL_KEYS = Object.freeze({
    Escape: 256,
    Enter: 257,
    Tab: 258,
    Backspace: 259,
    Insert: 260,
    Delete: 261,
    ArrowRight: 262,
    ArrowLeft: 263,
    ArrowDown: 264,
    ArrowUp: 265,
    PageUp: 266,
    PageDown: 267,
    Home: 268,
    End: 269,
});

const SPECIAL_SCANCODES = Object.freeze({
    Enter: 40,
    Escape: 41,
    Backspace: 42,
    Tab: 43,
    Space: 44,
    Insert: 73,
    Home: 74,
    PageUp: 75,
    Delete: 76,
    End: 77,
    PageDown: 78,
    ArrowRight: 79,
    ArrowLeft: 80,
    ArrowDown: 81,
    ArrowUp: 82,
});

export function inputModifiers(event) {
    return (event.shiftKey ? 1 : 0) |
        (event.ctrlKey ? 2 : 0) |
        (event.altKey ? 4 : 0) |
        (event.metaKey ? 8 : 0);
}

export function terminKeyCode(event) {
    const special = SPECIAL_KEYS[event.key];
    if (special !== undefined) return special;
    if (event.key === " ") return 32;
    if (typeof event.key === "string" && event.key.length === 1) {
        const upper = event.key.toUpperCase();
        const codepoint = upper.codePointAt(0);
        if ((codepoint >= 48 && codepoint <= 57) ||
                (codepoint >= 65 && codepoint <= 90)) {
            return codepoint;
        }
    }
    return -1;
}

export function terminScanCode(code) {
    if (SPECIAL_SCANCODES[code] !== undefined) return SPECIAL_SCANCODES[code];
    if (/^Key[A-Z]$/.test(code)) return code.charCodeAt(3) - 65 + 4;
    if (/^Digit[1-9]$/.test(code)) return Number(code.slice(5)) + 29;
    if (code === "Digit0") return 39;
    return 0;
}

export function pointerDevice(pointerType) {
    if (pointerType === "touch") return TerminPointerDevice.Touch;
    if (pointerType === "pen") return TerminPointerDevice.Pen;
    return TerminPointerDevice.Mouse;
}

export function terminMouseButton(button) {
    if (button === 1) return 2;
    if (button === 2) return 1;
    return 0;
}

export function canvasPoint(canvas, event) {
    const rect = canvas.getBoundingClientRect();
    const scaleX = rect.width > 0 ? canvas.width / rect.width : 1;
    const scaleY = rect.height > 0 ? canvas.height / rect.height : 1;
    const x = (event.clientX - rect.left) * scaleX;
    const y = (event.clientY - rect.top) * scaleY;
    return {
        x: Math.min(Math.max(x, 0), Math.max(canvas.width - 1, 0)),
        y: Math.min(Math.max(y, 0), Math.max(canvas.height - 1, 0)),
    };
}

export function normalizedWheelDelta(event, pageHeight = 800) {
    if (event.deltaMode === 1) return [-event.deltaX, -event.deltaY];
    if (event.deltaMode === 2) {
        const pages = Math.max(pageHeight, 1) / 100;
        return [-event.deltaX * pages, -event.deltaY * pages];
    }
    return [-event.deltaX / 100, -event.deltaY / 100];
}

export class TerminWebInputAdapter {
    constructor(core, options = {}) {
        this.module = core.module ?? core;
        this.canvas = options.canvas ?? globalThis.document?.querySelector?.("#termin-canvas");
        if (!this.canvas) throw new Error("TerminWebInputAdapter requires a canvas");
        this.window = options.window ?? globalThis.window;
        this.document = options.document ?? globalThis.document;
        this.ResizeObserver = options.ResizeObserver ?? globalThis.ResizeObserver;
        this.logger = options.logger ?? globalThis.console;
        this.getDevicePixelRatio = options.devicePixelRatio ??
            (() => this.window?.devicePixelRatio ?? 1);
        this.enabled = false;
        this.attached = false;
        this.activePointers = new Set();
        this.listeners = [];
        this.resizeObserver = null;
        this.metrics = {events: 0, resizes: 0};
    }

    listen(target, type, handler, options) {
        target?.addEventListener?.(type, handler, options);
        this.listeners.push({target, type, handler, options});
    }

    invoke(name, args = []) {
        const fn = this.module[name];
        if (typeof fn !== "function") {
            throw new Error(`Termin web module does not export ${name}`);
        }
        const accepted = fn(...args);
        if (!accepted) {
            this.logger?.error?.(`TerminWebInputAdapter: native dispatch rejected ${name}`);
            return false;
        }
        this.metrics.events += 1;
        return true;
    }

    attach() {
        if (this.attached) return this;
        this.attached = true;
        if (!this.canvas.hasAttribute?.("tabindex")) this.canvas.tabIndex = 0;
        this.listen(this.canvas, "pointerdown", (event) => this.onPointerDown(event));
        this.listen(this.canvas, "pointermove", (event) => this.onPointerMove(event));
        this.listen(this.canvas, "pointerup", (event) => this.onPointerEnd(event, false));
        this.listen(this.canvas, "pointercancel", (event) => this.onPointerEnd(event, true));
        this.listen(this.canvas, "wheel", (event) => this.onWheel(event), {passive: false});
        this.listen(this.canvas, "keydown", (event) => this.onKey(event, false));
        this.listen(this.canvas, "keyup", (event) => this.onKey(event, true));
        this.listen(this.canvas, "compositionend", (event) => this.onText(event.data));
        this.listen(this.canvas, "contextmenu", (event) => event.preventDefault());
        this.listen(this.canvas, "blur", () => this.onFocusLost());
        this.listen(this.document, "visibilitychange", () => {
            if (this.document.hidden) this.onFocusLost();
        });
        if (this.ResizeObserver) {
            this.resizeObserver = new this.ResizeObserver(() => this.syncCanvasSize());
            this.resizeObserver.observe(this.canvas);
        }
        this.listen(this.window, "resize", () => this.syncCanvasSize());
        this.syncCanvasSize();
        return this;
    }

    setEnabled(enabled) {
        const next = Boolean(enabled);
        if (!next && this.enabled) this.onFocusLost();
        this.enabled = next;
        if (this.enabled) this.syncCanvasSize();
        return this;
    }

    syncCanvasSize() {
        const rect = this.canvas.getBoundingClientRect();
        const dpr = Math.min(Math.max(Number(this.getDevicePixelRatio()) || 1, 0.25), 4);
        const width = Math.max(1, Math.round(rect.width * dpr));
        const height = Math.max(1, Math.round(rect.height * dpr));
        if (this.canvas.width === width && this.canvas.height === height) return false;
        this.canvas.width = width;
        this.canvas.height = height;
        this.metrics.resizes += 1;
        if (this.enabled) this.invoke("_termin_web_host_resize", [width, height]);
        return true;
    }

    onPointerDown(event) {
        if (!this.enabled) return;
        event.preventDefault?.();
        this.canvas.focus?.({preventScroll: true});
        this.activePointers.add(event.pointerId);
        try {
            this.canvas.setPointerCapture?.(event.pointerId);
        } catch (error) {
            this.logger?.warn?.("TerminWebInputAdapter: pointer capture failed", error);
        }
        const point = canvasPoint(this.canvas, event);
        const device = pointerDevice(event.pointerType);
        this.invoke("_termin_web_host_dispatch_pointer", [
            event.pointerId >>> 0, device,
            TerminPointerPhase.Down, point.x, point.y, Number(event.pressure) || 0,
        ]);
        if (device === TerminPointerDevice.Mouse) {
            this.invoke("_termin_web_host_dispatch_mouse_button", [
                point.x, point.y, terminMouseButton(event.button),
                TerminInputAction.Press, inputModifiers(event), event.detail || 1,
            ]);
        }
    }

    onPointerMove(event) {
        if (!this.enabled) return;
        const point = canvasPoint(this.canvas, event);
        const device = pointerDevice(event.pointerType);
        this.invoke("_termin_web_host_dispatch_pointer", [
            event.pointerId >>> 0, device,
            TerminPointerPhase.Move, point.x, point.y, Number(event.pressure) || 0,
        ]);
        if (device === TerminPointerDevice.Mouse) {
            this.invoke("_termin_web_host_dispatch_mouse_move", [point.x, point.y]);
        }
    }

    onPointerEnd(event, cancelled) {
        if (!this.enabled) return;
        event.preventDefault?.();
        const point = canvasPoint(this.canvas, event);
        const device = pointerDevice(event.pointerType);
        this.invoke("_termin_web_host_dispatch_pointer", [
            event.pointerId >>> 0, device,
            cancelled ? TerminPointerPhase.Cancel : TerminPointerPhase.Up,
            point.x, point.y, Number(event.pressure) || 0,
        ]);
        if (device === TerminPointerDevice.Mouse) {
            this.invoke("_termin_web_host_dispatch_mouse_button", [
                point.x, point.y, terminMouseButton(event.button),
                TerminInputAction.Release, inputModifiers(event), event.detail || 1,
            ]);
        }
        this.activePointers.delete(event.pointerId);
        try {
            if (this.canvas.hasPointerCapture?.(event.pointerId)) {
                this.canvas.releasePointerCapture(event.pointerId);
            }
        } catch (error) {
            this.logger?.warn?.("TerminWebInputAdapter: pointer release failed", error);
        }
    }

    onWheel(event) {
        if (!this.enabled) return;
        event.preventDefault?.();
        const point = canvasPoint(this.canvas, event);
        const [wheelX, wheelY] = normalizedWheelDelta(event, this.canvas.height);
        this.invoke("_termin_web_host_dispatch_wheel", [
            point.x, point.y, wheelX, wheelY, inputModifiers(event),
        ]);
    }

    onKey(event, released) {
        if (!this.enabled) return;
        const key = terminKeyCode(event);
        if (key < 0) return;
        event.preventDefault?.();
        this.invoke("_termin_web_host_dispatch_key", [
            key,
            terminScanCode(event.code ?? ""),
            released ? TerminInputAction.Release :
                (event.repeat ? TerminInputAction.Repeat : TerminInputAction.Press),
            inputModifiers(event),
        ]);
        if (!released && !event.repeat && !event.isComposing &&
                !event.ctrlKey && !event.metaKey && event.key?.length === 1) {
            this.onText(event.key);
        }
    }

    onText(text) {
        if (!this.enabled || !text) return;
        const accepted = this.module.ccall(
            "termin_web_host_dispatch_text", "number", ["string"], [text]);
        if (!accepted) {
            this.logger?.error?.("TerminWebInputAdapter: native text dispatch rejected");
            return;
        }
        this.metrics.events += 1;
    }

    onFocusLost() {
        this.activePointers.clear();
        if (this.enabled) this.invoke("_termin_web_host_dispatch_focus_lost");
    }

    detach() {
        if (!this.attached) return;
        this.onFocusLost();
        this.enabled = false;
        for (const {target, type, handler, options} of this.listeners) {
            target?.removeEventListener?.(type, handler, options);
        }
        this.listeners.length = 0;
        this.resizeObserver?.disconnect?.();
        this.resizeObserver = null;
        this.attached = false;
    }
}

export function createTerminWebInputAdapter(core, options) {
    return new TerminWebInputAdapter(core, options);
}
