import {createTerminCore, webAssetUrl} from "./termin-web-core.mjs?v=20261124-shadows1";
import {createTerminWebHost} from "./termin-web-host.mjs?v=20261124-shadows1";

const mounted = new WeakSet();
const defaultPackage = webAssetUrl("graphics.trpkg");

function viewport(canvas) {
    const rect = canvas.getBoundingClientRect();
    const scale = window.devicePixelRatio || 1;
    return {
        width: Math.max(1, Math.round(rect.width * scale)),
        height: Math.max(1, Math.round(rect.height * scale)),
        scale,
    };
}

async function releaseChartHost(core, host) {
    try {
        await host?.teardown();
    } finally {
        core?.shutdown();
    }
}

export async function mountTerminChart(canvas, options, ChartType) {
    if (!(canvas instanceof HTMLCanvasElement) || canvas.getRootNode() !== document) {
        throw new TypeError(`${ChartType.name} requires a canvas mounted in the document`);
    }
    if (mounted.has(canvas)) throw new Error("This canvas already has a Termin chart");
    mounted.add(canvas);
    let core;
    let host;
    let chart;
    try {
        const initial = viewport(canvas);
        canvas.width = initial.width;
        canvas.height = initial.height;
        core = await createTerminCore();
        host = createTerminWebHost(core, {canvas, graphicsBackend: options.backend ?? "auto"});
        await host.initializeGraphics();
        await host.loadPackageBlob(options.packageUrl ?? defaultPackage);
        chart = new ChartType(canvas, core, host, initial.scale);
        chart.initialize(options);
        chart.attachInput();
        chart.observeSize();
        return chart;
    } catch (error) {
        if (chart) await chart.dispose();
        else {
            try {
                await releaseChartHost(core, host);
            } finally {
                mounted.delete(canvas);
            }
        }
        throw error;
    }
}

export class TerminWebChart {
    constructor(canvas, core, host, scale) {
        this.canvas = canvas;
        this.core = core;
        this.host = host;
        this.module = core.module;
        this.backend = host.graphicsBackend;
        this.scale = scale;
        this.disposed = false;
        this.events = new AbortController();
        this.resizeObserver = null;
        this.previousTouchAction = canvas.style.touchAction;
        this.addedTabIndex = !canvas.hasAttribute("tabindex");
        canvas.style.touchAction = "none";
        if (this.addedTabIndex) canvas.tabIndex = 0;
    }

    check(success) {
        if (!success) {
            const pointer = this.module[`${this.constructor.nativePrefix}_error`]();
            throw new Error(this.module.UTF8ToString(pointer) || `Native ${this.constructor.name} operation failed`);
        }
    }

    ensureLive() {
        if (this.disposed) throw new Error("This Termin chart has been disposed");
    }

    render() {
        this.ensureLive();
        this.check(this.module[`${this.constructor.nativePrefix}_render`]());
    }

    withDoubles(count, operation) {
        const bytes = count * Float64Array.BYTES_PER_ELEMENT;
        if (!Number.isSafeInteger(bytes) || bytes < 0 || bytes > 0xffffffff) {
            throw new RangeError("Chart data exceeds Wasm memory");
        }
        const pointer = bytes ? this.module._malloc(bytes) : 0;
        if (bytes && !pointer) throw new Error("Failed to allocate chart data in Wasm");
        try {
            return operation(pointer);
        } finally {
            if (pointer) this.module._free(pointer);
        }
    }

    resize() {
        this.ensureLive();
        const {width, height, scale} = viewport(this.canvas);
        if (width === this.canvas.width && height === this.canvas.height && scale === this.scale) return;
        this.canvas.width = width;
        this.canvas.height = height;
        this.resizeNative(width, height, scale);
        this.scale = scale;
        this.render();
    }

    observeSize() {
        this.resizeObserver = new ResizeObserver(() => this.resize());
        this.resizeObserver.observe(this.canvas);
        window.addEventListener("resize", () => this.resize(), {signal: this.events.signal});
    }

    dispose() {
        this.disposal ??= this.#release();
        return this.disposal;
    }

    async #release() {
        this.disposed = true;
        this.resizeObserver?.disconnect();
        this.events.abort();
        this.canvas.style.touchAction = this.previousTouchAction;
        if (this.addedTabIndex) this.canvas.removeAttribute("tabindex");
        try {
            try {
                this.check(this.module[`${this.constructor.nativePrefix}_destroy`]());
            } finally {
                await releaseChartHost(this.core, this.host);
            }
        } finally {
            mounted.delete(this.canvas);
            this.host = null;
            this.core = null;
            this.module = null;
        }
    }
}
