const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const dotenv = require('dotenv');

dotenv.config();

// Configuration
const DIR_NAME = process.env.STORAGE_DIR_NAME || 'donations';
const STORAGE_DIR = path.join(__dirname, `../${DIR_NAME}`);
const MAX_FOLDER_SIZE_BYTES = parseInt(process.env.MAX_FOLDER_SIZE_MB) * 1024 * 1024 || 500 * 1024 * 1024; // 500MB
const MAX_FILE_SIZE_BYTES = parseInt(process.env.MAX_FILE_SIZE_MB) * 1024 * 1024 || 2097152; // 2MB

// Ensure directory exists on startup
if (!fs.existsSync(STORAGE_DIR)) {
    fs.mkdirSync(STORAGE_DIR);
}

// Calculate total folder size
function getFolderSize() {
    const files = fs.readdirSync(STORAGE_DIR);
    let totalSize = 0;
    for (const file of files) {
        const stats = fs.statSync(path.join(STORAGE_DIR, file));
        totalSize += stats.size;
    }
    return totalSize;
}

module.exports = {
    saveDonation: (dataPayload) => {
        return new Promise((resolve, reject) => {
            try {
                // Prepare content
                const fileContent = JSON.stringify(dataPayload, null, 2);
                const maxContentFileSize = Buffer.byteLength(fileContent);
                const maxFolderSizeBytes = MAX_FOLDER_SIZE_BYTES;

                // Check file size
                if (maxContentFileSize > MAX_FILE_SIZE_BYTES) {
                    return reject(new Error("FILE_TOO_LARGE"));
                }

                // Check disk quota
                if ((getFolderSize() + maxContentFileSize) > maxFolderSizeBytes) {
                    return reject(new Error("STORAGE_FULL"));
                }

                // Generate safe filename
                const safeId = crypto.randomUUID();
                const safeFilename = `${safeId}.json`;
                const safePath = path.join(STORAGE_DIR, safeFilename);

                // Write File (Read-only mode 0o444)
                fs.writeFile(safePath, fileContent, { mode: 0o444 }, (err) => {
                    if (err) return reject(err);
                    resolve(safeId);
                });

            } catch (err) {
                reject(err);
            }
        });
    }
};