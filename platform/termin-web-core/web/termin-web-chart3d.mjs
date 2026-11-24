import {mountTerminChart, TerminWebChart} from "./termin-web-chart.mjs?v=20261124-shadows1";
import {canvasPoint, normalizedWheelDelta, TerminPointerPhase} from "./termin-web-input.mjs?v=20261124-shadows1";

/** Mount an interactive Cartesian tcplot surface chart in a canvas sized by CSS. */
export async function createTerminChart3D(canvas, options = {}) {
    return mountTerminChart(canvas, options, RetainedChart3D);
}

const orbitButton = 0;
const panButton = 2;
// One wheel step changes the native perspective camera distance by a factor of 0.9.
const pinchStep = Math.log(1 / 0.9);

class RetainedChart3D extends TerminWebChart {
    static nativePrefix = "_termin_web_chart3d";

    initialize({xLabel = "X", yLabel = "Y", zLabel = "Z"}) {
        this.fitNextSurface = true;
        this.check(this.module.ccall("termin_web_chart3d_create", "number",
            ["string", "string", "string"], [xLabel, yLabel, zLabel]));
        this.render();
    }

    /** z[row * x.length + column] is the height at (x[column], y[row]). */
    setSurface(x, y, z, {fit = this.fitNextSurface} = {}) {
        this.ensureLive();
        const columns = x?.length, rows = y?.length;
        const count = columns * rows;
        if (!Number.isSafeInteger(columns) || !Number.isSafeInteger(rows) || rows < 2 || columns < 2 ||
                !Number.isSafeInteger(count) || z?.length !== count) {
            throw new RangeError("A surface needs at least two coordinates on each axis and x.length * y.length heights");
        }
        this.withDoubles(3 * count, (pointer) => {
            const values = new Float64Array(this.module.HEAPU8.buffer, pointer, 3 * count);
            for (let row = 0; row < rows; row++) {
                const offset = row * columns;
                values.set(x, offset);
                values.fill(y[row], count + offset, count + offset + columns);
            }
            values.set(z, 2 * count);
            const bytes = count * Float64Array.BYTES_PER_ELEMENT;
            this.check(this.module._termin_web_chart3d_set_surface(
                pointer, pointer + bytes, pointer + 2 * bytes, rows, columns, Boolean(fit)));
        });
        this.fitNextSurface = false;
        this.render();
    }

    getCamera() {
        this.ensureLive();
        return this.withDoubles(10, (pointer) => {
            this.check(this.module._termin_web_chart3d_camera(pointer));
            const [targetX, targetY, targetZ, distance, azimuth, elevation, fovY, nearClip, farClip, orthoSize]
                = new Float64Array(this.module.HEAPU8.buffer, pointer, 10);
            return {targetX, targetY, targetZ, distance, azimuth, elevation, fovY, nearClip, farClip, orthoSize};
        });
    }

    fit() {
        this.ensureLive();
        this.check(this.module._termin_web_chart3d_fit());
        this.render();
    }

    reset() {
        this.ensureLive();
        this.check(this.module._termin_web_chart3d_reset());
        this.render();
    }

    resizeNative(width, height) {
        this.check(this.module._termin_web_chart3d_resize(width, height));
    }

    drag(from, to, button) {
        if (to.x === from.x && to.y === from.y) return false;
        const pointer = this.module._termin_web_chart3d_pointer;
        this.check(pointer(TerminPointerPhase.Down, from.x, from.y, button));
        // Orbit measures angular change per pixel. Pan projects the actual framebuffer positions.
        const x = button === orbitButton ? from.x + (to.x - from.x) / this.scale : to.x;
        const y = button === orbitButton ? from.y + (to.y - from.y) / this.scale : to.y;
        try {
            this.check(pointer(TerminPointerPhase.Move, x, y, button));
        } finally {
            pointer(TerminPointerPhase.Up, x, y, button);
        }
        return true;
    }

    attachInput() {
        const canvas = this.canvas;
        const signal = this.events.signal;
        const pointers = new Map();
        let pinchRemainder = 0;
        let wheelRemainder = 0;
        const middle = (a, b) => ({x: (a.x + b.x) / 2, y: (a.y + b.y) / 2});
        const span = (a, b) => Math.max(this.scale * 4, Math.hypot(a.x - b.x, a.y - b.y));
        const zoom = (point, steps) => {
            // Native wheel uses discrete steps. Carry fractional input across touch/trackpad events.
            for (let i = 0; i < Math.abs(steps); i++) {
                this.check(this.module._termin_web_chart3d_wheel(point.x, point.y, Math.sign(steps)));
            }
        };
        canvas.addEventListener("pointerdown", (event) => {
            if (event.button < 0 || event.button > 2 || pointers.size >= 2) return;
            if (pointers.size && (event.pointerType !== "touch" || !pointers.values().next().value.touch)) return;
            pointers.set(event.pointerId, {
                point: canvasPoint(canvas, event), touch: event.pointerType === "touch",
                button: event.shiftKey || event.button !== 0 ? panButton : orbitButton,
            });
            pinchRemainder = 0;
            canvas.setPointerCapture(event.pointerId);
            canvas.focus({preventScroll: true});
            event.preventDefault();
        }, {signal});
        canvas.addEventListener("pointermove", (event) => {
            const active = pointers.get(event.pointerId);
            if (!active) return;
            const from = active.point;
            const to = canvasPoint(canvas, event);
            active.point = to;
            if (pointers.size === 1) {
                if (this.drag(from, to, active.button)) this.render();
                return;
            }
            const other = Array.from(pointers.values()).find(entry => entry !== active).point;
            const center = middle(to, other);
            const changed = this.drag(middle(from, other), center, panButton);
            pinchRemainder += Math.log(span(to, other) / span(from, other)) / pinchStep;
            const steps = Math.trunc(pinchRemainder);
            pinchRemainder -= steps;
            zoom(center, steps);
            if (changed || steps) this.render();
        }, {signal});
        for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
            canvas.addEventListener(type, event => pointers.delete(event.pointerId), {signal});
        }
        canvas.addEventListener("contextmenu", event => event.preventDefault(), {signal});
        canvas.addEventListener("wheel", (event) => {
            const [, delta] = normalizedWheelDelta(event, canvas.clientHeight);
            if (!delta || !Number.isFinite(delta)) return;
            event.preventDefault();
            // Bound a single device event (e.g. a page scroll) to one decade of zoom.
            wheelRemainder += Math.max(-22, Math.min(22, delta));
            const steps = Math.trunc(wheelRemainder);
            if (steps) {
                wheelRemainder -= steps;
                zoom(canvasPoint(canvas, event), steps);
                this.render();
            }
        }, {signal, passive: false});
        canvas.addEventListener("keydown", (event) => {
            if (event.ctrlKey || event.altKey || event.metaKey || pointers.size) return;
            const center = {x: canvas.width / 2, y: canvas.height / 2};
            if (event.key === "+" || event.key === "=" || event.key === "-") {
                zoom(center, event.key === "-" ? -1 : 1);
            } else if (event.key === "Home") {
                event.preventDefault();
                this.reset();
                return;
            } else {
                const dx = Number(event.key === "ArrowRight") - Number(event.key === "ArrowLeft");
                const dy = Number(event.key === "ArrowDown") - Number(event.key === "ArrowUp");
                if (!dx && !dy) return;
                const distance = 24 * this.scale;
                this.drag(center, {x: center.x + dx * distance, y: center.y + dy * distance},
                    event.shiftKey ? panButton : orbitButton);
            }
            event.preventDefault();
            this.render();
        }, {signal});
    }
}
