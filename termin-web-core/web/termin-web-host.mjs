export const TerminWebHostState = Object.freeze({
    Idle: "idle",
    Loading: "loading",
    Ready: "ready",
    Running: "running",
    Stopped: "stopped",
    Error: "error",
});

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

export class TerminWebHost {
    constructor(core, options = {}) {
        this.module = core.module ?? core;
        this.statusElement = options.statusElement ?? null;
        this.onStateChange = options.onStateChange ?? null;
        this.logger = options.logger ?? globalThis.console;
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
        this.frameRequest = 0;
        this.lastTimestamp = null;
        this.generation = 0;
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
            for (const scene of manifest.scenes) {
                if (!scene || typeof scene.path !== "string" || !scene.path) {
                    throw new Error("runtime scene entries require a non-empty path");
                }
                validateRelativePackagePath(scene.path);
                const bytes = await this.fetchFile(new URL(scene.path, base), scene.path);
                const destination = `${root}/${scene.path}`;
                this.module.FS.mkdirTree(parentPath(destination));
                this.module.FS.writeFile(destination, bytes);
            }
            const loaded = this.module.ccall(
                "termin_web_host_load", "number", ["string"], [root]);
            if (!loaded) {
                const message = this.module.UTF8ToString(
                    this.module._termin_web_host_error());
                throw new Error(message || "native runtime package load failed");
            }
            this.nativeLoaded = true;
            this.setState(TerminWebHostState.Ready);
            if (autoStart) this.start();
            return this;
        } catch (error) {
            if (this.nativeLoaded) this.module._termin_web_host_unload();
            this.nativeLoaded = false;
            if (this.packageRoot) removeTree(this.module.FS, this.packageRoot);
            this.packageRoot = "";
            this.setState(TerminWebHostState.Error, error.message);
            this.logger?.error?.("TerminWebHost load failed:", error);
            throw error;
        }
    }

    start() {
        if (this.state !== TerminWebHostState.Ready &&
                this.state !== TerminWebHostState.Stopped) {
            throw new Error(`cannot start runtime host from state ${this.state}`);
        }
        this.lastTimestamp = null;
        this.setState(TerminWebHostState.Running);
        this.frameRequest = this.requestFrame((timestamp) => this.tick(timestamp));
    }

    tick(timestamp) {
        if (this.state !== TerminWebHostState.Running) return;
        const delta = this.lastTimestamp === null
            ? 0
            : Math.min(Math.max((timestamp - this.lastTimestamp) / 1000, 0), 1);
        this.lastTimestamp = timestamp;
        try {
            if (this.module._termin_web_host_tick(delta)) {
                this.frameRequest = this.requestFrame((next) => this.tick(next));
                return;
            }
            throw new Error(this.module.UTF8ToString(
                this.module._termin_web_host_error()) || "runtime update failed");
        } catch (error) {
            this.stop();
            this.setState(TerminWebHostState.Error, error.message);
            this.logger?.error?.("TerminWebHost update failed:", error);
        }
    }

    stop() {
        if (this.frameRequest) this.cancelFrame(this.frameRequest);
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
        if (this.nativeLoaded) this.module._termin_web_host_unload();
        this.nativeLoaded = false;
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
