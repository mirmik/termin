// Inlined by package_web_html.py. All blob URLs belong to this document and
// must remain usable for later scene reloads and chart remounts.
(async () => {
    const imports = {};

    async function unpack(element) {
        const {terminAsset: name, mime} = element.dataset;
        const binary = atob(element.textContent);
        element.remove();
        const compressed = new Uint8Array(binary.length);
        for (let i = 0; i < binary.length; ++i) compressed[i] = binary.charCodeAt(i);
        const stream = new Blob([compressed]).stream().pipeThrough(new DecompressionStream("gzip"));
        const blob = await new Response(stream, {headers: {"Content-Type": mime}}).blob();
        const url = URL.createObjectURL(blob);
        if (mime === "text/javascript") {
            imports[name] = url;
        } else {
            const link = document.createElement("link");
            link.id = "termin-web-asset-" + name;
            link.rel = "termin-web-asset";
            link.href = url;
            document.head.append(link);
        }
    }

    await Promise.all(Array.from(document.querySelectorAll("script[data-termin-asset]"), unpack));
    const map = document.createElement("script");
    map.type = "importmap";
    map.textContent = JSON.stringify({imports});
    document.head.append(map);

    const entry = document.getElementById("termin-web-entry");
    const script = document.createElement("script");
    script.type = "module";
    script.textContent = entry.textContent;
    entry.replaceWith(script);
})().catch(error => {
    console.error("Termin standalone startup failed", error);
    const message = document.createElement("p");
    message.setAttribute("role", "alert");
    message.textContent = "Не удалось открыть сцену Termin: " + error.message;
    document.body.replaceChildren(message);
});
