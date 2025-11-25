# Fixed version of GOD-Tool Daemon Listener with multi-channel support and user mentions
#!/usr/bin/env python3
"""
GOD-Tool Daemon Listener by Sean Lyons
Command-line version for Slack integration, ICCID lookups, and Person ID app access management
"""
__version__ = "2.04" # Updated version number after GPS output logic changes.

import boto3
from datetime import datetime, timedelta
import threading
import time
import json
import msgpack
import sys
import signal
import re
import csv
import os
import math
import yaml

# --- Configuration Loading ---
CONFIG = None
# Determine the script's directory to correctly load config files
SCRIPT_DIR = os.path.dirname(os.path.abspath(sys.argv[0]))
V2_CONFIG_FILE_PATH = os.path.join(SCRIPT_DIR, "config.json")
BACKEND_ROOT_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, '..', '..', 'backend')) # Path to /api_tool/backend
SECRETS_CONFIG_FILE_PATH = os.path.join(BACKEND_ROOT_DIR, "config.yaml")


try:
    with open(V2_CONFIG_FILE_PATH, "r") as f:
        CONFIG = json.load(f)
except Exception as e:
    # Use print because print_info might not be defined yet
    print(f"FATAL: Could not load default config {V2_CONFIG_FILE_PATH}: {e}")
    sys.exit(1)

# Attempt to load secrets from config.yaml and override
try:
    if os.path.exists(SECRETS_CONFIG_FILE_PATH):
        with open(SECRETS_CONFIG_FILE_PATH, "r") as f:
            secrets_config = yaml.safe_load(f)
            # Merge secrets_config into CONFIG, prioritizing secrets
            # This is a deep merge for dicts, simple overwrite for values
            for key, value in secrets_config.items():
                if key in CONFIG and isinstance(CONFIG[key], dict) and isinstance(value, dict):
                    CONFIG[key].update(value) # Merge dictionaries
                else:
                    CONFIG[key] = value # Overwrite other types
        print(f"INFO: Successfully loaded secrets from {SECRETS_CONFIG_FILE_PATH}")
    else:
        print(f"INFO: No secrets file found at {SECRETS_CONFIG_FILE_PATH}. Using defaults from {V2_CONFIG_FILE_PATH}.")
except Exception as e:
    print(f"WARNING: Could not load secrets from {SECRETS_CONFIG_FILE_PATH}: {e}. Using defaults.")

# Check for debug flag
DEBUG_MODE = '--debug' in sys.argv

def debug_print(message):
    """Print debug messages only if debug mode is enabled"""
    if DEBUG_MODE:
        print(f"[DEBUG] {message}")

