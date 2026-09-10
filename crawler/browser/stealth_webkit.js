// stealth_webkit.js

// Bypass window.navigator.webdriver
Object.defineProperty(navigator, 'webdriver', {
    get: () => false,
});

// Mock the MimeType object
const makeMimeType = (type, suffixes, description, plugin) => {
    const mime = Object.create(MimeType.prototype);
    Object.defineProperties(mime, {
        type: { value: type },
        suffixes: { value: suffixes },
        description: { value: description },
        enabledPlugin: { value: plugin },
    });
    return mime;
};

// Mock the Plugin object
const makePlugin = (name, filename, description) => {
    const plugin = Object.create(Plugin.prototype);
    
    const mime1 = makeMimeType('application/pdf', 'pdf', 'Portable Document Format', plugin);
    const mime2 = makeMimeType('text/pdf', 'pdf', 'Portable Document Format', plugin);

    Object.defineProperties(plugin, {
        name: { value: name },
        filename: { value: filename },
        description: { value: description },
        length: { value: 2 },
        0: { value: mime1 },
        1: { value: mime2 },
        'application/pdf': { value: mime1 },
        'text/pdf': { value: mime2 }
    });
    return plugin;
};

// Create standard WebKit plugins
const pluginNames = [
    "PDF Viewer",
    "Chrome PDF Viewer",
    "Chromium PDF Viewer",
    "Microsoft Edge PDF Viewer",
    "WebKit built-in PDF"
];

const plugins = pluginNames.map(name => 
    makePlugin(name, "internal-pdf-viewer", "Portable Document Format")
);

// Mock the PluginArray
const pluginArray = Object.create(PluginArray.prototype);
Object.defineProperties(pluginArray, {
    length: { value: plugins.length },
    ...plugins.reduce((acc, plugin, i) => {
        acc[i] = { value: plugin };
        acc[plugin.name] = { value: plugin };
        return acc;
    }, {})
});

// Overwrite navigator.plugins
Object.defineProperty(navigator, 'plugins', {
    get: () => pluginArray
});

// Overwrite navigator.mimeTypes
const mimeTypesArray = Object.create(MimeTypeArray.prototype);
Object.defineProperties(mimeTypesArray, {
    length: { value: 2 },
    0: { value: plugins[0][0] },
    1: { value: plugins[0][1] },
    'application/pdf': { value: plugins[0][0] },
    'text/pdf': { value: plugins[0][1] }
});

Object.defineProperty(navigator, 'mimeTypes', {
    get: () => mimeTypesArray
});