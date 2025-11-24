# WebTools

A collection of web-based tools for various tasks.

## Project Overview

This project is a refactored version of the `api_lookup` application. The goal is to create a clean, modern, and maintainable web application with a focus on usability.

## Getting Started

### Prerequisites

- Python 3.8+
- Node.js 16+
- `pip` for Python package management
- `npm` for Node.js package management

### Installation

1.  **Clone the repository:**
    ```bash
    git clone git@github.com:slyons1106/webtools.git
    cd webtools
    ```

2.  **Backend Setup:**
    ```bash
    cd backend
    python -m venv .venv
    source .venv/bin/activate
    pip install -r requirements.txt
    # Create and populate backend/config.py from backend/config.py.example
    # Create and populate backend/accounts.json from backend/accounts.json.example
    cd ..
    ```

3.  **Frontend Setup:**
    ```bash
    cd frontend
    npm install
    # Create and populate frontend/.env from frontend/.env.example
    cd ..
    ```

### Running the Application

1.  **Start the backend server:**
    ```bash
    cd backend
    source .venv/bin/activate
    uvicorn main:app --reload
    ```

2.  **Start the frontend development server:**
    ```bash
    cd frontend
    npm start
    ```

## Secrets Management

All secrets, API keys, and other sensitive information are stored in files that are not committed to the repository. These files are:

- `backend/config.py`
- `backend/accounts.json`
- `frontend/.env`

Example files (`backend/config.py.example` and `frontend/.env.example`) are provided in the repository. You must create the actual secret files from these examples and populate them with your credentials.
