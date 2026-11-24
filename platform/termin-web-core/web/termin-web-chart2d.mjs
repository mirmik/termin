import {mountTerminChart, TerminWebChart} from "./termin-web-chart.mjs?v=20261124-srgb1";
import {canvasPoint, normalizedWheelDelta, TerminPointerPhase} from "./termin-web-input.mjs?v=20261124-srgb1";

/** Mount an interactive tcplot line chart. Give the canvas a size in CSS pixels. */
export async function createTerminChart2D(canvas, options = {}) {
    return mountTerminChart(canvas, options, RetainedChart2D);
}

class RetainedChart2D extends TerminWebChart {
    static nativePrefix = "_termin_web_chart2d";

    initialize({title = "", xLabel = "", yLabel = "", seriesName = "Series", range}) {
        this.fitNextSeries = true;
        this.check(this.module.ccall("termin_web_chart2d_create", "number",
            ["string", "string", "string", "string", "number"],
            [title, xLabel, yLabel, seriesName, this.scale]));
        if (range) this.setRange(range);
        else this.render();
    }

    /** Replace the series. Fit its first dataset, then preserve pan and zoom unless fit is requested. */
    setData(x, y, {fit = this.fitNextSeries} = {}) {
        this.ensureLive();
        if (!x || !y || !Number.isSafeInteger(x.length) || x.length !== y.length || x.length < 0) {
            throw new TypeError("Chart x and y must be numeric arrays of the same length");
        }
        const count = x.length;
        this.withDoubles(2 * count, (pointer) => {
            if (count) {
                const values = new Float64Array(this.module.HEAPU8.buffer, pointer, count * 2);
                values.set(x);
                values.set(y, count);
            }
            this.check(this.module._termin_web_chart2d_set_data(
                pointer, pointer + count * Float64Array.BYTES_PER_ELEMENT, count, Boolean(fit && count)));
        });
        if (count) this.fitNextSeries = false;
        this.render();
    }

    setRange({xMin, xMax, yMin, yMax}) {
        this.ensureLive();
        this.check(this.module._termin_web_chart2d_set_range(xMin, xMax, yMin, yMax));
        this.fitNextSeries = false;
        this.render();
    }

    getRange() {
        this.ensureLive();
        return this.withDoubles(4, (pointer) => {
            this.check(this.module._termin_web_chart2d_range(pointer));
            const [xMin, xMax, yMin, yMax] = new Float64Array(this.module.HEAPU8.buffer, pointer, 4);
            return {xMin, xMax, yMin, yMax};
        });
    }

    resizeNative(width, height, scale) {
        this.check(this.module._termin_web_chart2d_resize(width, height, scale));
    }

    attachInput() {
        const canvas = this.canvas;
        const signal = this.events.signal;
        const panButton = 2; // tcplot uses middle-button drag; map touch and primary drags to pan too.
        let pointerId = null;
        const dispatch = (phase, event) => {
            const {x, y} = canvasPoint(canvas, event);
            return this.module._termin_web_chart2d_pointer(phase, x, y, panButton);
        };
        canvas.addEventListener("pointerdown", (event) => {
            if (pointerId !== null || (event.button !== 0 && event.button !== 1)) return;
            if (dispatch(TerminPointerPhase.Down, event)) {
                pointerId = event.pointerId;
                canvas.setPointerCapture(pointerId);
                canvas.focus({preventScroll: true});
                event.preventDefault();
            }
        }, {signal});
        canvas.addEventListener("pointermove", (event) => {
            if (pointerId === event.pointerId && dispatch(TerminPointerPhase.Move, event)) this.render();
        }, {signal});
        const endPan = (event) => {
            if (event.pointerId !== pointerId) return;
            dispatch(event.type === "pointerup" ? TerminPointerPhase.Up : TerminPointerPhase.Cancel, event);
            pointerId = null;
        };
        for (const type of ["pointerup", "pointercancel", "lostpointercapture"]) {
            canvas.addEventListener(type, endPan, {signal});
        }
        canvas.addEventListener("wheel", (event) => {
            const {x, y} = canvasPoint(canvas, event);
            const [, steps] = normalizedWheelDelta(event, canvas.clientHeight);
            if (this.module._termin_web_chart2d_wheel(x, y, steps, event.shiftKey)) {
                event.preventDefault();
                this.render();
            }
        }, {signal, passive: false});
        canvas.addEventListener("keydown", (event) => {
            if (event.ctrlKey || event.altKey || event.metaKey || pointerId !== null) return;
            const x = canvas.width / 2;
            const y = canvas.height / 2;
            let changed = false;
            if (event.key === "+" || event.key === "=" || event.key === "-") {
                changed = this.module._termin_web_chart2d_wheel(x, y, event.key === "-" ? -1 : 1, false);
            } else {
                const dx = Number(event.key === "ArrowLeft") - Number(event.key === "ArrowRight");
                const dy = Number(event.key === "ArrowUp") - Number(event.key === "ArrowDown");
                if ((!dx && !dy) || !this.module._termin_web_chart2d_pointer(TerminPointerPhase.Down, x, y, panButton)) return;
                changed = this.module._termin_web_chart2d_pointer(TerminPointerPhase.Move,
                    x + dx * canvas.width * 0.1, y + dy * canvas.height * 0.1, panButton);
                this.module._termin_web_chart2d_pointer(TerminPointerPhase.Up, x, y, panButton);
            }
            if (changed) {
                event.preventDefault();
                this.render();
            }
        }, {signal});
    }
}
