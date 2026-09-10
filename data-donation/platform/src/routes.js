const express = require('express');
const router = express.Router();
const storage = require('./storage');
const crypto = require('crypto');

// In-memory duplicate check (resets on restart)
const seenHashes = new Set();

router.get('/', (req, res) => {
    // serve index.html
    res.sendFile('index.html', { root: './public' });
});

router.get('/thankyou', async (req, res) => {
    res.sendFile('thankyou.html', { root: './public' });
});

router.get('/privacy', (req, res) => {
    res.sendFile('privacy.html', { root: './public' });
});

router.post('/donate', async (req, res) => {
    const payload = req.body;

    // Basic format validation
    if (!payload) {
        console.log("Received invalid payload format");
        return res.status(400).json({ error: "Invalid payload format" });
    }

    // Check if is valid json
    try {
        JSON.stringify(payload);
    } catch (err) {
        console.log("Received invalid JSON payload");
        return res.status(400).json({ error: "Invalid payload format" });
    }

    // Duplicate Detection (Content Hash)
    const contentHash = crypto.createHash('sha256')
        .update(JSON.stringify(payload.domains) + JSON.stringify(payload.topFrameUniqueRedirects))
        .digest('hex');

    const ensureUniqueDonations = process.env.ENSURE_UNIQUE_DONATIONS === 'true';
    if (ensureUniqueDonations && seenHashes.has(contentHash)) {
        // Silent success
        console.log("Duplicate donation detected, ignoring and providing fake ID.");
        const fakeID = crypto.randomUUID();
        return res.json({ message: "Donation received", data: {id: fakeID } });
    }

    try {
        // Save to Disk
        const fileId = await storage.saveDonation(payload);
        
        // Mark as seen only after successful save
        seenHashes.add(contentHash);
        
        console.log(`Saved donation: ${fileId}`);
        return res.json({ message: "Donation received", data: { id: fileId } });

    } catch (err) {
        if (err.message === "STORAGE_FULL") {
            console.error("Storage Limit Reached");
            return res.json({ message: "Donation received" });
        }
        console.error("Write Error:", err);
        res.status(500).json({ error: "Internal Server Error" });
    }
});

module.exports = router;