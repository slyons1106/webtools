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

## Environment Variable Strategy for Frontend

The Create React App (CRA) frontend relies on build-time environment variables for configuring API endpoints. Due to aggressive caching and potential inconsistencies with `.env` file loading in certain environments, the following strategy is recommended:

1.  **Source Code Usage**: Always reference API endpoints and other environment-dependent values in the source code using `process.env.REACT_APP_YOUR_VARIABLE_NAME`. Ensure there are **no hardcoded values** or **fallback `|| 'http://localhost:8000'` constructs** for critical API URLs.
2.  **`frontend/.env` File**: The `frontend/.env` file (if present) should primarily be used for development server (`npm start`) specific variables that are non-critical or for variables whose values don't need to be strictly controlled at build time. For build-time critical variables like `REACT_APP_API_BASE_URL`, it's best to avoid setting them in this file to prevent conflicts.
3.  **Build-Time Configuration (Recommended)**: For `npm run build`, explicitly pass critical environment variables directly to the build command. This ensures the correct values are embedded into the compiled JavaScript bundle, overriding any other potential sources.

    *   **For Local Development / Testing (Backend on `127.0.0.1:8000`):**
        ```bash
        REACT_APP_API_BASE_URL=http://127.0.0.1:8000 npm run build --prefix frontend
        ```
    *   **For Remote Deployment / Staging (Backend on `192.168.1.109:8000` or similar):**
        ```bash
        REACT_APP_API_BASE_URL=http://192.168.1.109:8000 npm run build --prefix frontend
        ```
        (Replace `192.168.1.109:8000` with the actual remote backend URL.)

This strategy ensures predictable and reliable environment variable injection into the frontend build, bypassing the persistent caching issues observed.


## Debugging Notes

- **`ImportError: attempted relative import with no known parent package`**: This error occurs when running a Python script with relative imports as a top-level script. The solution is to run `uvicorn` from the project's root directory and specify the application path as `backend.main:app`, which makes the package structure explicit.
- **`SyntaxError` in `config.py`**: This indicates a syntax error in the `config.py` file. Carefully check the file for any mistakes, such as extra characters or misplaced braces, by comparing it against `config.py.example`.
- **`NameError: name 'BATTERY_WEIGHTINGS_DATA' is not defined`**: This was a bug introduced during refactoring where a global variable was not initialized. The fix was to add `BATTERY_WEIGHTINGS_DATA = None` before its first use in `backend/main.py`.
- **Persistent `react-scripts` Build Caching with API Endpoints**: When deploying the frontend, especially for local testing or remote access, `react-scripts` (v5.0.1) exhibits aggressive caching behavior. Attempts to configure the backend API endpoint via `frontend/.env` (`REACT_APP_API_BASE_URL`) or even direct code modifications in `frontend/src/pages/S3ViewerPage.tsx` were not consistently reflected in the production build (`npm run build`). This resulted in the frontend persistently trying to connect to `http://localhost:8000` from remote machines, or `http://192.168.1.109:8000` when running locally (if previously patched for remote).
  *   **Workaround:** The only consistent solution found was direct patching of the compiled JavaScript bundle (`frontend/build/static/js/main.<hash>.js`) using `sed`.
  *   For **remote access** (e.g., from `192.168.1.109`), `sed -i '' 's/http:\/\/localhost:8000/http:\/\/192.168.1.109:8000/g' frontend/build/static/js/main.<hash>.js` and `sed -i '' 's/http:\/\/localhost/http:\/\/192.168.1.109:8000/g' frontend/build/static/js/main.<hash>.js` were used.
  *   For **local development** (when backend is on `127.0.0.1:8000`), `sed -i '' 's/http:\/\/192.168.1.109:8000/http:\/\/127.0.0.1:8000/g' frontend/build/static/js/main.<hash>.js` was used.
  *   **Note:** The `<hash>` in the filename changes with each build, requiring an `ls` command to get the current filename before applying `sed`. This is an extreme measure and the root cause of the `react-scripts` caching requires further investigation for a sustainable solution.