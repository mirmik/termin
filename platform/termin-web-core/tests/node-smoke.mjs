import path from "node:path";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";

const outputDirectory = process.env.TERMIN_WEB_CORE_DIR;
if (!outputDirectory) {
    throw new Error("TERMIN_WEB_CORE_DIR is required");
}

const loaderUrl = pathToFileURL(path.join(outputDirectory, "termin-web-core.mjs"));
const { createTerminCore } = await import(loaderUrl.href);
const hostUrl = pathToFileURL(path.join(outputDirectory, "termin-web-host.mjs"));
const {
    assertTerminWebEnvironment,
    createTerminWebHost,
    terminWebEnvironment,
    TerminWebHostState,
} = await import(hostUrl.href);
const inputUrl = pathToFileURL(path.join(outputDirectory, "termin-web-input.mjs"));
const {
    createTerminWebInputAdapter,
    inputModifiers,
    pointerDevice,
    terminKeyCode,
    terminMouseButton,
    terminScanCode,
} = await import(inputUrl.href);
const core = await createTerminCore({
    locateFile: (file) => path.join(outputDirectory, file),
});
core.smoke();
core.lifecycleSmoke();

assert.deepEqual(terminWebEnvironment({
    isSecureContext: true,
    crossOriginIsolated: false,
    navigator: {gpu: {}},
}), {secureContext: true, webGpu: true, webGl2: false, crossOriginIsolated: false});
assert.throws(
    () => assertTerminWebEnvironment({isSecureContext: false, navigator: {gpu: {}}}),
    /WebGL 2, or WebGPU/);
assert.throws(
    () => assertTerminWebEnvironment({isSecureContext: true, navigator: {}}),
    /WebGL 2, or WebGPU/);
assert.equal(assertTerminWebEnvironment({
    isSecureContext: false,
    navigator: {},
    WebGL2RenderingContext: class {},
}).webGl2, true);

assert.equal(inputModifiers({shiftKey: true, ctrlKey: true, altKey: false, metaKey: true}), 11);
assert.equal(terminKeyCode({key: "w"}), 87);
assert.equal(terminKeyCode({key: "ArrowLeft"}), 263);
assert.equal(terminScanCode("KeyA"), 4);
assert.equal(terminMouseButton(1), 2);
assert.equal(terminMouseButton(2), 1);
assert.equal(pointerDevice(undefined), 0);

class FakeEventTarget {
    constructor() {
        this.listeners = new Map();
    }
    addEventListener(type, listener) {
        if (!this.listeners.has(type)) this.listeners.set(type, new Set());
        this.listeners.get(type).add(listener);
    }
    removeEventListener(type, listener) {
        this.listeners.get(type)?.delete(listener);
    }
    emit(type, event = {}) {
        for (const listener of this.listeners.get(type) ?? []) listener(event);
    }
}

class FakeCanvas extends FakeEventTarget {
    constructor() {
        super();
        this.width = 100;
        this.height = 50;
        this.tabIndex = -1;
        this.rect = {left: 10, top: 20, width: 200, height: 100};
    }
    hasAttribute() { return false; }
    getBoundingClientRect() { return this.rect; }
    focus() {}
    setPointerCapture() {}
    hasPointerCapture() { return true; }
    releasePointerCapture() {}
}

const inputCalls = [];
const fakeModule = new Proxy({
    ccall(name, returnType, argumentTypes, args) {
        inputCalls.push({name, args});
        return 1;
    },
}, {
    get(target, property) {
        if (property in target) return target[property];
        if (typeof property === "string" && property.startsWith("_termin_web_host_")) {
            return (...args) => {
                inputCalls.push({name: property, args});
                return 1;
            };
        }
        return undefined;
    },
});
const fakeCanvas = new FakeCanvas();
const fakeWindow = new FakeEventTarget();
const fakeDocument = new FakeEventTarget();
fakeDocument.hidden = false;
const inputAdapter = createTerminWebInputAdapter(fakeModule, {
    canvas: fakeCanvas,
    window: fakeWindow,
    document: fakeDocument,
    ResizeObserver: null,
    devicePixelRatio: () => 2,
    logger: {error() {}, warn() {}},
}).attach();
assert.deepEqual([fakeCanvas.width, fakeCanvas.height], [400, 200]);
inputAdapter.setEnabled(true);
fakeCanvas.emit("pointerdown", {
    pointerId: 7, pointerType: "mouse", button: 1, detail: 1,
    clientX: 110, clientY: 70, pressure: 0.5,
    shiftKey: false, ctrlKey: false, altKey: false, metaKey: false,
    preventDefault() {},
});
fakeCanvas.emit("pointermove", {
    pointerId: 7, pointerType: "mouse", clientX: 150, clientY: 80, pressure: 0.5,
});
assert.deepEqual(inputCalls[0], {
    name: "_termin_web_host_dispatch_pointer",
    args: [7, 0, 0, 200, 100, 0.5],
});
assert.equal(inputCalls[1].name, "_termin_web_host_dispatch_mouse_button");
assert.equal(inputCalls[1].args[2], 2);
assert.equal(inputCalls[2].name, "_termin_web_host_dispatch_pointer");
assert.equal(inputCalls[3].name, "_termin_web_host_dispatch_mouse_move");
fakeCanvas.emit("pointermove", {
    pointerId: 8, clientX: 160, clientY: 85, pressure: 0,
});
assert.equal(inputCalls.at(-1).name, "_termin_web_host_dispatch_mouse_move");
fakeCanvas.rect = {left: 10, top: 20, width: 300, height: 150};
assert.equal(inputAdapter.syncCanvasSize(), true);
assert.deepEqual(inputCalls.at(-1), {
    name: "_termin_web_host_resize",
    args: [600, 300],
});
inputAdapter.setEnabled(false);
assert.equal(inputCalls.at(-1).name, "_termin_web_host_dispatch_focus_lost");
inputAdapter.detach();

