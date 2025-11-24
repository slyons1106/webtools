# Thingco Internal Web Tools

## Overview

This project is a comprehensive, web-based toolkit designed to provide internal users with easy access to key information from various AWS services and device data sources. It replaces a collection of separate scripts with a unified, user-friendly interface.

The application consists of a Python FastAPI backend that serves a REST API and a React (TypeScript) frontend that provides the user interface.

## Version

**v1.0.0**

## Features

The toolkit includes the following pages/features:

-   **Lookup**: A powerful tool for retrieving detailed information about a device (by ICCID).
    -   Displays general device information, registration status, and last known heartbeat data.
    -   Fetches and displays the device's **IoT Thing Shadow**, showing its last reported state from AWS IoT Core.
    -   Allows authorized users to **edit the device's 'desired' shadow state** for specific fields (`Debug`, `Trip-Timeout`, `After-Trip-Reports`).
    -   Lists the last 6 IoT Jobs associated with the device.
-   **Person Details**: A tool for looking up user information by Person ID (UUID).
    -   Displays the user's associated account and their full details from the relevant Cognito User Pool.
    -   Dynamically finds the correct "Customer" user pool for the account.
    -   Allows authorized users to **enable or disable the Cognito user** via a toggle switch.
-   **API Log Search**: A utility for searching CloudWatch logs across different AWS accounts and API handlers to find specific log entries.
-   **S3 Label Viewer**: A simple browser for viewing PNG labels stored in the `pat-labels` S3 bucket.
-   **CSV Splitter**: A utility to split a large CSV file into smaller, zipped chunks based on a specified number of rows.

## Prerequisites

Before you begin, ensure you have the following installed:
-   **Python 3.8+**
-   **Node.js v16+** and **npm**
-   **AWS CLI**: Make sure it's configured with your AWS credentials. The tool reads profiles from `~/.aws/config` and `~/.aws/credentials`. The backend logic depends on these profiles being named correctly to match the account names in the database.

## Backend (`/backend`)

The backend is a Python application built with the **FastAPI** framework. It provides all the API endpoints that the frontend consumes.

### Key Configuration

-   `backend/config.json`: Contains AWS profile names, DynamoDB table names, and S3 bucket information. This file is critical and must be configured correctly.
-   `backend/accounts.json`: Maps AWS Account IDs to account names and other metadata. This is used to find the correct AWS profile for a given device or person.
-   `backend/BatteryWeightings.csv`: Contains the mapping for calculating the display battery percentage from raw values.

### Backend Setup

```bash
# Navigate to the backend directory
cd backend

# Create and activate a Python virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install the required Python packages
pip install -r requirements.txt
```

### Running the Backend

```bash
# From the backend directory with the virtual environment activated
uvicorn main:app --host 0.0.0.0 --port 8000
```
The server will be running on `http://0.0.0.0:8000`.

## Frontend (`/frontend`)

The frontend is a single-page application built with **React** and **TypeScript**, using the `react-bootstrap` library for UI components.

### Frontend Setup

```bash
# Navigate to the frontend directory
cd frontend

# Install the required npm packages
npm install
```

### Running the Frontend

To run the application for development, you need to have both the backend server and the frontend server running in **two separate terminals.**

**Terminal 1: Start the Backend** (as described above)

**Terminal 2: Start the Frontend**

```bash
# Navigate to the frontend directory
cd frontend

# Start the React development server
npm start
```
This will automatically open a new tab in your web browser with the application at `http://localhost:3000`.