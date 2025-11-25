# GEMINI Code Understanding (v2)

This document provides an overview of the `v2` implementation of the `godtool` script, located in `godtool_with_cognito_release_v2.py`.

## Version
v2.03

## Overview

This v2 script builds upon the original GOD-Tool daemon, introducing significant refactoring to improve configuration management, data collection, and future model improvements. The core functionalities (ICCID and Person ID lookups) remain, but the underlying architecture is now more robust and configurable.

## Key v2 Features & Changes

### 1. Centralized Configuration (`v2/config.json`)
All hardcoded settings have been removed from the script and placed in `v2/config.json`. This file now controls:
*   **AWS Settings:** Profiles, DynamoDB table names, and S3 bucket names.
*   **Slack Credentials:** All bot/app tokens and channel IDs for both production and local testing environments.
*   **Application Settings:** An `active_slack_config` key to easily switch between environments, and the `heartbeat_max_search_days` value.

The script will exit on startup if this configuration file is missing or invalid.

### 2. New Battery Percentage Model (`v2/BatteryWeightings.csv`)
The battery percentage calculation has been updated to use a new model based on `v2/BatteryWeightings.csv`. This file provides a direct mapping from the battery percentage reported by the device in its heartbeat to the final percentage displayed in the Slack output. This allows for more accurate and easily adjustable battery percentage reporting.

### 3. Automated Data Logging (`v2/battery_voltage_log.csv`)
To facilitate future analysis and model improvements, the script continues to log every raw battery voltage reading from successful heartbeats to `v2/battery_voltage_log.csv`. Each entry includes a timestamp, the device's ICCID, and the raw millivolt value.

### 4. Enhanced Slack Output
The lookup results sent to Slack now include a "**Latest Reported Firmware**" field, which displays the firmware version reported in the device's most recent heartbeat.


## Usage

To run the script, you must first ensure the `v2/config.json` and `v2/BatteryWeightings.csv` files are correctly configured.

**Run the script:**
```bash
# Ensure you are in the project's root directory
python v2/godtool_with_cognito_release_v2.py
```

**Run in Debug Mode (for Local Testing):**
```bash
python v2/godtool_with_cognito_release_v2.py --debug
```
When the `--debug` flag is used, the script will automatically ignore the `active_slack_config` setting in `config.json` and force the use of the `local_testing` Slack credentials. This prevents accidental messages in production channels during testing.

## DynamoDB Query Script (`python_scripts/modem_fail_count/dynamo_query.py`)

### Overview

This script queries the `Refurb-Table` in DynamoDB to generate statistics about device refurbishment. It is primarily used to track the status of modem and GNSS firmware installations for devices processed at different user ports.

### Features

*   **Time-boxed Queries:** The script queries for entries created in the last two weeks.
*   **User Port Breakdown:** It provides a breakdown of entries by the `3_User-Port` field.
*   **Statistics for 'Investigations':** It calculates and displays specific statistics for entries where the user port starts with `cramlington1` (referred to as 'Investigations'). This includes:
    *   Total entries.
    *   Entries with modem issues.
    *   Entries that have passed all checks.
    *   Percentages for the above statistics.
*   **Overall Statistics:** It also provides the same statistics for all entries in the last two weeks, regardless of the user port.

### Usage

The script is executed by the backend API when the "Modem Failed Count" button is clicked on the "Tools" page of the web application. It can also be run directly from the command line for testing or manual report generation.

**Run the script:**
```bash
# Ensure you are in the project's root directory
python python_scripts/modem_fail_count/dynamo_query.py
```

## Deployment Progress (as of 24 November 2025)

Here's a summary of the progress made on deploying the site to `cramlington1@192.168.1.137`:

**Current Goal:** Install the local machine's `api_lookup` project (including `backend/` and `frontend/`) onto the new PC.

**Steps Completed:**
*   **Create a Remote Git Repository:** An empty remote repository (`git@github.com:slyons1106/api_tool.git`) was created on GitHub.
*   **Add Remote Origin and Push Code (Current PC):** The local repository was configured to point to the remote. An initial push failed due to a secret in Git history.
*   **Remove secret from Git history using git filter-repo:** The Slack Incoming Webhook URL was removed from the Git history of the local repository using `git filter-repo`, and the cleaned history was force-pushed to GitHub.
*   **Connect to the New PC via SSH:** Successfully established an SSH connection to `cramlington1@192.168.1.137`.
*   **Clone the Repository onto the New PC:** The `api_tool` repository was cloned onto the new PC.
*   **Correct Local Git Repository Content and Push to GitHub:** Identified that `backend/` and `frontend/` were missing from the GitHub repository due to an incorrect push from a subdirectory. The local `api_lookup` directory was re-initialized as its own Git repository, all its contents were added and committed, and then force-pushed to `slyons1106/api_tool.git` to include `backend/` and `frontend/`.
*   **Update cloned repository on New PC:** The new PC's cloned repository was updated using `git reset --hard origin/main` to reflect the corrected history, and the `backend/` and `frontend/` directories are now present.
*   **Install Python Dependencies for the identified application (New PC):** Python dependencies from `backend/requirements.txt` and `python_scripts/v2/requirements.txt` were installed in a virtual environment on the new PC.
*   **Install Node.js Dependencies and Build the Frontend (if applicable) (New PC):** Node.js dependencies were installed and the frontend was built on the new PC.
*   **Add `config.yaml` to backend and push to remote:** A `config.yaml` file was added to the `backend` directory and pushed to the remote repository. The changes have been pulled on the remote PC.

**Current ToDo List:**
1.  [completed] Create a Remote Git Repository.
2.  [completed] Add Remote Origin and Push Code (Current PC).
3.  [completed] Remove secret from Git history using git filter-repo.
4.  [completed] Connect to the New PC via SSH.
5.  [completed] Clone the Repository onto the New PC.
6.  [cancelled] Identify the specific "site" or application to install/run on the New PC.
7.  [completed] Correct Local Git Repository Content and Push to GitHub.
8.  [completed] Update cloned repository on New PC.
9.  [completed] Install Python Dependencies for the identified application (New PC).
10. [completed] Install Node.js Dependencies and Build the Frontend (if applicable) (New PC).
11. [completed] Add `config.yaml` to backend and push to remote.
12. [completed] Configure Project Files (New PC).
13. [in_progress] Run the identified application (New PC) - Focusing on Frontend.

**Next Step for Monday:**
Continue with **Step 13: Run the identified application (New PC) - Focusing on Frontend**. This involves executing the necessary commands to start the frontend application and make it visible.