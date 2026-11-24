export const TERMIN_WEB_ASSET_REVISION = "20261124-srgb1";

export function webAssetUrl(file, relativePath = file) {
    const embedded = globalThis.document?.getElementById(`termin-web-asset-${file}`);
    return embedded?.href ?? new URL(`${relativePath}?v=${TERMIN_WEB_ASSET_REVISION}`, import.meta.url).href;
}
