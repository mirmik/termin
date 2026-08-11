export const TerminWebHostState = Object.freeze({
    Idle: "idle",
    Loading: "loading",
    Ready: "ready",
    Running: "running",
    Stopped: "stopped",
    Error: "error",
});

export function terminWebEnvironment(scope = globalThis) {
    return Object.freeze({
        secureContext: scope.isSecureContext === true,
        webGpu: Boolean(scope.navigator?.gpu),
        crossOriginIsolated: scope.crossOriginIsolated === true,
    });
}

export function assertTerminWebEnvironment(scope = globalThis) {
    const environment = terminWebEnvironment(scope);
    if (!environment.secureContext) {
        throw new Error(
            "Termin Web requires a secure context (HTTPS or loopback localhost)");
    }
    if (!environment.webGpu) {
        throw new Error("Termin Web requires a browser with WebGPU support");
    }
    return environment;
}

function packageBaseUrl(packageUrl) {
    const base = new URL(packageUrl, globalThis.location?.href ?? import.meta.url);
    return base.href.endsWith("/") ? base : new URL(`${base.href}/`);
}

function describeThrown(module, error) {
    if (error instanceof Error && error.message) return error.message;
    try {
        const [type, message] = module.getExceptionMessage(error);
        if (message) return type ? `${type}: ${message}` : message;
    } catch {
        // Not an Emscripten C++ exception; use its serializable JS shape below.
    }
    if (error instanceof Error && error.cause !== undefined) {
        const cause = describeThrown(module, error.cause);
        if (cause) return cause;
    }
    try {
        const serialized = JSON.stringify(error);
        if (serialized && serialized !== "{}") return serialized;
    } catch {
        // Fall through to the generic string representation.
    }
    return String(error);
}

export class TerminWebHost {
    constructor(core, options = {}) {
        this.module = core.module ?? core;
        this.statusElement = options.statusElement ?? null;
        this.onStateChange = options.onStateChange ?? null;
        this.onFrame = options.onFrame ?? null;
        this.logger = options.logger ?? globalThis.console;
        this.headless = options.headless ?? false;
        this.fetch = options.fetch ?? globalThis.fetch?.bind(globalThis);
        this.requestFrame = options.requestAnimationFrame ??
            globalThis.requestAnimationFrame?.bind(globalThis);
        this.cancelFrame = options.cancelAnimationFrame ??
            globalThis.cancelAnimationFrame?.bind(globalThis);
        if (!this.fetch) throw new Error("TerminWebHost requires fetch");
        if (!this.requestFrame || !this.cancelFrame) {
            throw new Error("TerminWebHost requires requestAnimationFrame support");
        }
        this.state = TerminWebHostState.Idle;
        this.error = "";
        this.packageBlobUrl = "";
        this.nativeLoaded = false;
        this.graphicsStarted = false;
        this.frameRequest = 0;
        this.lastTimestamp = null;
        this.lastObservedFrameCount = 0;
        this.loadStartedAt = 0;
        this.metrics = {};
        this.setState(this.state);
    }

    setState(state, error = "") {
        this.state = state;
        this.error = error;
        if (this.statusElement) {
            this.statusElement.textContent = error ? `${state}: ${error}` : state;
            this.statusElement.dataset.state = state;
        }
        this.onStateChange?.({state, error});
    }

    async fetchFile(url, label) {
        const response = await this.fetch(url);
        if (!response.ok) {
            throw new Error(`failed to fetch ${label}: HTTP ${response.status}`);
        }
        return new Uint8Array(await response.arrayBuffer());
    }