def print_info(message):
    """Print info messages with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

# Get available AWS profiles on this machine
AVAILABLE_PROFILES = boto3.Session().available_profiles

# AWS Sessions
dev_session = boto3.Session(profile_name=CONFIG['aws']['profiles']['dev'])
gateway_session = boto3.Session(profile_name=CONFIG['aws']['profiles']['gateway'])

dev_dynamodb = dev_session.resource("dynamodb")
gateway_dynamodb = gateway_session.resource("dynamodb")

# DynamoDB Tables
refurb_table = dev_dynamodb.Table(CONFIG['aws']['dynamodb_tables']['refurb'])
device_reg_table = gateway_dynamodb.Table(CONFIG['aws']['dynamodb_tables']['device_registration'])
pat_labels_table = gateway_dynamodb.Table(CONFIG['aws']['dynamodb_tables']['pat_labels'])

# S3 Setup
s3_client = gateway_session.client("s3")
dev_s3_client = dev_session.client("s3")

# Slack Integration Variables
slack_listener_thread = None
slack_listener_enabled = False
slack_stop_event = threading.Event()

# Global cache for the battery weightings
BATTERY_WEIGHTINGS_DATA = None

def load_battery_weightings():
    """Load the battery weightings from BatteryWeightings.csv (relative to script)"""
    global BATTERY_WEIGHTINGS_DATA
    BATTERY_WEIGHTINGS_FILE_PATH = os.path.join(SCRIPT_DIR, "BatteryWeightings.csv")
    try:
        weightings = []
        with open(BATTERY_WEIGHTINGS_FILE_PATH, "r") as f:
            reader = csv.reader(f)
            next(reader) # Skip header row
            for row in reader:
                if len(row) == 2:
                    try:
                        reported_percentage = int(row[0])
                        desired_percentage = int(row[1])
                        weightings.append((reported_percentage, desired_percentage))
                    except ValueError:
                        print_info(f"WARNING: Skipping malformed row in {BATTERY_WEIGHTINGS_FILE_PATH}: {row}")
        
        if weightings:
            # Sort by reported percentage just in case the file is not ordered
            weightings.sort(key=lambda x: x[0])
            BATTERY_WEIGHTINGS_DATA = weightings
            print_info(f"Successfully loaded battery weightings from {BATTERY_WEIGHTINGS_FILE_PATH}")
        else:
            print_info(f"WARNING: No valid battery weightings found in {BATTERY_WEIGHTINGS_FILE_PATH}. Using fallback.")
            BATTERY_WEIGHTINGS_DATA = [(0,0), (100,100)] # Fallback to 1:1 mapping
    except FileNotFoundError:
        print_info(f"ERROR: {BATTERY_WEIGHTINGS_FILE_PATH} not found. Using fallback battery weightings.")
        BATTERY_WEIGHTINGS_DATA = [(0,0), (100,100)] # Fallback to 1:1 mapping
    except Exception as e:
        print_info(f"ERROR: Could not load {BATTERY_WEIGHTINGS_FILE_PATH}: {e}. Using fallback battery weightings.")
        BATTERY_WEIGHTINGS_DATA = [(0,0), (100,100)] # Fallback to 1:1 mapping

def portal_battery(reported_percentage):
    """
    Calculate portal battery percentage from the reported percentage using battery weightings.
    """
    if BATTERY_WEIGHTINGS_DATA is None:
        load_battery_weightings()

    try:
        if reported_percentage is None:
            return "N/A"
        reported_percentage = int(reported_percentage)
        
        weightings = BATTERY_WEIGHTINGS_DATA

        # Handle edge cases
        if reported_percentage <= weightings[0][0]:
            return weightings[0][1]
        if reported_percentage >= weightings[-1][0]:
            return weightings[-1][1]

        # Find the two points to interpolate between
        for i in range(len(weightings) - 1):
            rp_lower, dp_lower = weightings[i] # reported_percentage_lower, desired_percentage_lower
            rp_upper, dp_upper = weightings[i+1] # reported_percentage_upper, desired_percentage_upper

            if rp_lower <= reported_percentage <= rp_upper:
                rp_range = rp_upper - rp_lower
                dp_range = dp_upper - dp_lower
                
                if rp_range == 0:
                    return dp_lower

                rp_delta = reported_percentage - rp_lower
                final_percentage = dp_lower + (rp_delta / rp_range) * dp_range
                
                return round(final_percentage)
        
        # Fallback for safety, though it should not be reached with correct logic.
        return weightings[-1][1]

    except (ValueError, TypeError) as e:
        debug_print(f"Error in portal_battery: {e} with reported_percentage {reported_percentage}")
        return "N/A"

def extract_year_of_manufacture(iccid):
    """Extract year of manufacture from ICCID"""
    try:
        if len(iccid) >= 12:
            year_digits = iccid[10:12]
            return f"20{year_digits}"
        return "N/A"
    except Exception:
        return "N/A"

def slack_listener_worker():
    """Main Slack listener worker thread"""
    try:
        from slack_sdk import WebClient
        from slack_sdk.socket_mode import SocketModeClient
        from slack_sdk.socket_mode.request import SocketModeRequest
        from slack_sdk.socket_mode.response import SocketModeResponse

        # --- Slack Configuration ---
        # Determine which slack configuration to use
        if DEBUG_MODE:
            active_config_name = "local_testing"
            print_info("DEBUG MODE: Using 'local_testing' Slack configuration.")
        else:
            active_config_name = CONFIG['settings']['active_slack_config']
        
        active_config = CONFIG['slack'].get(active_config_name)
        if not active_config:
            print_info(f"FATAL: Active Slack configuration '{active_config_name}' not found in config.json.")
            sys.exit(1)

        SLACK_BOT_TOKEN = active_config.get('bot_token')
        SLACK_APP_TOKEN = active_config.get('app_token')
        CHANNEL_IDS = active_config.get('channels', [])

        if not all([SLACK_BOT_TOKEN, SLACK_APP_TOKEN, CHANNEL_IDS]):
            print_info(f"FATAL: Missing 'bot_token', 'app_token', or 'channels' in '{active_config_name}' config.")
            sys.exit(1)

        client = WebClient(token=SLACK_BOT_TOKEN)
        socket_client = SocketModeClient(app_token=SLACK_APP_TOKEN, web_client=client)

        # Send startup message in debug mode
        if DEBUG_MODE:
            try:
                print_info(f"Sending startup message to channel {CHANNEL_IDS[0]}")
                client.chat_postMessage(channel=CHANNEL_IDS[0], text="-- God Tool Started (Debug Mode) --")
            except Exception as e:
                print_info(f"ERROR: Could not send startup message to Slack: {e}")

        def handle_message(client: SocketModeClient, req: SocketModeRequest):
            debug_print(f"SLACK: Received request type={req.type}")
            if req.type == "events_api":
                try:
                    response = SocketModeResponse(envelope_id=req.envelope_id)
                    client.send_socket_mode_response(response)
                    debug_print("SLACK: Acked events_api request")
                except Exception as e:
                    debug_print(f"SLACK: Failed to ack events_api: {e}")

                event = req.payload.get("event", {}) or {}
                debug_print(
                    f"SLACK: Event summary -> type={event.get('type')} "
                    f" subtype={event.get('subtype')} channel={event.get('channel')} "
                    f" user={event.get('user')} text={event.get('text')!r}"
                )

                # Check if message is in one of our target channels and is a plain message
                if (event.get("type") == "message" and
                    not event.get("subtype") and
                    event.get("channel") in CHANNEL_IDS and
                    not event.get("bot_id")):

                    text = event.get("text", "") or ""
                    user_id = event.get("user")
                    channel_id = event.get("channel")
                    
                    # Check if this is Channel B (wrong channel)
                    is_wrong_channel = (channel_id == CHANNEL_IDS[1]) if len(CHANNEL_IDS) > 1 else False

                    # Check for ICCID pattern [[19-20 digits]]
                    iccid_match = re.search(r"\[\[([0-9]{19,20})\]\]", text)
                    # Check for Person ID pattern [[UUID format]]
                    person_match = re.search(r"\[\[([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})\]\]", text, re.IGNORECASE)
                    
                    if iccid_match:
                        iccid = iccid_match.group(1)
                        debug_print(f"SLACK: Found ICCID trigger: {iccid} from user {user_id} in channel {channel_id}")
                        
                        # Acknowledge with a reaction
                        try:
                            ts = event.get("ts")
                            client.web_client.reactions_add(channel=channel_id, name="eyes", timestamp=ts)
                        except Exception as e:
                            debug_print(f"SLACK: Error adding reaction: {e}")

                        result = perform_slack_lookup(iccid, user_id)
                        
                        # Add warning if wrong channel
                        if is_wrong_channel:
                            result = ":Alert: **Enabling MAT Code. This is the wrong channel!** ⚠️\n\n" + result + "\n\n:Alert: **Enabling MAT Code. This is the wrong channel!** ⚠️"
                        
                        try:
                            # Reply in the same channel where the trigger was sent
                            client.web_client.chat_postMessage(
                                channel=channel_id,
                                text=result,
                                unfurl_links=False,
                                unfurl_media=False
                            )
                            debug_print("SLACK: Replied with lookup result")
                        except Exception as e:
                            debug_print(f"SLACK: Error posting reply: {e}")
                    elif person_match:
                        person_id = person_match.group(1)
                        debug_print(f"SLACK: Found Person ID trigger: {person_id} from user {user_id} in channel {channel_id}")

                        # Acknowledge with a reaction
                        try:
                            ts = event.get("ts")
                            client.web_client.reactions_add(channel=channel_id, name="eyes", timestamp=ts)
                        except Exception as e:
                            debug_print(f"SLACK: Error adding reaction: {e}")
                        
                        result = perform_person_lookup(person_id, user_id)
                        
                        # Add warning if wrong channel
                        if is_wrong_channel:
                            result = ":Alert: **Enabling MAT Code. This is the wrong channel!** ⚠️\n\n" + result + "\n\n:Alert: **Enabling MAT Code. This is the wrong channel!** ⚠️"
                        
                        try:
                            # Reply in the same channel where the trigger was sent
                            client.web_client.chat_postMessage(
                                channel=channel_id,
                                text=result,
                                unfurl_links=False,
                                unfurl_media=False
                            )
                            debug_print("SLACK: Replied with person lookup result")
                        except Exception as e:
                            debug_print(f"SLACK: Error posting reply: {e}")
                    else:
                        debug_print("SLACK: Event ignored (no ICCID or Person ID pattern found)")

        socket_client.socket_mode_request_listeners.append(handle_message)
        debug_print(f"SLACK: Starting listener on channels {CHANNEL_IDS}")
        socket_client.connect()

        while not slack_stop_event.is_set():
            time.sleep(1)

        # Send shutdown message in debug mode
        if DEBUG_MODE:
            try:
                print_info(f"Sending shutdown message to channel {CHANNEL_IDS[0]}")
                client.chat_postMessage(channel=CHANNEL_IDS[0], text="-- God Tool Stopping now (Debug Mode) --")
            except Exception as e:
                print_info(f"ERROR: Could not send shutdown message to Slack: {e}")

        socket_client.disconnect()
        debug_print("SLACK: Listener stopped")

    except ImportError:
        print_info("ERROR: slack_sdk not installed. Install with: pip install slack_sdk")
    except Exception as e:
        print_info(f"ERROR: Slack listener error: {e}")


def perform_person_lookup(person_id, user_id=None):
    """Perform Person ID lookup and enable app access"""
    try:
        # Add user mention if user_id is provided
        if user_id:
            result_lines = [f"<@{user_id}> 👤 **Person ID Lookup: {person_id}"]
        else:
            result_lines = [f"👤 **Person ID Lookup: {person_id}"]

        # Query pat-labels table to get account ID
        try:
            debug_print(f"PERSON: Querying pat-labels for PersonID: {person_id}")
            response = pat_labels_table.query(
                IndexName="PersonID-index",  # You may need to adjust this if the GSI name is different
                KeyConditionExpression=boto3.dynamodb.conditions.Key("PersonID").eq(person_id)
            )
            
            items = response.get("Items", [])
            
            if not items:
                # Try direct get_item if it's the primary key
                debug_print(f"PERSON: Trying direct get_item with ID={person_id}")
                response = pat_labels_table.get_item(
                    Key={"ID": person_id, "Metadata": "FULFILMENT#REQUEST"}
                )
                item = response.get("Item")
                if item:
                    items = [item]
            
            if not items:
                result_lines.append("❌ Person ID not found in pat-labels table")
                return "\n".join(result_lines)
            
            # Get the first matching item (should only be one)
            item = items[0]
            account_id = item.get("AccountID")
            
            if not account_id:
                result_lines.append("❌ No AccountID found for this Person ID")
                return "\n".join(result_lines)
            
            account_name = get_account_name(account_id)
            result_lines.append(f"🏢 Account: {account_name} ({account_id})")
            
            # Get AWS profile for this account
            matched_profile = get_profile_for_account(account_id, account_name)
            
            if not matched_profile:
                result_lines.append(f"❌ No AWS profile found for account {account_name}")
                result_lines.append(f"💡 Available profiles: {', '.join(AVAILABLE_PROFILES)}")
                return "\n".join(result_lines)
            
            result_lines.append(f"🔑 Using AWS profile: {matched_profile}")
            
            # Get Cognito user pool ID from accounts.json
            user_pool_id = get_user_pool_id(account_id)
            
            if not user_pool_id:
                result_lines.append(f"❌ No Cognito User Pool ID configured for {account_name}")
                result_lines.append(f"💡 Add 'user_pool_id' to accounts.json for this account")
                return "\n".join(result_lines)
            
            # Create session for the daughter account
            session = boto3.Session(profile_name=matched_profile)
            cognito_client = session.client("cognito-idp")
            
            # Enable the user
            try:
                debug_print(f"PERSON: Enabling user {person_id} in pool {user_pool_id}")
                cognito_client.admin_enable_user(
                    UserPoolId=user_pool_id,
                    Username=person_id
                )
                result_lines.append(f"✅ **App access ENABLED** for {person_id}")
                result_lines.append(f"🎉 User can now log in to the app")
            except cognito_client.exceptions.UserNotFoundException:
                result_lines.append(f"❌ User {person_id} not found in Cognito User Pool")
            except Exception as e:
                result_lines.append(f"❌ Error enabling user: {str(e)}")
                debug_print(f"PERSON: Cognito error: {e}")
            
        except Exception as e:
            result_lines.append(f"❌ Error querying pat-labels: {str(e)}")
            debug_print(f"PERSON: Error: {e}")
            if DEBUG_MODE:
                import traceback
                traceback.print_exc()

        return "\n".join(result_lines)

    except Exception as e:
        return f"❌ Error performing person lookup: {str(e)}"





LOG_FILE_PATH = os.path.join(SCRIPT_DIR, "battery_voltage_log.csv")

def log_battery_data(iccid, voltage):
    """Appends a new voltage reading to the battery data log."""
    try:
        # Ensure voltage is a number
        if voltage is None or not str(voltage).isdigit():
            return

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        file_exists = os.path.isfile(LOG_FILE_PATH)

        with open(LOG_FILE_PATH, 'a', newline='') as f:
            writer = csv.writer(f)
            # Write header if file is new
            if not file_exists:
                writer.writerow(["timestamp", "iccid", "voltage_mv"])
            
            writer.writerow([timestamp, iccid, voltage])

        # In debug mode, trigger a rebuild after every new data point
        if DEBUG_MODE:
            pass

    except Exception as e:
        print_info(f"ERROR: Could not write to battery log file: {e}")


def perform_slack_lookup(iccid, user_id=None):
    """Perform ICCID lookup and return formatted result for Slack"""
    try:
        # Extract year of manufacture
        year_of_manufacture = extract_year_of_manufacture(iccid)
        found_anything = False # Flag to track if we find any data

        # Add user mention if user_id is provided
        if user_id:
            result_lines = [
                f"<@{user_id}> 🔍 **Lookup Results for ICCID: {iccid}**",
                f"🏭 Year of Manufacture: {year_of_manufacture}"
            ]
        else:
            result_lines = [
                f"🔍 **Lookup Results for ICCID: {iccid}**",
                f"🏭 Year of Manufacture: {year_of_manufacture}"
            ]

        # Check refurb table
        try:
            response = refurb_table.query(
                KeyConditionExpression=boto3.dynamodb.conditions.Key("iccid").eq(iccid)
            )
            items = response.get("Items", [])
            if items:
                found_anything = True
                result_lines.append(f"📊 Found {len(items)} records in Refurb-Table")
            else:
                result_lines.append("📊 No records found in Refurb-Table")
        except Exception as e:
            result_lines.append(f"❌ Error checking Refurb-Table: {str(e)}")

        # Check device registration
        account_id = None
        account_name = None
        try:
            response = device_reg_table.get_item(
                Key={"ID": iccid, "Metadata": "ACCOUNTALLOCATION"}
            )
            item = response.get("Item")
            if item:
                found_anything = True
                account_id = item.get("AccountID")
                account_name = get_account_name(account_id) if account_id else "Unknown"
                created_at = item.get("CreatedAt")
                uk_time = format_timestamp(created_at) if created_at else "N/A"
                result_lines.append(f"🏢 Device registered to: {account_name}")
                result_lines.append(f"📅 Registration time: {uk_time}")
            else:
                result_lines.append("🏢 No registration found")
        except Exception as e:
            result_lines.append(f"❌ Error checking registration: {str(e)}")

        # Device type detection
        try:
            if iccid.startswith("894303017220"):
                result_lines.append("📱 Device Type: ST Device")
            elif iccid > "8943030172210000":
                result_lines.append("📱 Device Type: GD Device")
        except Exception:
            pass

        # Battery replacement check
        try:
            if check_battery_replacement(iccid):
                found_anything = True
                result_lines.append("🔋 ⚠️ Battery has been replaced")
        except Exception:
            pass

        # Heartbeat lookup if we have account info
        if account_id and account_name:
            matched_profile = get_profile_for_account(account_id, account_name)
            if matched_profile:
                try:
                    session = boto3.Session(profile_name=matched_profile)
                    s3_client_local = session.client("s3")

                    heartbeat_info = get_latest_heartbeat_info(iccid, account_id, s3_client_local, max_search=CONFIG['settings']['heartbeat_max_search_days'])
                    if heartbeat_info:
                        found_anything = True
                        # Use battery_percentage for the portal display calculation
                        reported_batt = heartbeat_info.get("battery_percentage")
                        portal_batt = portal_battery(reported_batt)
                        
                        # Log the raw voltage for future analysis, not the reported percentage
                        raw_voltage = heartbeat_info.get("battery_voltage")
                        log_battery_data(iccid, raw_voltage)
                        result_lines.append(f"💓 Last Heartbeat: {heartbeat_info['last_seen']}")
                        fw_version = heartbeat_info.get('firmware_version', 'N/A')
                        result_lines.append(f"🛰️ Latest reported Firmware: {fw_version}")
                        result_lines.append(f"🔋 Battery: {portal_batt}%")
                        # Handle GPS status and location
                        lat = heartbeat_info.get('lat')
                        lng = heartbeat_info.get('lng')

                        if lat == 'nan' or lng == 'nan':
                            result_lines.append(f"📍 GPS: Faulty/No Fix")
                            result_lines.append(f"🌐 Location: No valid GPS data")
                        elif heartbeat_info.get('gps_connected') and lat is not None and lng is not None and lat != 'N/A' and lng != 'N/A':
                            maps_url = f"https://maps.google.com/?q={lat},{lng}"
                            result_lines.append(f"📍 GPS: Connected")
                            result_lines.append(f"🌐 Location: {lat}, {lng} <{maps_url}|View Map>")
                        else:
                            result_lines.append(f"📍 GPS: Disconnected")
                            result_lines.append(f"🌐 Location: N/A")
                    else:
                        result_lines.append("💓 No heartbeat in last 31 days")

                    # Registration info
                    registration_info = get_latest_registration_info(iccid, account_id, s3_client_local)
                    if registration_info:
                        found_anything = True
                        reg_raw = registration_info.get('raw')
                        if isinstance(reg_raw, list) and len(reg_raw) >= 14:
                            install_battery = reg_raw[1] # Use index 1 for voltage, not 2
                            install_fw = reg_raw[13].replace('-', '.') if isinstance(reg_raw[13], str) else reg_raw[13]
                            portal_install_batt = portal_battery(install_battery)
                            result_lines.append(f"📝 Last Registration: {registration_info.get('last_seen', 'N/A')}")
                            result_lines.append(f"🔋 Last Reset Battery: {portal_install_batt}%")
                            if install_fw:
                                result_lines.append(f"💾 Last Reset FW: {install_fw}")
                except Exception as e:
                    result_lines.append(f"❌ Error getting heartbeat/registration: {str(e)}")
        
        # If no meaningful data was found, add a message.
        if not found_anything:
            result_lines.append("\n🤷 No information found for this ICCID.")

        return "\n".join(result_lines)

    except Exception as e:
        return f"❌ Error performing lookup: {str(e)}"

def start_slack_listener():
    """Start the Slack listener in a separate thread"""
    global slack_listener_thread, slack_stop_event
    if slack_listener_thread is None or not slack_listener_thread.is_alive():
        slack_stop_event.clear()
        slack_listener_thread = threading.Thread(target=slack_listener_worker, daemon=True)
        slack_listener_thread.start()
        print_info("🚀 Slack listener started")

def stop_slack_listener():
    """Stop the Slack listener"""
    global slack_listener_thread, slack_stop_event
    if slack_listener_thread and slack_listener_thread.is_alive():
        slack_stop_event.set()
        slack_listener_thread.join(timeout=5)
        print_info("🛑 Slack listener stopped")

def load_account_mapping():
    """Load account ID to name mapping from JSON file (or example if main not found)"""
    account_file_path = os.path.join(BACKEND_ROOT_DIR, "accounts.json")
    account_example_file_path = os.path.join(BACKEND_ROOT_DIR, "accounts.json.example")

    try:
        if os.path.exists(account_file_path):
            with open(account_file_path, "r") as file:
                accounts = json.load(file)
                print_info(f"INFO: Loaded account mapping from {account_file_path}")
                return {account["aws_account_id"]: account for account in accounts}
        elif os.path.exists(account_example_file_path):
            with open(account_example_file_path, "r") as file:
                accounts = json.load(file)
                print_info(f"WARNING: '{account_file_path}' not found. Loaded example account mapping from '{account_example_file_path}'. Please create and configure '{account_file_path}' for production use.")
                return {account["aws_account_id"]: account for account in accounts}
        else:
            print_info(f"Warning: Neither '{account_file_path}' nor '{account_example_file_path}' found.")
            return {}
    except Exception as e:
        print_info(f"Error loading account mapping: {e}")
        return {}

# Load account mapping at startup
ACCOUNT_MAPPING = load_account_mapping()

def get_account_name(account_id):
    """Get account name from account ID"""
    account = ACCOUNT_MAPPING.get(account_id, {})
    return account.get("name", "Unknown Account")

def get_user_pool_id(account_id):
    """Get Cognito User Pool ID from account mapping"""
    account = ACCOUNT_MAPPING.get(account_id, {})
    return account.get("user_pool_id")

def get_profile_for_account(account_id, account_name):
    """Try to match account to available AWS profile"""
    for profile in AVAILABLE_PROFILES:
        if profile.lower() == account_name.lower() or profile == account_id:
            return profile
    return None

def find_iotbackup_bucket(s3_client):
    """Find the IoT backup bucket"""
    try:
        response = s3_client.list_buckets()
        for bucket in response['Buckets']:
            bucket_name = bucket['Name']
            if 'iotbackuprule' in bucket_name.lower() or 'iotbackuprul' in bucket_name.lower():
                return bucket_name
        return None
    except Exception as e:
        debug_print(f"Error finding iotbackup bucket: {e}")
        return None

def list_all_s3_objects(s3_client, bucket_name, prefix):
    """List all S3 objects with given prefix"""
    try:
        paginator = s3_client.get_paginator('list_objects_v2')
        page_iterator = paginator.paginate(Bucket=bucket_name, Prefix=prefix)
        objects = []
        for page in page_iterator:
            if 'Contents' in page:
                for obj in page['Contents']:
                    objects.append(obj['Key'])
        return objects
    except Exception as e:
        debug_print(f"Error listing objects: {e}")
        return []

def download_from_s3(s3_client, bucket_name, key):
    """Download object from S3"""
    try:
        response = s3_client.get_object(Bucket=bucket_name, Key=key)
        return response['Body'].read()
    except Exception as e:
        debug_print(f"Error downloading from S3: {e}")
        return None

def decode_messagepack(data):
    """Decode MessagePack data"""
    try:
        return msgpack.unpackb(data, raw=False)
    except Exception as e:
        debug_print(f"Error decoding MessagePack: {e}")
        return None

def decode_heartbeat_v1(data):
    """Decode version 1 heartbeat data"""
    try:
        unpacked = msgpack.unpackb(data, raw=False)
        if isinstance(unpacked, (list, tuple)) and len(unpacked) > 1 and isinstance(unpacked[1], dict):
            return unpacked[1]
        if isinstance(unpacked, dict):
            return unpacked
        if isinstance(unpacked, list) and len(unpacked) >= 12:
            return {
                'timestamp': unpacked[1],
                'battery_percentage': unpacked[2],
                'battery_voltage': unpacked[3],
                'ax': unpacked[4],
                'ay': unpacked[5],
                'az': unpacked[6],
                'hdop': unpacked[7],
                'lng': unpacked[8],
                'lat': unpacked[9],
                'firmware_version': unpacked[10],
                'gps_connected': bool(unpacked[11]) if len(unpacked) > 11 else False
            }
        debug_print(f"Unexpected unpacked type in decode_heartbeat_v1: {type(unpacked)} - {unpacked}")
        return None
    except Exception as e:
        debug_print(f"Error decoding heartbeat v1: {e}")
        return None

def format_gps_location(lat, lng):
    """Format GPS coordinates with Google Maps link"""
    if lat == 'N/A' or lng == 'N/A' or lat is None or lng is None:
        return "N/A"

    try:
        # Format coordinates
        lat_formatted = format_coordinate(lat)
        lng_formatted = format_coordinate(lng)

        # Create Google Maps URL (this is already quite short)
        # Wrap in angle brackets to prevent Slack link preview
        maps_url = f"<https://maps.google.com/?q={lat},{lng}>"

        return f"{lat_formatted}, {lng_formatted} {maps_url}"
    except Exception as e:
        debug_print(f"Error formatting GPS location: {e}")
        return f"{lat}, {lng}"

def format_coordinate(coord):
    """Format coordinate to 6 decimal places"""
    if coord == 'N/A' or coord is None:
        return 'N/A'
    try:
        return f"{float(coord):.6f}"
    except (ValueError, TypeError):
        return 'N/A'

def get_latest_heartbeat_info(box_id, account_id, s3_client, max_search=31):
    """Get latest heartbeat information for a device"""
    try:
        bucket_name = find_iotbackup_bucket(s3_client)
        debug_print(f"Found bucket: {bucket_name}")
        if not bucket_name:
            debug_print("No iotbackup bucket found")
            return None

        search_count = 0
        now = datetime.now()

        while search_count < max_search:
            date_to_search = now - timedelta(days=search_count)
            search_count += 1
            date_str = date_to_search.strftime("%Y-%m-%d")
            year, month, day = date_str.split('-')
            base_path = f"{year}/{month}/{day}/Inovia/dev/LittleTheo/"
            heartbeat_path = f"{base_path}{box_id}/v1-0/heartbeat/push/"

            debug_print(f"Searching date {date_str}, path: {heartbeat_path}")

            objects = list_all_s3_objects(s3_client, bucket_name, heartbeat_path)
            debug_print(f"Found {len(objects)} objects in {heartbeat_path}")

            if objects:
                latest_obj = max(objects)
                debug_print(f"Latest object: {latest_obj}")

                data = download_from_s3(s3_client, bucket_name, latest_obj)
                if not data:
                    debug_print(f"Failed to download data from {latest_obj}")
                    continue

                debug_print(f"Downloaded {len(data)} bytes")

                vals = decode_messagepack(data)
                if not vals or len(vals) == 0:
                    debug_print("Failed to decode messagepack or empty data")
                    continue

                debug_print(f"Decoded messagepack, first value: {vals[0] if len(vals) > 0 else 'None'}")

                try:
                    fw_version = int(str(vals[0]))
                    debug_print(f"Firmware version: {fw_version}")
                except (ValueError, IndexError):
                    debug_print(f"Failed to parse firmware version from {vals[0] if len(vals) > 0 else 'None'}")
                    continue

                hb = None
                if fw_version > 1000:
                    debug_print("Treating as unversioned (timestamp)")
                    hb = decode_messagepack(data)
                else:
                    if fw_version == 1:
                        debug_print("Treating as version 1 heartbeat")
                        hb = decode_heartbeat_v1(data)
                    else:
                        debug_print(f"Unknown firmware version: {fw_version}")
                        continue

                debug_print(f"Decoded heartbeat: {hb}")

                # Handle dictionary-based heartbeats (v1 and others)
                if isinstance(hb, dict) and 'timestamp' in hb:
                    timestamp = hb['timestamp']
                    dt = datetime.fromtimestamp(timestamp)
                    debug_print(f"Successfully parsed dict heartbeat with timestamp: {timestamp}")
                    return {
                        'last_seen': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'battery_percentage': hb.get('battery_percentage', 'N/A'),
                        'battery_voltage': hb.get('battery_voltage', 'N/A'),
                        'gps_connected': hb.get('gps_connected', False),
                        'lat': format_coordinate(hb.get('lat', 'N/A')),
                        'lng': format_coordinate(hb.get('lng', 'N/A')),
                        'firmware_version': hb.get('firmware_version', 'N/A')
                    }
                # Handle list-based "unversioned" heartbeats
                elif isinstance(hb, list) and len(hb) >= 11:
                    timestamp = hb[0]
                    dt = datetime.fromtimestamp(timestamp)
                    debug_print(f"Successfully parsed list heartbeat with timestamp: {timestamp}")
                    return {
                        'last_seen': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'battery_percentage': hb[1],
                        'battery_voltage': hb[2],
                        'gps_connected': bool(hb[10]),
                        'lat': format_coordinate(hb[8]),
                        'lng': format_coordinate(hb[7]),
                        'firmware_version': hb[9]
                    }
                else:
                    debug_print("No timestamp found in heartbeat data or format is unrecognized")

        debug_print(f"No heartbeat data found after searching {max_search} days")
        return None
    except Exception as e:
        debug_print(f"Error getting heartbeat info: {e}")
        if DEBUG_MODE:
            import traceback
            traceback.print_exc()
        return None

def get_latest_registration_info(box_id, account_id, s3_client, max_search=31):
    """Get latest registration information for a device"""
    try:
        bucket_name = find_iotbackup_bucket(s3_client)
        debug_print(f"REG: Found bucket: {bucket_name}")
        if not bucket_name:
            debug_print("REG: No iotbackup bucket found")
            return None

        search_count = 0
        now = datetime.now()

        while search_count < max_search:
            date_to_search = now - timedelta(days=search_count)
            search_count += 1
            date_str = date_to_search.strftime("%Y-%m-%d")
            year, month, day = date_str.split('-')

            base_path = f"{year}/{month}/{day}/Inovia/dev/LittleTheo/"
            registration_path = f"{base_path}{box_id}/v1-0/registration/push/"

            debug_print(f"REG: Searching date {date_str}, path: {registration_path}")

            objects = list_all_s3_objects(s3_client, bucket_name, registration_path)
            debug_print(f"REG: Found {len(objects)} objects in {registration_path}")

            if objects:
                latest_obj = max(objects)
                debug_print(f"REG: Latest object: {latest_obj}")

                data = download_from_s3(s3_client, bucket_name, latest_obj)
                if not data:
                    debug_print(f"REG: Failed to download data from {latest_obj}")
                    continue

                debug_print(f"REG: Downloaded {len(data)} bytes")

                vals = decode_messagepack(data)
                if not vals or len(vals) == 0:
                    debug_print("REG: Failed to decode messagepack or empty data")
                    continue

                debug_print(f"REG: Decoded messagepack: {vals}")

                reg = None
                if isinstance(vals, dict):
                    reg = vals
                elif isinstance(vals, list) and len(vals) > 0:
                    if isinstance(vals[0], dict):
                        reg = vals[0]
                    elif len(vals) > 1 and isinstance(vals[1], dict):
                        reg = vals[1]
                    else:
                        reg = vals
                else:
                    reg = vals

                debug_print(f"REG: Processed registration data: {reg}")

                if isinstance(reg, dict) and 'timestamp' in reg:
                    timestamp = reg['timestamp']
                    dt = datetime.fromtimestamp(timestamp)
                    debug_print(f"REG: Successfully parsed registration with timestamp: {timestamp}")
                    return {
                        'last_seen': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        **{k: v for k, v in reg.items() if k != 'timestamp'}
                    }
                elif isinstance(reg, list) and len(reg) > 0 and isinstance(reg[0], (int, float)):
                    timestamp = reg[0]
                    dt = datetime.fromtimestamp(timestamp)
                    debug_print(f"REG: Successfully parsed registration (list) with timestamp: {timestamp}")
                    return {
                        'last_seen': dt.strftime('%Y-%m-%d %H:%M:%S'),
                        'raw': reg
                    }
                else:
                    debug_print("REG: No timestamp found in registration data")

        debug_print(f"REG: No registration data found after searching {max_search} days")
        return None

    except Exception as e:
        debug_print(f"REG: Error getting registration info: {e}")
        if DEBUG_MODE:
            import traceback
            traceback.print_exc()
        return None

def format_timestamp(unix_timestamp):
    """Format Unix timestamp to readable format"""
    dt = datetime.fromtimestamp(int(unix_timestamp))
    return dt.strftime("%d %b %Y @ %H:%M:%S")

def check_battery_replacement(iccid):
    """Check if battery has been replaced for this ICCID"""
    try:
        response = dev_s3_client.get_object(Bucket=CONFIG['aws']['s3']['support_bucket'], Key="battery_swap/replacement_battery.txt")
        content = response['Body'].read().decode('utf-8')
        replacements = content.strip().splitlines()
        return iccid in replacements
    except Exception as e:
        debug_print(f"Error checking battery replacement: {e}")
        return False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    print_info(f"Received signal {signum}, shutting down...")
    stop_slack_listener()
    sys.exit(0)




def main():
    """Main daemon function"""
    # Note: config is loaded at the top of the script
    print_info(f"GOD-Tool Daemon Listener starting... v{__version__}")

    if DEBUG_MODE:
        print_info("Debug mode enabled")

    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start Slack listener if enabled in config
    global slack_listener_enabled
    slack_listener_enabled = CONFIG['settings'].get("listener_enabled", False)

    if slack_listener_enabled:
        start_slack_listener()
        print_info("Slack listener enabled and started")
    else:
        print_info("Slack listener disabled")

    print_info("Daemon is running. Press Ctrl+C to stop.")

    try:
        # Keep the main thread alive
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print_info("Keyboard interrupt received, shutting down...")
        stop_slack_listener()

if __name__ == "__main__":
    main()