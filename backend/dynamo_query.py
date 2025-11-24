
import boto3
from boto3.dynamodb.conditions import Key
from datetime import datetime, timedelta

def query_dynamodb():
    """
    Queries the 'Refurb-Table' for entries in the last 2 weeks and provides a breakdown
    by the '3_User-Port' field. Returns a dictionary of statistics.
    """
    table_name = 'Refurb-Table'
    try:
        # Use the 'dev' profile for AWS credentials
        session = boto3.Session(profile_name='dev')
        dynamodb = session.resource('dynamodb')
        table = dynamodb.Table(table_name)

        # Calculate the date 2 weeks ago
        two_weeks_ago = datetime.now() - timedelta(weeks=2)
        two_weeks_ago_iso = two_weeks_ago.isoformat()

        # Perform a scan with a filter expression
        response = table.scan(
            FilterExpression=Key('dateTime').gt(two_weeks_ago_iso)
        )

        items = response.get('Items', [])
        
        while 'LastEvaluatedKey' in response:
            response = table.scan(
                FilterExpression=Key('dateTime').gt(two_weeks_ago_iso),
                ExclusiveStartKey=response['LastEvaluatedKey']
            )
            items.extend(response.get('Items', []))

        total_count = len(items)
        cramlington1_count = 0
        cramlington1_gsm_fw_count = 0
        cramlington1_gnss_gsm_null_count = 0
        total_gsm_fw_count = 0
        total_gnss_gsm_null_count = 0

        for item in items:
            port = item.get('3_User-Port', '')
            if port.startswith('cramlington1'):
                cramlington1_count += 1
                if item.get('6_GSM FW loaded') is not None:
                    cramlington1_gsm_fw_count += 1
                if item.get('5_GNSS FW loaded') is None and item.get('6_GSM FW loaded') is None:
                    cramlington1_gnss_gsm_null_count += 1
            
            if item.get('6_GSM FW loaded') is not None:
                total_gsm_fw_count += 1
            if item.get('5_GNSS FW loaded') is None and item.get('6_GSM FW loaded') is None:
                total_gnss_gsm_null_count += 1

        stats = {
            "message": f"Successfully queried {total_count} entries from {table_name}.",
            "table_name": table_name,
            "total_entries": total_count,
            "investigations": {
                "total": cramlington1_count,
                "modem_issues": cramlington1_gsm_fw_count,
                "total_passed": cramlington1_gnss_gsm_null_count,
                "percentage_modem_issues": (cramlington1_gsm_fw_count / cramlington1_count) * 100 if cramlington1_count > 0 else 0,
                "percentage_total_passed": (cramlington1_gnss_gsm_null_count / cramlington1_count) * 100 if cramlington1_count > 0 else 0,
            },
            "all_entries": {
                "total": total_count,
                "modem_issues": total_gsm_fw_count,
                "total_passed": total_gnss_gsm_null_count,
                "percentage_modem_issues": (total_gsm_fw_count / total_count) * 100 if total_count > 0 else 0,
                "percentage_total_passed": (total_gnss_gsm_null_count / total_count) * 100 if total_count > 0 else 0,
            }
        }
        return stats

    except Exception as e:
        return {"error": f"An error occurred while querying {table_name}: {str(e)}", "table_name": table_name}
