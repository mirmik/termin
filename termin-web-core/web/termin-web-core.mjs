import createTerminWebCore from "./termin_web_core.mjs";

export async function createTerminCore(options = {}) {
    const module = await createTerminWebCore(options);
    return {
        module,
        smoke() {
            const result = module._termin_web_core_smoke();
            if (result !== 0x5443) {
                throw new Error(`Termin Web core smoke failed with code ${result}`);
            }
            return result;
        },
    };
}
