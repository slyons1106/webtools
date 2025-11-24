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
    python3 -m venv .venv
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
    *   From the project root directory (`webtools`), run:
        ```bash
        python3 -m uvicorn backend.main:app --reload
        ```
    *   The backend will be available at `http://127.0.0.1:8000`.

2.  **Start the frontend development server:**
    *   In a new terminal, navigate to the `frontend` directory and run:
        ```bash
        npm start
        ```
    *   The frontend will be available at `http://localhost:3000` (or another port if 3000 is busy).

## Secrets Management

All secrets, API keys, and other sensitive information are stored in files that are not committed to the repository. These files are:

- `backend/config.py`
- `backend/accounts.json`
- `frontend/.env`

Example files (`backend/config.py.example` and `frontend/.env.example`) are provided in the repository. You must create the actual secret files from these examples and populate them with your credentials.

## Debugging Notes

- **`ImportError: attempted relative import with no known parent package`**: This error occurs when running a Python script with relative imports as a top-level script. The solution is to run `uvicorn` from the project's root directory and specify the application path as `backend.main:app`, which makes the package structure explicit.
- **`SyntaxError` in `config.py`**: This indicates a syntax error in the `config.py` file. Carefully check the file for any mistakes, such as extra characters or misplaced braces, by comparing it against `config.py.example`.
- **`NameError: name 'BATTERY_WEIGHTINGS_DATA' is not defined`**: This was a bug introduced during refactoring where a global variable was not initialized. The fix was to add `BATTERY_WEIGHTINGS_DATA = None` before its first use in `backend/main.py`.