    async load(packageUrl, {autoStart = true} = {}) {
        if (this.state === TerminWebHostState.Loading) {
            throw new Error("runtime package load is already in progress");
        }
        await this.teardown();
        this.setState(TerminWebHostState.Loading);
        const loadStartedAt = performance.now();
        this.loadStartedAt = loadStartedAt;
        this.metrics = {
            packageFetchMs: 0,
            packageBytes: 0,
            packageRequests: 0,
            packageProvider: "blob",
            graphicsInitMs: 0,
            nativeLoadMs: 0,
            startupMs: 0,
            firstFrameMs: 0,
            lastFrameMs: 0,
            averageFrameMs: 0,
            maxFrameMs: 0,
            measuredFrames: 0,
        };
        try {
            const supplied = new URL(packageUrl, globalThis.location?.href ?? import.meta.url);
            const blobUrl = supplied.pathname.endsWith(".trpkg")
                ? supplied
                : new URL("package.trpkg", packageBaseUrl(supplied));
            this.packageBlobUrl = blobUrl.href;
            const packageBlob = await this.fetchFile(blobUrl, "runtime package blob");
            this.metrics.packageBytes = packageBlob.byteLength;
            this.metrics.packageRequests = 1;
            const pointer = this.module._malloc(packageBlob.byteLength);
            if (!pointer) throw new Error("failed to allocate runtime package blob memory");
            try {
                this.module.HEAPU8.set(packageBlob, pointer);
                if (!this.module._termin_web_host_set_package_blob(
                        pointer, packageBlob.byteLength)) {
                    const message = this.module.UTF8ToString(
                        this.module._termin_web_host_error());
                    throw new Error(message || "native runtime package blob validation failed");
                }
            } finally {
                this.module._free(pointer);
            }
            this.metrics.packageFetchMs = performance.now() - loadStartedAt;
            const graphicsStartedAt = performance.now();
            if (!this.headless) await this.initializeGraphics();
            this.metrics.graphicsInitMs = performance.now() - graphicsStartedAt;
            const nativeLoadStartedAt = performance.now();
            const loaded = this.module.ccall(
                this.headless ? "termin_web_host_load_headless" : "termin_web_host_load",
                "number", ["string"], [""]);
            if (!loaded) {
                const message = this.module.UTF8ToString(
                    this.module._termin_web_host_error());
                throw new Error(message || "native runtime package load failed");
            }
            this.metrics.nativeLoadMs = performance.now() - nativeLoadStartedAt;
            this.metrics.startupMs = performance.now() - loadStartedAt;
            this.nativeLoaded = true;
            this.setState(TerminWebHostState.Ready);
            this.logger?.info?.("TerminWebHost startup metrics", {...this.metrics});
            if (autoStart) this.start();
            return this;
        } catch (error) {
            const message = describeThrown(this.module, error);
            if (this.nativeLoaded || this.graphicsStarted) {
                this.module._termin_web_host_unload();
            }
            this.nativeLoaded = false;
            this.graphicsStarted = false;
            this.packageBlobUrl = "";
            this.setState(TerminWebHostState.Error, message);
            this.logger?.error?.("TerminWebHost load failed:", error);
            throw new Error(message, {cause: error});
        }
    }

    async initializeGraphics(timeoutMs = 5000) {
        assertTerminWebEnvironment(globalThis);
        const canvas = globalThis.document?.querySelector?.("#termin-canvas");
        if (!canvas) throw new Error("TerminWebHost requires #termin-canvas");
        const initial = this.module._termin_web_host_graphics_start(
            Number(canvas.width), Number(canvas.height));
        this.graphicsStarted = initial > 0;
        const deadline = performance.now() + timeoutMs;
        let status = initial;
        while (status === 1) {
            if (performance.now() >= deadline) {
                throw new Error("WebGPU player initialization timed out");
            }
            await new Promise((resolve) => setTimeout(resolve, 10));
            status = this.module._termin_web_host_graphics_status();
        }
        if (status !== 2) {
            const message = this.module.UTF8ToString(
                this.module._termin_web_host_graphics_error());
            throw new Error(message || "WebGPU player initialization failed");
        }
    }

    start() {
        if (this.state !== TerminWebHostState.Ready &&
                this.state !== TerminWebHostState.Stopped) {
            throw new Error(`cannot start runtime host from state ${this.state}`);
        }
        this.lastTimestamp = null;
        this.lastObservedFrameCount = this.frameCount();
        this.setState(TerminWebHostState.Running);
        if (!this.headless && !this.module._termin_web_host_loop_start()) {
            this.setState(TerminWebHostState.Error, this.module.UTF8ToString(
                this.module._termin_web_host_error()));
            throw new Error(this.error || "native browser frame loop failed to start");
        }
        this.frameRequest = this.requestFrame((timestamp) => this.tick(timestamp));
    }

