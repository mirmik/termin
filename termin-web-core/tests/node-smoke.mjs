import path from "node:path";
import { pathToFileURL } from "node:url";

const outputDirectory = process.env.TERMIN_WEB_CORE_DIR;
if (!outputDirectory) {
    throw new Error("TERMIN_WEB_CORE_DIR is required");
}

const loaderUrl = pathToFileURL(path.join(outputDirectory, "termin-web-core.mjs"));
const { createTerminCore } = await import(loaderUrl.href);
const core = await createTerminCore({
    locateFile: (file) => path.join(outputDirectory, file),
});
core.smoke();
console.log("TERMIN_WEB_CORE_NODE_SMOKE_PASSED");
