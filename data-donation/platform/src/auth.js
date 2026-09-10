const dotenv = require('dotenv');

dotenv.config();

// Default to a fallback if not found in .env
const ACCESS_KEY = process.env.ACCESS_KEY;

const allowedExtensions = [
    '.css', '.js', '.map', '.wasm', // Common static asset extensions
    '.png', '.jpg', '.jpeg', '.gif', '.svg', // Image formats
    '.txt', 
];

const requireKey = (req, res, next) => {

    // Check if no ACCESS_KEY is set, allow all requests
    if (!ACCESS_KEY) {
        return next();
    }

    // Allow preflight requests and static file requests without key
    if (req.method === 'OPTIONS') {
        return next();
    }

    // Check if this is a static asset request (GET only)
    if (req.method === 'GET') {
        const path = req.path.toLowerCase();
        // If the path ends with an allowed extension, skip the check
        const isStaticAsset = allowedExtensions.some(ext => path.endsWith(ext));
        if (isStaticAsset) {
            return next();
        }
    }

    // Otherwise, enforce key check
    const userKey = req.query.k;
    if (!userKey || userKey !== ACCESS_KEY) {
        return res.status(403).send('Access Denied.');
    }

    next();
};

module.exports = requireKey;