const express = require('express');
const cors = require('cors');
const dotenv = require('dotenv');
const apiRoutes = require('./src/routes');
const requireKey = require('./src/auth');

dotenv.config();

const app = express();
const PORT = process.env.PORT || 3000;

// Middleware
app.use(cors());
app.use(express.json({ limit: '2mb' })); // Limit JSON body size to 2MB
app.use(requireKey);
app.use(express.static('public')); // Serve static files

// Use routes
app.use('/', apiRoutes);

// Start server
app.listen(PORT, () => {
    console.log(`Server running on port ${PORT}`);
    console.log(`Storage Directory: ${process.env.STORAGE_DIR_NAME || 'donations'}`);
    console.log(`Ensuring unique donations: ${process.env.ENSURE_UNIQUE_DONATIONS || false}`);
    
});
