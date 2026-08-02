import path from "node:path";
import { readFile } from "node:fs/promises";
import { fileURLToPath, pathToFileURL } from "node:url";

const outputDirectory = process.env.TERMIN_WEB_CORE_DIR;
if (!outputDirectory) {
    throw new Error("TERMIN_WEB_CORE_DIR is required");
}

const loaderUrl = pathToFileURL(path.join(outputDirectory, "termin-web-core.mjs"));
const { createTerminCore } = await import(loaderUrl.href);
const hostUrl = pathToFileURL(path.join(outputDirectory, "termin-web-host.mjs"));
const { createTerminWebHost, TerminWebHostState } = await import(hostUrl.href);
const core = await createTerminCore({
    locateFile: (file) => path.join(outputDirectory, file),
});
core.smoke();

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
    ["invalid-package/", "version 2"],
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
console.log("TERMIN_WEB_CORE_NODE_SMOKE_PASSED");
