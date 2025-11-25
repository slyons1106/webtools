from fastapi import FastAPI, HTTPException, Query, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pathlib import Path
import configparser
from typing import List, Set, Dict, Any
from pydantic import BaseModel
import boto3
import time
from datetime import datetime, timedelta # Added timedelta
import re
import os
from botocore.exceptions import ClientError
import base64
import tempfile
import shutil

# New imports for godtool functions
import json
import msgpack
import sys
import signal
import csv
import math
import subprocess
from .dynamo_query import query_dynamodb
from .combined_counter2 import generate_report
from .csv_splitter import split_csv_and_zip
from fastapi.responses import StreamingResponse
import io
import tempfile
from pathlib import Path

app = FastAPI()

# Add CORS middleware to allow requests from the frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

@app.get("/api/tools/modem-failed-count")
def get_modem_failed_count():
    try:
        stats = query_dynamodb()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/api/labels/today")
def get_labels_today():
    try:
        report = generate_report(date_offset='today')
        return {"output": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.get("/api/labels/tomorrow")
def get_labels_tomorrow():
    try:
        report = generate_report(date_offset='tomorrow')
        return {"output": report}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


# --- Configuration Loading ---
try:
    from . import config
except ImportError:
    print("FATAL: Could not import config.py. Please create this file from config.py.example.")
    sys.exit(1)

# AWS Sessions
dev_session = boto3.Session(profile_name=config.AWS_PROFILES['dev'])
gateway_session = boto3.Session(profile_name=config.AWS_PROFILES['gateway'])

dev_dynamodb = dev_session.resource("dynamodb")
gateway_dynamodb = gateway_session.resource("dynamodb")

# DynamoDB Tables
refurb_table = dev_dynamodb.Table(config.DYNAMODB_TABLES['refurb'])
device_reg_table = gateway_dynamodb.Table(config.DYNAMODB_TABLES['device_registration'])
pat_labels_table = gateway_dynamodb.Table(config.DYNAMODB_TABLES['pat_labels'])

# S3 Setup
s3_client = gateway_session.client("s3")
dev_s3_client = dev_session.client("s3")

# Load account mapping
ACCOUNT_MAPPING = {} # Initialize
try:
    with open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "accounts.json"), "r") as file:
        accounts_data = json.load(file)
        ACCOUNT_MAPPING = {account["aws_account_id"]: account for account in accounts_data}
except FileNotFoundError:
    print("Warning: accounts.json file not found in backend directory.")
except Exception as e:
    print(f"Error loading accounts.json: {e}")

# --- End Configuration Loading ---

# --- GOD-Tool Helper Functions (adapted from godtool_with_cognito_release.py) ---

# Note: debug_print and print_info are adapted to use standard print for FastAPI context
def debug_print(message):
    """Print debug messages only if debug mode is enabled (always off in FastAPI unless explicitly set)"""
    # For FastAPI, we'll assume debug mode is off unless a global flag is set
    # For now, just print if you want to see debug messages in FastAPI logs
    # if DEBUG_MODE: # DEBUG_MODE is not defined globally in this context
    print(f"[DEBUG] {message}")