async function fetchFile(url) {
    try {
        const bytes = await readFile(fileURLToPath(url));
        return {
            ok: true,
            status: 200,
            async arrayBuffer() {
                return bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
            },
        };
    } catch (error) {
        if (error.code !== "ENOENT") throw error;
        return {
            ok: false,
            status: 404,
            async arrayBuffer() {
                return new ArrayBuffer(0);
            },
        };
    }
}

let nextFrame = 1;
let timestamp = 0;
const frameTimers = new Map();
function requestFrame(callback) {
    const id = nextFrame++;
    const timer = setTimeout(() => {
        frameTimers.delete(id);
        timestamp += 1000 / 60;
        callback(timestamp);
    }, 0);
    frameTimers.set(id, timer);
    return id;
}
function cancelFrame(id) {
    clearTimeout(frameTimers.get(id));
    frameTimers.delete(id);
}

const fixtures = pathToFileURL(path.join(outputDirectory, "fixtures") + path.sep);
const host = createTerminWebHost(core, {
    headless: true,
    fetch: fetchFile,
    requestAnimationFrame: requestFrame,
    cancelAnimationFrame: cancelFrame,
    logger: {error() {}},
});
await host.load(new URL("core-package/", fixtures));
assert.equal(host.metrics.packageRequests, 1);
assert.equal(host.metrics.packageProvider, "blob");
assert.equal(core.module.FS.analyzePath("/termin-runtime").exists, false);
await host.waitForFrames(3);
if (host.state !== TerminWebHostState.Running || host.entityCount() !== 1) {
    throw new Error("runtime host did not run the packaged entry scene");
}
await host.reload(new URL("core-package/", fixtures));
await host.waitForFrames(2);
if (host.entityCount() !== 1) {
    throw new Error("runtime host reload lost the entry scene");
}
await host.teardown();
if (host.state !== TerminWebHostState.Idle || host.entityCount() !== 0) {
    throw new Error("runtime host teardown did not release the package");
}
for (const [fixture, expected] of [
    ["invalid-package/", "version 3"],
    ["invalid-path-package/", "dot segments"],
    ["unsupported-component-package/", "MeshComponent"],
    ["unsupported-resource-package/", "Texture"],
    ["missing-package/", "HTTP 404"],
]) {
    try {
        await host.load(new URL(fixture, fixtures));
        throw new Error(`${fixture} unexpectedly loaded`);
    } catch (error) {
        if (!error.message.includes(expected) || host.state !== TerminWebHostState.Error) {
            throw error;
        }
    }
}
await host.teardown();
const corruptingHost = createTerminWebHost(core, {
    headless: true,
    async fetch(url) {
        const response = await fetchFile(url);
        if (!response.ok) return response;
        const bytes = new Uint8Array(await response.arrayBuffer());
        bytes[bytes.length - 1] ^= 0xff;
        return {
            ok: true,
            status: 200,
            async arrayBuffer() { return bytes.buffer; },
        };
    },
    requestAnimationFrame: requestFrame,
    cancelAnimationFrame: cancelFrame,
    logger: {error() {}},
});
await assert.rejects(
    corruptingHost.load(new URL("core-package/", fixtures)),
    /hash mismatch/);
await corruptingHost.teardown();
core.shutdown();
core.lifecycleSmoke();
core.shutdown();

const simulatedDeviceLossModule = {
    _termin_web_host_frame_count() { return 1; },
    _termin_web_host_error() { return 1; },
    _termin_web_host_loop_stop() {},
    UTF8ToString(pointer) {
        return pointer === 1 ? "device lost: simulated" : "";
    },
};
const simulatedDeviceLossHost = createTerminWebHost(simulatedDeviceLossModule, {
    fetch: fetchFile,
    requestAnimationFrame: requestFrame,
    cancelAnimationFrame: cancelFrame,
    logger: {error() {}},
});
simulatedDeviceLossHost.state = TerminWebHostState.Running;
simulatedDeviceLossHost.nativeLoaded = true;
simulatedDeviceLossHost.tick(1000 / 60);
assert.equal(simulatedDeviceLossHost.state, TerminWebHostState.Error);
assert.match(simulatedDeviceLossHost.error, /device lost: simulated/);

console.log("TERMIN_WEB_CORE_NODE_SMOKE_PASSED");
