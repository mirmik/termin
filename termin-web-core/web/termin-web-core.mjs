import createTerminWebCore from "./termin_web_core.mjs?v=20260807-textureops1";

export const TERMIN_WEB_ASSET_REVISION = "20260807-textureops1";

export async function createTerminCore(options = {}) {
    const module = await createTerminWebCore({
        locateFile: (file) => new URL(
            `${file}?v=${TERMIN_WEB_ASSET_REVISION}`, import.meta.url).href,
        ...options,
    });
    return {
        module,
        smoke() {
            const result = module._termin_web_core_smoke();
            if (result !== 0x5443) {
                throw new Error(`Termin Web core smoke failed with code ${result}`);
            }
            return result;
        },
        lifecycleSmoke() {
            const result = module._termin_web_core_lifecycle_smoke();
            if (result !== 0x5743) {
                throw new Error(`Termin Web lifecycle smoke failed with code ${result}`);
            }
            return result;
        },
        shutdown() {
            if (!module._termin_web_core_shutdown()) {
                throw new Error("Termin Web core shutdown failed");
            }
        },
        async renderSmoke() {
            module._termin_web_render_smoke_start();
            for (;;) {
                const status = module._termin_web_render_smoke_status();
                if (status === 2) {
                    // WebGPU validation is asynchronous. Give uncaptured-error
                    // and device-loss callbacks a turn before accepting the frame.
                    await new Promise((resolve) => setTimeout(resolve, 200));
                    const settledStatus = module._termin_web_render_smoke_status();
                    if (settledStatus < 0) {
                        const error = module.UTF8ToString(module._termin_web_render_smoke_error());
                        throw new Error(`Termin WebGPU smoke failed (${settledStatus}): ${error}`);
                    }
                    return;
                }
                if (status < 0) {
                    const error = module.UTF8ToString(module._termin_web_render_smoke_error());
                    throw new Error(`Termin WebGPU smoke failed (${status}): ${error}`);
                }
                await new Promise((resolve) => setTimeout(resolve, 20));
            }
        },
        resize(width, height) {
            if (!module._termin_web_render_smoke_resize(width, height)) {
                const error = module.UTF8ToString(module._termin_web_render_smoke_error());
                throw new Error(`Termin WebGPU resize failed: ${error}`);
            }
        },
    };
}