def print_info(message):
    """Print info messages with timestamp"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{timestamp}] {message}")

BATTERY_WEIGHTINGS_DATA = None
def load_battery_weightings():
    """Load the battery weightings from BatteryWeightings.csv (relative to script)"""
    global BATTERY_WEIGHTINGS_DATA
    SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
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

def find_customer_user_pool_id(session: boto3.Session) -> str | None:
    """
    Lists Cognito User Pools for a given session and returns the ID of the first one
    whose name contains 'Customer'.
    """
    try:
        cognito_client = session.client("cognito-idp")
        response = cognito_client.list_user_pools(MaxResults=60) # MaxResults up to 60
        
        for user_pool in response.get('UserPools', []):
            if "Customer" in user_pool.get('Name', ''):
                debug_print(f"PERSON: Found Customer User Pool: {user_pool['Name']} ({user_pool['Id']})")
                return user_pool['Id']
        debug_print("PERSON: No 'Customer' User Pool found.")
        return None
    except Exception as e:
        debug_print(f"PERSON: Error finding Customer User Pool: {e}")
        return None

def perform_person_lookup(person_id: str) -> Dict[str, Any]:
    """Perform Person ID lookup and return a structured dictionary of results."""
    
    person_data = {
        "person_id": person_id,
        "account": None,
        "cognito_user": None,
        "errors": []
    }

    try:
        # 1. Query pat-labels table to get account ID
        account_id = None
        try:
            response = pat_labels_table.query(
                IndexName="PersonID-index",
                KeyConditionExpression=boto3.dynamodb.conditions.Key("PersonID").eq(person_id)
            )
            items = response.get("Items", [])
            
            if not items:
                response = pat_labels_table.get_item(
                    Key={"ID": person_id, "Metadata": "FULFILMENT#REQUEST"}
                )
                item = response.get("Item")
                if item:
                    items = [item]
            
            if items:
                item = items[0]
                account_id = item.get("AccountID")
                if account_id:
                    account_name = get_account_name(account_id)
                    person_data["account"] = {
                        "id": account_id,
                        "name": account_name
                    }
                else:
                    person_data["errors"].append("No AccountID found for this Person ID in pat-labels.")
            else:
                person_data["errors"].append("Person ID not found in pat-labels table.")
                return person_data # Exit early if no account found
            
        except Exception as e:
            person_data["errors"].append(f"Error querying pat-labels: {str(e)}")
            return person_data # Exit early on error

        # 2. Get AWS session for the account
        session = get_aws_session_for_account(account_id)
        if not session:
            person_data["errors"].append("Could not determine AWS profile for the account. Cannot retrieve Cognito data.")
            return person_data

        # 3. Find Customer User Pool ID
        user_pool_id = find_customer_user_pool_id(session)
        if not user_pool_id:
            person_data["errors"].append(f"No 'Customer' Cognito User Pool found for account {person_data['account']['name']}.")
            return person_data

        # 4. Get Cognito User Details
        try:
            cognito_client = session.client("cognito-idp")
            user_response = cognito_client.admin_get_user(
                UserPoolId=user_pool_id,
                Username=person_id
            )
            
            user_attributes = {attr['Name']: attr['Value'] for attr in user_response.get('UserAttributes', [])}
            person_data["cognito_user"] = {
                "username": user_response.get('Username'),
                "status": user_response.get('UserStatus'),
                "enabled": user_response.get('Enabled'),
                "attributes": user_attributes
            }

            # 5. Get Cognito User Groups (REMOVED as per user request)
            # groups_response = cognito_client.admin_list_groups_for_user(
            #     UserPoolId=user_pool_id,
            #     Username=person_id
            # )
            # customer_groups = [
            #     group['GroupName'] for group in groups_response.get('Groups', [])
            #     if "Customer" in group['GroupName']
            # ]
            # person_data["cognito_groups"] = customer_groups

        except cognito_client.exceptions.UserNotFoundException:
            person_data["errors"].append(f"User {person_id} not found in Cognito User Pool.")
        except Exception as e:
            person_data["errors"].append(f"Error retrieving Cognito user details: {str(e)}")

    except Exception as e:
        person_data["errors"].append(f"An unexpected error occurred during person lookup: {str(e)}")
    
    return person_data

def log_battery_data(iccid, voltage):
    """Appends a new voltage reading to the battery data log. (Placeholder for FastAPI)"""
    # In a FastAPI context, logging to a local CSV might not be desired or possible.
    # This function is kept for compatibility but its behavior might need adjustment.
    print_info(f"Battery data logging (placeholder): ICCID={iccid}, Voltage={voltage}")

@app.get("/api/person_lookup")
def person_lookup(person_id: str = Query(..., description="The Person ID (UUID) to lookup.")):
    try:
        return perform_person_lookup(person_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

def get_iot_info_for_thing(thing_name: str, iot_client_instance, iot_data_client_instance) -> Dict:
    """
    Retrieves a summary of the last 6 IoT Job executions, the Thing Shadow,
    and the Thing's description for a given thing.
    Returns a dictionary containing all this information.
    """
    output = {"jobs": [], "shadow": None, "description": None}

    # 1. Describe the Thing itself
    try:
        debug_print(f"IoT Describe: Attempting to describe thing: {thing_name}")
        thing_description = iot_client_instance.describe_thing(thingName=thing_name)
        debug_print(f"IoT Describe: Raw response for {thing_name}: {thing_description}")
        
        # Filter what we want to keep
        output["description"] = {
            "thingName": thing_description.get("thingName"),
            "attributes": thing_description.get("attributes", {}),
            "version": thing_description.get("version")
        }

    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            debug_print(f"IoT Describe: Thing {thing_name} not found in AWS IoT Core.")
        else:
            debug_print(f"IoT Describe: ClientError describing thing {thing_name}: {e}")
        # If the thing doesn't exist, no point in looking for jobs or shadow
        return output
    except Exception as e:
        debug_print(f"IoT Describe: Unexpected error describing thing {thing_name}: {e}")
        return output


    # 2. Get IoT Jobs
    try:
        debug_print(f"IoT Jobs: Attempting to list jobs for thingName: {thing_name}")
        response = iot_client_instance.list_job_executions_for_thing(
            thingName=thing_name,
            maxResults=6
        )
        debug_print(f"IoT Jobs: Raw response for {thing_name}: {response}")
        
        jobs_summary = []
        execution_summaries = response.get('executionSummaries', [])
        debug_print(f"IoT Jobs: Execution summaries for {thing_name}: {execution_summaries}")

        for job_execution in execution_summaries:
            summary = job_execution.get('jobExecutionSummary', {})
            job_id = job_execution['jobId']
            status = summary.get('status')
            last_updated_at = summary.get('lastUpdatedAt')
            
            simplified_status = "queued"
            if status in ["SUCCEEDED", "CANCELED", "REMOVED"]:
                simplified_status = "pass"
            elif status in ["FAILED", "TIMED_OUT", "REJECTED"]:
                simplified_status = "fail"
            elif status in ["QUEUED", "IN_PROGRESS"]:
                simplified_status = "queued"

            jobs_summary.append({
                "jobId": job_id,
                "status": status,
                "simplified_status": simplified_status,
                "lastUpdatedAt": last_updated_at.strftime("%Y-%m-%d %H:%M:%S") if last_updated_at else "N/A"
            })
        output["jobs"] = jobs_summary
    except ClientError as e:
        debug_print(f"IoT Jobs: ClientError getting IoT jobs for thing {thing_name}: {e}")
    except Exception as e:
        debug_print(f"IoT Jobs: Unexpected error getting IoT jobs for thing {thing_name}: {e}")

    # 3. Get Thing Shadow
    try:
        debug_print(f"IoT Shadow: Attempting to get shadow for thingName: {thing_name}")
        shadow_response = iot_data_client_instance.get_thing_shadow(thingName=thing_name)
        debug_print(f"IoT Shadow: Raw response for {thing_name}: {shadow_response}")
        
        payload = shadow_response.get('payload')
        if payload:
            shadow_data = json.loads(payload.read())
            output["shadow"] = shadow_data
            
    except ClientError as e:
        if e.response['Error']['Code'] == 'ResourceNotFoundException':
            debug_print(f"IoT Shadow: No shadow found for thing {thing_name}")
        else:
            debug_print(f"IoT Shadow: ClientError getting shadow for thing {thing_name}: {e}")
    except Exception as e:
        debug_print(f"IoT Shadow: Unexpected error getting shadow for thing {thing_name}: {e}")
        
    return output


def perform_device_lookup(iccid, user_id=None):
    """Perform ICCID lookup and return a structured dictionary of results."""
    
    result_data = {
        "general": {},
        "registration": None,
        "heartbeat": None,
        "iot": None,
        "errors": []
    }

    try:
        # --- General Info ---
        result_data["general"]["iccid"] = iccid
        result_data["general"]["year_of_manufacture"] = extract_year_of_manufacture(iccid)

        # --- Refurb Table Check ---
        try:
            response = refurb_table.query(KeyConditionExpression=boto3.dynamodb.conditions.Key("iccid").eq(iccid))
            result_data["general"]["refurb_records"] = len(response.get("Items", []))
        except Exception as e:
            result_data["errors"].append(f"Error checking Refurb-Table: {str(e)}")

        # --- Device Registration Check ---
        account_id = None
        account_name = None
        try:
            response = device_reg_table.get_item(Key={"ID": iccid, "Metadata": "ACCOUNTALLOCATION"})
            item = response.get("Item")
            if item:
                account_id = item.get("AccountID")
                print(f"INFO: Device lookup for ICCID {iccid} found AccountID: {account_id}. Verifying this ID exists in your config's ACCOUNT_TO_PROFILE_MAPPING.")
                account_name = get_account_name(account_id) if account_id else "Unknown"
                
                # Initialize registration data
                registration_data = {
                    "account_name": account_name,
                    "registration_time": format_timestamp(item.get("CreatedAt")) if item.get("CreatedAt") else "N/A",
                    "firmware_on_registration": None,
                    "battery_on_registration": None
                }

                # Get account-specific session for S3 lookup
                session_for_s3 = get_aws_session_for_account(account_id)
                if session_for_s3:
                    s3_client_for_reg = session_for_s3.client("s3")
                    latest_s3_reg_info = get_latest_registration_info(iccid, account_id, s3_client_for_reg)
                    
                    if latest_s3_reg_info and latest_s3_reg_info.get('raw'):
                        reg_raw = latest_s3_reg_info['raw']
                        if isinstance(reg_raw, list) and len(reg_raw) >= 14:
                            install_battery = reg_raw[1]
                            install_fw = reg_raw[13].replace('-', '.') if isinstance(reg_raw[13], str) else reg_raw[13]
                            portal_install_batt = portal_battery(install_battery)

                            registration_data["firmware_on_registration"] = install_fw
                            registration_data["battery_on_registration"] = portal_install_batt

                result_data["registration"] = registration_data

        except Exception as e:
            result_data["errors"].append(f"Error checking registration: {str(e)}")

        # --- Device Type & Battery Replacement ---
        try:
            if iccid.startswith("894303017220"):
                result_data["general"]["device_type"] = "ST Device"
            elif iccid > "8943030172210000":
                result_data["general"]["device_type"] = "GD Device"
            
            if check_battery_replacement(iccid):
                result_data["general"]["battery_replaced"] = True
        except Exception:
            pass

        # --- Account-Specific Lookups (Heartbeat & IoT) ---
        session = get_aws_session_for_account(account_id)
        if session:
            try:
                # Heartbeat
                s3_client_local = session.client("s3")
                heartbeat_info = get_latest_heartbeat_info(iccid, account_id, s3_client_local, max_search=config.HEARTBEAT_MAX_SEARCH_DAYS)
                if heartbeat_info:
                    raw_voltage = heartbeat_info.get("battery_voltage")
                    log_battery_data(iccid, raw_voltage)
                    
                    lat = heartbeat_info.get('lat')
                    lng = heartbeat_info.get('lng')
                    location = "N/A"
                    maps_url = None
                    if lat and lng and lat != 'nan' and lng != 'nan':
                        location = f"{lat}, {lng}"
                        maps_url = f"https://maps.google.com/?q={lat},{lng}"

                    result_data["heartbeat"] = {
                        "last_seen": heartbeat_info.get('last_seen'),
                        "firmware": heartbeat_info.get('firmware_version', 'N/A'),
                        "battery_percentage": portal_battery(heartbeat_info.get("battery_percentage")),
                        "gps_status": "Connected" if heartbeat_info.get('gps_connected') else "Disconnected",
                        "location": location,
                        "location_url": maps_url
                    }

                # IoT Info
                iot_client_local = session.client("iot", region_name='eu-west-1')
                iot_data_client_local = session.client("iot-data", region_name='eu-west-1')
                iot_info = get_iot_info_for_thing(iccid, iot_client_local, iot_data_client_local)
                
                iot_result = {"jobs": iot_info.get("jobs"), "shadow": None}

                # Process Shadow
                shadow = iot_info.get("shadow")
                if shadow and 'state' in shadow and 'reported' in shadow['state']:
                    reported_state = shadow['state'].get('reported', {})
                    
                    desired_keys_map = {
                        "latest-bootloader": "Latest-Bootloader",
                        "latest-firmware": "Latest-Firmware",
                        "latest-fallback": "Latest-Fallback",
                        "debug": "Debug",
                        "heartbeat-interval": "Heartbeat-Interval",
                        "battery-low-threshold": "Battery-Low-Threshold",
                        "trip-timeout": "Trip-Timeout",
                        "after-trip-reports": "After-Trip-Reports",
                        "heartbeat-tod": "Heartbeat-Tod",
                        "heartbeat-enable": "Heartbeat-Enable",
                        "daily-upload-time": "Daily-Upload-Time"
                    }
                    
                    processed_shadow = {}
                    try:
                        metadata = shadow.get('metadata', {}).get('reported', {})
                        if metadata:
                            for key, value in metadata.items():
                                if isinstance(value, dict) and 'timestamp' in value:
                                    ts = value['timestamp']
                                    processed_shadow["Last Updated"] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                                    break
                    except Exception:
                        pass

                    for key, display_key in desired_keys_map.items():
                        processed_shadow[display_key] = reported_state.get(key, "Null")
                    
                    iot_result["shadow"] = processed_shadow

                result_data["iot"] = iot_result

            except Exception as e:
                result_data["errors"].append(f"Error during account-specific lookups: {str(e)}")
        else:
            result_data["errors"].append("Could not determine AWS profile for the account. Cannot retrieve Heartbeat or IoT data.")
        
        return result_data

    except Exception as e:
        # debug_print(f"Major error in perform_device_lookup: {e}")
        return {"error": f"An unexpected error occurred: {str(e)}"}



def get_account_name(account_id):
    """Get account name from account ID"""
    account = ACCOUNT_MAPPING.get(account_id, {})
    return account.get("name", "Unknown Account")

def get_user_pool_id(account_id):
    """Get Cognito User Pool ID from account mapping"""
    account = ACCOUNT_MAPPING.get(account_id, {})
    return account.get("user_pool_id")

def get_aws_session_for_account(account_id: str) -> boto3.Session | None:
    """
    Finds the correct AWS profile for a given Account ID by looking up the explicit
    mapping in the config file and returns a boto3 Session.
    """
    try:
        if not account_id:
            debug_print("SESSION: No account_id provided to get_aws_session_for_account.")
            return None

        # Look up the profile name from the mapping in config.py
        profile_name = config.ACCOUNT_TO_PROFILE_MAPPING.get(account_id)

        if profile_name:
            debug_print(f"SESSION: Found profile '{profile_name}' for Account '{account_id}' in config mapping.")
            # Verify the profile exists before trying to use it
            if profile_name not in boto3.Session().available_profiles:
                debug_print(f"SESSION: WARNING - Profile '{profile_name}' for Account '{account_id}' is defined in config but NOT FOUND in system's AWS profiles.")
                return None
            return boto3.Session(profile_name=profile_name)
        else:
            debug_print(f"SESSION: No profile mapping found for Account '{account_id}' in config.ACCOUNT_TO_PROFILE_MAPPING.")
            return None
    except Exception as e:
        debug_print(f"SESSION: Error getting session for Account {account_id}: {e}")
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
    """Format GPS coordinates with Google Maps link (not used in current perform_slack_lookup output)"""
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
        # if DEBUG_MODE: # DEBUG_MODE is not defined globally in this context
        #     import traceback
        #     traceback.print_exc()
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
        # if DEBUG_MODE: # DEBUG_MODE is not defined globally in this context
        #     import traceback
        #     traceback.print_exc()
        return None

def format_timestamp(unix_timestamp):
    """Format Unix timestamp to readable format"""
    dt = datetime.fromtimestamp(int(unix_timestamp))
    return dt.strftime("%d %b %Y @ %H:%M:%S")

def check_battery_replacement(iccid):
    """Check if battery has been replaced for this ICCID"""
    try:
        response = dev_s3_client.get_object(Bucket=config.S3_BUCKETS['support_bucket'], Key="battery_swap/replacement_battery.txt")
        content = response['Body'].read().decode('utf-8')
        replacements = content.strip().splitlines()
        return iccid in replacements
    except Exception as e:
        debug_print(f"Error checking battery replacement: {e}")
        return False

# --- End GOD-Tool Helper Functions ---

# --- Pydantic Models ---
class SearchRequest(BaseModel):
    profile: str
    handler: str
    search_term: str
    start_time: datetime
    end_time: datetime

class LogResult(BaseModel):
    timestamp: str
    message: str
    logStream: str
    log: str

class S3Item(BaseModel):
    name: str
    type: str  # 'folder' or 'file'
    key: str

class S3Object(BaseModel):
    key: str
    content: str # base64 data URL
    size: int
    last_modified: datetime

class GeneralInfo(BaseModel):
    iccid: str | None = None
    year_of_manufacture: str | None = None
    refurb_records: int | None = None
    device_type: str | None = None
    battery_replaced: bool | None = None

class RegistrationInfo(BaseModel):
    account_name: str | None = None
    registration_time: str | None = None
    firmware_on_registration: str | None = None
    battery_on_registration: int | str | None = None

class HeartbeatInfo(BaseModel):
    last_seen: str | None = None
    firmware: str | None = None
    battery_percentage: int | str | None = None # Can be int or "N/A"
    gps_status: str | None = None
    location: str | None = None
    location_url: str | None = None

class IoTJob(BaseModel):
    jobId: str | None = None
    status: str | None = None
    simplified_status: str | None = None
    lastUpdatedAt: str | None = None

class IoTInfo(BaseModel):
    jobs: List[IoTJob] | None = None
    shadow: Dict[str, Any] | None = None # Use Dict[str, Any] for the nested shadow structure

class DeviceLookupResponse(BaseModel):
    general: GeneralInfo
    registration: RegistrationInfo | None = None
    heartbeat: HeartbeatInfo | None = None
    iot: IoTInfo | None = None
    errors: List[str]

class ShadowUpdateRequest(BaseModel):
    iccid: str
    desired_state: Dict[str, Any]

class SetPersonEnabledRequest(BaseModel):
    person_id: str
    enabled: bool


# --- Logic ---
def get_aws_session_for_account(account_id: str) -> boto3.Session | None:
    """
    Finds the correct AWS profile for a given Account ID and returns a boto3 Session.
    """
    try:
        if not account_id:
            return None
            
        account_name = get_account_name(account_id)
        matched_profile = get_profile_for_account(account_id, account_name)

        if matched_profile:
            debug_print(f"SESSION: Found profile '{matched_profile}' for Account {account_id}")
            return boto3.Session(profile_name=matched_profile)
        else:
            debug_print(f"SESSION: Could not find a matching profile for account {account_name} ({account_id})")
            return None
    except Exception as e:
        debug_print(f"SESSION: Error getting session for Account {account_id}: {e}")
        return None

def get_aws_session_for_iccid(iccid: str) -> boto3.Session | None:
    """
    Finds the correct AWS profile for a given ICCID and returns a boto3 Session.
    """
    try:
        response = device_reg_table.get_item(Key={"ID": iccid, "Metadata": "ACCOUNTALLOCATION"})
        item = response.get("Item")
        if not item or not item.get("AccountID"):
            debug_print(f"SESSION: No AccountID found for ICCID {iccid}")
            return None
        
        account_id = item["AccountID"]
        return get_aws_session_for_account(account_id)
    except Exception as e:
        debug_print(f"SESSION: Error getting session for ICCID {iccid}: {e}")
        return None

def get_aws_profiles() -> List[str]:
    """
    Returns a sorted list of all unique AWS profile names the application is
    configured to use, drawn from the ACCOUNT_TO_PROFILE_MAPPING.
    """
    try:
        # Use a set to get all unique profile names from the mapping
        profiles = set(config.ACCOUNT_TO_PROFILE_MAPPING.values())
        print(f"DEBUG: Returning AWS profiles from mapping: {profiles}")
        return sorted(list(profiles))
    except AttributeError:
        print("DEBUG: config.ACCOUNT_TO_PROFILE_MAPPING not found. Returning empty list.")
        return []
    except Exception as e:
        # Log the error and return an empty list to prevent crashing
        print(f"Error reading AWS profiles from config mapping: {e}")
        return []

# --- API Endpoints ---
@app.get("/api/aws-profiles", response_model=List[str])
def read_aws_profiles():
    return get_aws_profiles()

@app.get("/api/handlers", response_model=List[str])
def get_handlers(profile: str = Query(..., description="The AWS profile to use.")):
    try:
        session = boto3.Session(profile_name=profile)
        client = session.client("logs")
        paginator = client.get_paginator("describe_log_groups")
        handler_names: Set[str] = set()
        handler_regex = re.compile(r'(\w+Handler)')
        for page in paginator.paginate():
            for group in page["logGroups"]:
                found_handlers = handler_regex.findall(group["logGroupName"])
                for handler in found_handlers:
                    handler_names.add(handler)
        return sorted(list(handler_names))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/search", response_model=List[LogResult])
def search_logs(request: SearchRequest):
    try:
        session = boto3.Session(profile_name=request.profile)
        client = session.client("logs")
        log_group_search_string = request.handler
        paginator = client.get_paginator("describe_log_groups")
        log_group_names = []
        for page in paginator.paginate():
            for group in page["logGroups"]:
                if log_group_search_string in group["logGroupName"]:
                    log_group_names.append(group["logGroupName"])
        if not log_group_names:
            raise HTTPException(status_code=404, detail=f"No log groups found containing '{log_group_search_string}'")
        query = f"""fields @timestamp, @message, @logStream, @log