    tick(timestamp) {
        if (this.state !== TerminWebHostState.Running) return;
        const delta = this.lastTimestamp === null
            ? 0
            : Math.min(Math.max((timestamp - this.lastTimestamp) / 1000, 0), 1);
        this.lastTimestamp = timestamp;
        try {
            const frameStartedAt = performance.now();
            const previousFrameCount = this.lastObservedFrameCount;
            const nativeFrameCount = this.headless
                ? previousFrameCount + Number(Boolean(this.module._termin_web_host_tick(delta)))
                : this.frameCount();
            const advanced = nativeFrameCount > previousFrameCount;
            if (this.headless && !advanced) {
                throw new Error(this.module.UTF8ToString(
                    this.module._termin_web_host_error()) || "runtime update failed");
            }
            if (!this.headless) {
                const nativeError = this.module.UTF8ToString(
                    this.module._termin_web_host_error());
                if (nativeError) throw new Error(nativeError);
            }
            if (advanced) {
                const frameMs = this.headless
                    ? performance.now() - frameStartedAt
                    : delta * 1000;
                const measuredFrames = this.metrics.measuredFrames + 1;
                this.metrics.lastFrameMs = frameMs;
                this.metrics.averageFrameMs +=
                    (frameMs - this.metrics.averageFrameMs) / measuredFrames;
                this.metrics.maxFrameMs = Math.max(this.metrics.maxFrameMs, frameMs);
                this.metrics.measuredFrames = measuredFrames;
                if (!this.metrics.firstFrameMs) {
                    this.metrics.firstFrameMs = performance.now() - this.loadStartedAt;
                }
                this.onFrame?.({
                    frameCount: nativeFrameCount,
                    timestamp,
                    metrics: this.metrics,
                });
                this.lastObservedFrameCount = nativeFrameCount;
            }
            this.frameRequest = this.requestFrame((next) => this.tick(next));
        } catch (error) {
            this.stop();
            this.setState(
                TerminWebHostState.Error,
                describeThrown(this.module, error));
            this.logger?.error?.("TerminWebHost update failed:", error);
        }
    }

    stop() {
        if (this.frameRequest) this.cancelFrame(this.frameRequest);
        if (!this.headless) this.module._termin_web_host_loop_stop();
        this.frameRequest = 0;
        this.lastTimestamp = null;
        if (this.state === TerminWebHostState.Running) {
            this.setState(TerminWebHostState.Stopped);
        }
    }

    frameCount() {
        return Number(this.module._termin_web_host_frame_count());
    }

    entityCount() {
        return Number(this.module._termin_web_host_entity_count());
    }

    async waitForFrames(minimum, timeoutMs = 3000) {
        const deadline = performance.now() + timeoutMs;
        while (this.frameCount() < minimum) {
            if (this.state === TerminWebHostState.Error) {
                throw new Error(this.error);
            }
            if (performance.now() >= deadline) {
                throw new Error(`runtime did not reach ${minimum} frames before timeout`);
            }
            await new Promise((resolve) => setTimeout(resolve, 10));
        }
    }

    async reload(packageUrl, options = {}) {
        return this.load(packageUrl, options);
    }

    async teardown() {
        this.stop();
        // emscripten_request_animation_frame_loop is cancelled by its next
        // callback returning false. Let that callback observe loop_stop before
        // destroying the engine/device state it references.
        if (!this.headless && (this.nativeLoaded || this.graphicsStarted)) {
            await new Promise((resolve) => this.requestFrame(() => resolve()));
        }
        if (this.nativeLoaded || this.graphicsStarted) {
            this.module._termin_web_host_unload();
        }
        this.nativeLoaded = false;
        this.graphicsStarted = false;
        this.packageBlobUrl = "";
        if (this.state !== TerminWebHostState.Idle) {
            this.setState(TerminWebHostState.Idle);
        }
    }
}

export function createTerminWebHost(core, options = {}) {
    return new TerminWebHost(core, options);
}
