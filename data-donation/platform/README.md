# Safari Intelligent Tracking Prevention (ITP) Data Donation
A simple web application to collect and preprocess user data donations of Safari ITP's observation database.

## Usage
1. Clone this repository to your local machine.
2. Navigate to the project directory:
```bash
cd platform
```
3. Source environment variables as shown in the `example.env` file:
```bash
source .env
```
4. Build and start the Docker containers:
```bash
docker compose up --build -d
```

## Run Locally without Docker
1. Install the required dependencies:
```bash
npm install
```
2. Source environment variables as shown in the `example.env` file:
```bash
source .env
```
3. Start the application:
```bash
npm start
```

## Environment Variables
- `PORT`: Port number for the web application (default: `3000`).
- `STORAGE_DIR_NAME`: Directory name for storing donations (default: `donations`).
- `MAX_FOLDER_SIZE_MB`: Maximum allowed size for the donation folder in MB (default: `500`).
- `MAX_FILE_SIZE_MB`: Maximum allowed size for each data donation in MB (default: `2`).
- `ENSURE_UNIQUE_DONATIONS`: Whether to ensure unique donations by checking for duplicates (default: `true`).
- `ACCESS_KEY`: Secure access key for API authentication. Leave empty to disable authentication.
