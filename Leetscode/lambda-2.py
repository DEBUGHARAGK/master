import json
import time
import boto3
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from botocore.exceptions import ClientError

# Initialize clients
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

# Constants
CLAUDE_MODEL_ID = "arn:aws:bedrock:us-east-1:851725293109:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0"
MAX_RETRIES = 5  # Maximum retry attempts
BACKOFF_FACTOR = 2  # Exponential backoff multiplier
INITIAL_DELAY = 1  # Initial delay in seconds


def lambda_handler(event, context):
    """Process SQS messages."""
    for record in event["Records"]:
        try:
            # Parse SQS message
            message = json.loads(record["body"])
            user_prompt = message["user_prompt"]
            response_url = message["response_url"]

            print(f"Processing user prompt: {user_prompt}")

            # Construct the prompt for Bedrock
            final_prompt = f"You are Claude, an AI assistant. User query: {user_prompt}"
            response_payload = invoke_bedrock_with_retry(final_prompt)

            print(f"Bedrock response: {response_payload}")

            # Send response back to Slack
            slack_response = {
                "response_type": "in_channel",
                "text": f"*Prompt:* {user_prompt}\n*Response:* {response_payload}",
            }
            send_to_slack(response_url, slack_response)

        except Exception as e:
            print(f"Error processing message: {e}")


def invoke_bedrock_with_retry(prompt):
    """Invoke Bedrock with exponential backoff for throttling."""
    retries = 0
    delay = INITIAL_DELAY

    while retries < MAX_RETRIES:
        try:
            # Prepare Bedrock payload
            bedrock_payload = {
                "modelId": CLAUDE_MODEL_ID,
                "contentType": "application/json",
                "accept": "application/json",
                "body": {
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 500,
                    "temperature": 1,
                    "top_p": 0.999,
                    "messages": [{"role": "user", "content": prompt}],
                },
            }

            print(f"Invoking Bedrock model (attempt {retries + 1})...")
            response = bedrock_client.invoke_model_with_response_stream(
                modelId=bedrock_payload["modelId"],
                contentType=bedrock_payload["contentType"],
                accept=bedrock_payload["accept"],
                body=json.dumps(bedrock_payload["body"]),
            )

            response_payload = ""
            for event in response["body"]:
                if "chunk" in event:
                    chunk_data = json.loads(event["chunk"]["bytes"].decode("utf-8"))
                    if "delta" in chunk_data and "text" in chunk_data["delta"]:
                        response_payload += chunk_data["delta"]["text"]

            return response_payload

        except ClientError as e:
            if e.response["Error"]["Code"] == "ThrottlingException":
                print(
                    f"ThrottlingException encountered. Retrying in {delay} seconds..."
                )
                time.sleep(delay)
                retries += 1
                delay *= BACKOFF_FACTOR  # Exponential backoff
            else:
                raise e

    raise Exception(
        "Max retries exceeded. Unable to process request due to throttling."
    )


def send_to_slack(response_url, slack_response):
    """Send response back to Slack."""
    try:
        print(f"Sending response to Slack via {response_url}")
        req = Request(
            response_url,
            method="POST",
            data=json.dumps(slack_response).encode("utf-8"),
            headers={"Content-Type": "application/json"},
        )
        with urlopen(req) as res:
            res_body = res.read()
        print(f"Response sent to Slack: {res_body}")
    except (HTTPError, URLError) as e:
        print(f"Error sending response to Slack: {e}")
