import json
import os
from urllib.parse import parse_qs
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
import boto3
from botocore.exceptions import ClientError

# Initialize clients
sqs_client = boto3.client("sqs")
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

# Constants
SLACK_VERIFICATION_TOKEN = os.environ["SLACK_VERIFICATION_TOKEN"]
SQS_QUEUE_URL = "https://sqs.us-east-1.amazonaws.com/851725293109/slack-bot"
CLAUDE_MODEL_ID = "arn:aws:bedrock:us-east-1:851725293109:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0"


def lambda_handler(event, context):
    """Main Lambda handler for Slackbot."""
    print(f"Event received: {json.dumps(event)}")

    # Parse and verify Slack request
    try:
        body = event["body"]
        params = parse_qs(body)
        token = params["token"][0]
        user_prompt = params.get("text", [""])[0]
        response_url = params["response_url"][0]

        if token != SLACK_VERIFICATION_TOKEN:
            raise ValueError("Invalid Slack verification token")

        print(f"Received user prompt: {user_prompt}")
    except (KeyError, ValueError, IndexError) as e:
        print(f"Error parsing request body: {e}")
        return {"statusCode": 400, "body": "Invalid request body"}

    # Publish the user query and response URL to SQS
    try:
        sqs_message = {
            "user_prompt": user_prompt,
            "response_url": response_url,
        }
        sqs_client.send_message(
            QueueUrl=SQS_QUEUE_URL,
            MessageBody=json.dumps(sqs_message),
        )
        print("Message published to SQS successfully.")
    except ClientError as e:
        print(f"Error sending message to SQS: {e}")
        return {"statusCode": 500, "body": "Error sending message to SQS"}

    # # Respond to Slack immediately
    # ack_response = {
    #     "response_type": "ephemeral",
    #     "text": "Processing your request. You will receive a response shortly.",
    # }
    # return {"statusCode": 200, "body": json.dumps(ack_response)}

    return {"statusCode": 200}