| filter @message like /{request.search_term}/
| sort @timestamp desc
| limit 1000"""
        start_query_response = client.start_query(
            logGroupNames=log_group_names,
            startTime=int(request.start_time.timestamp()),
            endTime=int(request.end_time.timestamp()),
            queryString=query,
        )
        query_id = start_query_response["queryId"]
        response = None
        while response is None or response["status"] in ["Running", "Scheduled"]:
            time.sleep(1)
            response = client.get_query_results(queryId=query_id)
        results = []
        for record in response["results"]:
            result_item = {}
            for field in record:
                if field["field"] == "@ptr":
                    continue
                result_item[field["field"].replace("@", "")] = field["value"]
            results.append(LogResult(**result_item))
        return results
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/s3/list", response_model=List[S3Item])
def s3_list_items(bucket: str, prefix: str = ""):
    try:
        session = boto3.Session(profile_name='gateway')
        s3 = session.client("s3")
        paginator = s3.get_paginator("list_objects_v2")
        items = []
        for page in paginator.paginate(Bucket=bucket, Prefix=prefix, Delimiter="/"):
            for common in page.get("CommonPrefixes", []):
                folder_key = common["Prefix"]
                items.append(S3Item(name=folder_key.replace(prefix, "").strip("/"), type="folder", key=folder_key))
            for item in page.get("Contents", []):
                file_key = item["Key"]
                if file_key == prefix: continue
                items.append(S3Item(name=os.path.basename(file_key), type="file", key=file_key))
        return items
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            raise HTTPException(status_code=403, detail="Access Denied. Ensure the 'gateway' AWS profile has s3:ListBucket permissions.")
        else:
            raise HTTPException(status_code=500, detail=f"Boto3 ClientError: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/s3/object", response_model=S3Object)
def s3_get_object(bucket: str, key: str):
    try:
        session = boto3.Session(profile_name='gateway')
        s3 = session.client("s3")
        obj = s3.get_object(Bucket=bucket, Key=key)
        raw = obj["Body"].read()
        
        img_bytes = None
        try:
            text = raw.decode("utf-8", errors="strict").strip()
        except UnicodeDecodeError:
            text = None

        if raw.startswith(b'\x89PNG\r\n\x1a\n'):
            img_bytes = raw
        elif text is not None:
            if text.startswith("data:image/png;base64,"):
                text = text.split(",", 1)[1].strip()
            b64 = "".join(text.split())
            try:
                img_bytes = base64.b64decode(b64, validate=True)
            except (base64.binascii.Error, ValueError):
                img_bytes = base64.b64decode(b64, validate=False)
        else:
            img_bytes = raw

        if not img_bytes:
            raise HTTPException(status_code=400, detail="Could not decode image content.")

        b64_content = base64.b64encode(img_bytes).decode('utf-8')
        data_url = f"data:image/png;base64,{b64_content}"

        return S3Object(
            key=key,
            content=data_url,
            size=obj["ContentLength"],
            last_modified=obj["LastModified"]
        )
    except ClientError as e:
        if e.response['Error']['Code'] == 'AccessDenied':
            raise HTTPException(status_code=403, detail="Access Denied. Ensure the 'gateway' AWS profile has s3:GetObject permissions.")
        else:
            raise HTTPException(status_code=500, detail=f"Boto3 ClientError: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/device_lookup", response_model=DeviceLookupResponse)
def device_lookup(iccid: str = Query(..., description="The ICCID (device ID) to lookup.")):
    if not re.fullmatch(r"^[0-9]{19,20}$", iccid):
        raise HTTPException(status_code=400, detail="Invalid ICCID format. Must be 19 or 20 digits.")
    try:
        # user_id=None as this is an API call, not Slack
        return perform_device_lookup(iccid, user_id=None)
    except Exception as e:
        debug_print(f"Error in /api/device_lookup: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred during device lookup: {str(e)}")

@app.get("/api/person_lookup")
def person_lookup(person_id: str = Query(..., description="The Person ID (UUID) to lookup.")):
    try:
        return perform_person_lookup(person_id)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/api/set_person_enabled_status")
def set_person_enabled_status(request: SetPersonEnabledRequest):
    """
    Enables or disables a Cognito user.
    """
    # Find the account ID from the person ID
    account_id = None
    try:
        response = pat_labels_table.query(
            IndexName="PersonID-index",
            KeyConditionExpression=boto3.dynamodb.conditions.Key("PersonID").eq(request.person_id)
        )
        items = response.get("Items", [])
        if items:
            account_id = items[0].get("AccountID")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Could not find account for person: {e}")

    if not account_id:
        raise HTTPException(status_code=404, detail="Person not found or no account associated.")

    # Get the session for that account
    session = get_aws_session_for_account(account_id)
    if not session:
        raise HTTPException(status_code=404, detail="Could not determine AWS profile for the account.")

    # Find the user pool
    user_pool_id = find_customer_user_pool_id(session)
    if not user_pool_id:
        raise HTTPException(status_code=404, detail="No 'Customer' Cognito User Pool found for account.")

    try:
        cognito_client = session.client("cognito-idp")
        
        if request.enabled:
            cognito_client.admin_enable_user(
                UserPoolId=user_pool_id,
                Username=request.person_id
            )
            message = f"Successfully enabled user {request.person_id}."
        else:
            cognito_client.admin_disable_user(
                UserPoolId=user_pool_id,
                Username=request.person_id
            )
            message = f"Successfully disabled user {request.person_id}."
        
        debug_print(f"PERSON ENABLE/DISABLE: {message}")
        return {"message": message}

    except ClientError as e:
        debug_print(f"PERSON ENABLE/DISABLE ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"AWS Error: {e}")
    except Exception as e:
        debug_print(f"PERSON ENABLE/DISABLE ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/api/update_shadow")
def update_shadow(request: ShadowUpdateRequest):
    """
    Updates the 'desired' state of a Thing's shadow.
    """
    session = get_aws_session_for_iccid(request.iccid)
    if not session:
        raise HTTPException(status_code=404, detail="Device registration not found or AWS profile could not be determined.")

    try:
        iot_data_client = session.client("iot-data", region_name='eu-west-1')
        
        # The payload for update_thing_shadow must be a JSON string
        payload = {"state": {"desired": request.desired_state}}
        
        debug_print(f"SHADOW UPDATE: Thing={request.iccid}, Payload={json.dumps(payload)}")

        iot_data_client.update_thing_shadow(
            thingName=request.iccid,
            payload=json.dumps(payload)
        )
        
        return {"message": "Shadow update request sent successfully."}

    except ClientError as e:
        debug_print(f"SHADOW UPDATE ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"AWS Error: {e}")
    except Exception as e:
        debug_print(f"SHADOW UPDATE ERROR: {e}")
        raise HTTPException(status_code=500, detail=f"An unexpected error occurred: {str(e)}")


@app.post("/api/csvsplitter/split")
async def split_csv_file(
    file: UploadFile = File(...),
    rows_per_chunk: int = Query(..., ge=1, description="Number of rows per chunk for splitting the CSV.")
):
    """
    Receives a CSV file, splits it into multiple chunks based on rows_per_chunk,
    zips each chunk, and returns a single ZIP file containing all chunk zips.
    """
    # Create a temporary directory for file operations
    with tempfile.TemporaryDirectory() as temp_dir:
        temp_path = Path(temp_dir)

        # Save the uploaded file to a temporary location
        input_csv_path = temp_path / file.filename
        try:
            with open(input_csv_path, "wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Could not save uploaded file: {e}")

        try:
            # Call the splitting and zipping logic
            final_zip_path = split_csv_and_zip(input_csv_path, rows_per_chunk, temp_path)

            # Read the generated zip file into a BytesIO object
            zip_file_content = io.BytesIO()
            with open(final_zip_path, "rb") as f:
                zip_file_content.write(f.read())
            zip_file_content.seek(0)

            # Return the zip file as a StreamingResponse
            return StreamingResponse(
                zip_file_content,
                media_type="application/zip",
                headers={"Content-Disposition": f"attachment; filename={final_zip_path.name}"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"CSV splitting failed: {e}")


@app.get("/health")

def read_root():

    return {"status": "ok"}
