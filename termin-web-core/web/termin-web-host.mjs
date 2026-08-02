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

function parentPath(path) {
    const separator = path.lastIndexOf("/");
    return separator > 0 ? path.slice(0, separator) : "/";
}

function validateRelativePackagePath(path) {
    if (!path || path.startsWith("/") || path.includes("\\") ||
            /^[A-Za-z][A-Za-z0-9+.-]*:/.test(path)) {
        throw new Error(`runtime package path must be relative: ${path}`);
    }
    if (path.split("/").some((segment) => segment === "." || segment === "..")) {
        throw new Error(`runtime package path must not contain dot segments: ${path}`);
    }
}

function removeTree(FS, root) {
    try {
        for (const name of FS.readdir(root)) {
            if (name === "." || name === "..") continue;
            const path = `${root}/${name}`;
            if (FS.isDir(FS.stat(path).mode)) removeTree(FS, path);
            else FS.unlink(path);
        }
        FS.rmdir(root);
    } catch (error) {
        if (error?.errno !== 44) throw error;
    }
}

function describeThrown(module, error) {
    if (error instanceof Error) return error.message;
    try {
        const [type, message] = module.getExceptionMessage(error);
        if (message) return type ? `${type}: ${message}` : message;
    } catch {
        // Not an Emscripten C++ exception; use its serializable JS shape below.
    }
    try {
        return JSON.stringify(error);
    } catch {
        return String(error);
    }
}

function collectArtifactPaths(value, result) {
    if (typeof value === "string") {
        validateRelativePackagePath(value);
        result.add(value);
        if (value.endsWith(".wgsl")) result.add(`${value}.layout.json`);
        return;
    }
    if (!value || typeof value !== "object") return;
    for (const child of Object.values(value)) collectArtifactPaths(child, result);
}

function resourceDependencyPaths(type, spec) {
    const result = new Set();
    if (!spec || typeof spec !== "object") return result;
    if (type === "shader") {
        for (const name of [
            "vertex_source_path", "fragment_source_path", "geometry_source_path",
        ]) {
            const path = spec[name];
            if (typeof path === "string" && path) {
                validateRelativePackagePath(path);
                result.add(path);
            }
        }
        collectArtifactPaths(spec.artifacts, result);
    } else if (type === "texture") {
        const path = spec.source_path;
        if (typeof path === "string" && path) {
            validateRelativePackagePath(path);
            result.add(path);
        }
    }
    return result;
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
        this.packageRoot = "";
        this.nativeLoaded = false;
        this.graphicsStarted = false;
        this.frameRequest = 0;
        this.lastTimestamp = null;
        this.lastObservedFrameCount = 0;
        this.generation = 0;
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
            graphicsInitMs: 0,
            nativeLoadMs: 0,
            startupMs: 0,
            firstFrameMs: 0,
            lastFrameMs: 0,
            averageFrameMs: 0,
            maxFrameMs: 0,
            measuredFrames: 0,
        };
        const generation = ++this.generation;
        try {
            const base = packageBaseUrl(packageUrl);
            const manifestBytes = await this.fetchFile(
                new URL("manifest.json", base), "manifest.json");
            let manifest;
            try {
                manifest = JSON.parse(new TextDecoder().decode(manifestBytes));
            } catch (error) {
                throw new Error(`malformed manifest.json: ${error.message}`);
            }
            if (!manifest || !Array.isArray(manifest.scenes)) {
                throw new Error("manifest scenes must be a list");
            }

            const root = `/termin-runtime/package-${generation}`;
            this.module.FS.mkdirTree(root);
            this.packageRoot = root;
            this.module.FS.writeFile(`${root}/manifest.json`, manifestBytes);
            const packageFiles = new Map();
            const builtinContract = manifest.builtin_shader_contract;
            if (builtinContract && typeof builtinContract === "object") {
                if (typeof builtinContract.catalog === "string" &&
                        builtinContract.catalog) {
                    validateRelativePackagePath(builtinContract.catalog);
                    packageFiles.set(
                        builtinContract.catalog,
                        await this.fetchFile(
                            new URL(builtinContract.catalog, base),
                            builtinContract.catalog));
                }
                if (Array.isArray(builtinContract.shaders)) {
                    for (const shader of builtinContract.shaders) {
                        const artifacts = new Set();
                        collectArtifactPaths(shader?.artifacts, artifacts);
                        for (const artifact of artifacts) {
                            packageFiles.set(
                                artifact,
                                await this.fetchFile(new URL(artifact, base), artifact));
                        }
                    }
                }
            }
            for (const scene of manifest.scenes) {
                if (!scene || typeof scene.path !== "string" || !scene.path) {
                    throw new Error("runtime scene entries require a non-empty path");
                }
                validateRelativePackagePath(scene.path);
                packageFiles.set(
                    scene.path,
                    await this.fetchFile(new URL(scene.path, base), scene.path));
            }
            if (!Array.isArray(manifest.resources)) {
                throw new Error("manifest resources must be a list");
            }
            for (const resource of manifest.resources) {
                if (!resource || typeof resource.type !== "string" ||
                        typeof resource.path !== "string" || !resource.path) {
                    throw new Error("runtime resource entries require type and path");
                }
                validateRelativePackagePath(resource.path);
                const specBytes = await this.fetchFile(
                    new URL(resource.path, base), resource.path);
                packageFiles.set(resource.path, specBytes);
                let spec = null;
                if (resource.type === "shader" || resource.type === "texture") {
                    try {
                        spec = JSON.parse(new TextDecoder().decode(specBytes));
                    } catch (error) {
                        throw new Error(`malformed ${resource.path}: ${error.message}`);
                    }
                }
                for (const dependency of resourceDependencyPaths(resource.type, spec)) {
                    if (!packageFiles.has(dependency)) {
                        packageFiles.set(
                            dependency,
                            await this.fetchFile(new URL(dependency, base), dependency));
                    }
                }
            }
            for (const [path, bytes] of packageFiles) {
                const destination = `${root}/${path}`;
                this.module.FS.mkdirTree(parentPath(destination));
                this.module.FS.writeFile(destination, bytes);
            }
            this.metrics.packageFetchMs = performance.now() - loadStartedAt;
            const graphicsStartedAt = performance.now();
            if (!this.headless) await this.initializeGraphics();
            this.metrics.graphicsInitMs = performance.now() - graphicsStartedAt;
            const nativeLoadStartedAt = performance.now();
            const loaded = this.module.ccall(
                this.headless ? "termin_web_host_load_headless" : "termin_web_host_load",
                "number", ["string"], [root]);
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
            if (this.packageRoot) removeTree(this.module.FS, this.packageRoot);
            this.packageRoot = "";
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
        if (this.packageRoot) removeTree(this.module.FS, this.packageRoot);
        this.packageRoot = "";
        if (this.state !== TerminWebHostState.Idle) {
            this.setState(TerminWebHostState.Idle);
        }
    }
}

export function createTerminWebHost(core, options = {}) {
    return new TerminWebHost(core, options);
}
