import json
from urllib.parse import parse_qs
from urllib.request import Request, urlopen
from urllib.error import HTTPError, URLError
from botocore.exceptions import ClientError
import boto3
import os
from langchain.prompts import PromptTemplate

# AWS Clients
bedrock_client = boto3.client("bedrock-runtime", region_name="us-east-1")

# Constants
SLACK_VERIFICATION_TOKEN = os.environ["SLACK_VERIFICATION_TOKEN"]
CLAUDE_MODEL_ID = "arn:aws:bedrock:us-east-1:851725293109:inference-profile/us.anthropic.claude-3-5-sonnet-20241022-v2:0"

# LangChain PromptTemplate
template = """
You are Claude, an AI assistant. Please provide a helpful and detailed response to the user's query.
User Query: {user_query}
Assistant:
"""
prompt = PromptTemplate(input_variables=["user_query"], template=template)


def lambda_handler(event, context):
    """Main Lambda handler for Slackbot."""
    print(f"Event received: {json.dumps(event)}")

    # Step 1: Parse and verify Slack request
    try:
        body = event["body"]
        params = parse_qs(body)
        token = params["token"][0]
        user_prompt = params.get("text", [""])[0]
        response_url = params["response_url"][0]

        if token != SLACK_VERIFICATION_TOKEN:
            print("Invalid Slack verification token")
            return {"statusCode": 400, "body": "Invalid token."}

        print(f"User prompt: {user_prompt}")
    except Exception as e:
        print(f"Error parsing Slack request: {e}")
        return {"statusCode": 400, "body": "Invalid request"}

    # Step 2: Acknowledge Slack immediately
    ack_response = {
        "response_type": "ephemeral",
        "text": "Processing your request. You will receive a response shortly.",
    }
    print("Sending acknowledgment...")
    return {"statusCode": 200, "body": json.dumps(ack_response)}

    # Step 3: Trigger asynchronous processing
    try:
        process_request_async(user_prompt, response_url)
    except Exception as e:
        print(f"Error scheduling async task: {e}")


def process_request_async(user_prompt, response_url):
    """Handles the request asynchronously."""
    try:
        # Construct prompt
        final_prompt = prompt.format(user_query=user_prompt)
        print(f"Final prompt: {final_prompt}")

        # Prepare Bedrock payload
        bedrock_payload = {
            "modelId": CLAUDE_MODEL_ID,
            "contentType": "application/json",
            "accept": "application/json",
            "body": {
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 300,  # Reduced for faster response
                "temperature": 0.7,
                "top_p": 0.9,
                "messages": [{"role": "user", "content": final_prompt}],
            },
        }

        # Invoke Bedrock
        print("Invoking Bedrock...")
        bedrock_response = invoke_bedrock(bedrock_payload)

        # Process Bedrock response
        response_payload = ""
        for event in bedrock_response["body"]:
            if "chunk" in event:
                chunk_data = json.loads(event["chunk"]["bytes"].decode("utf-8"))
                if "delta" in chunk_data and "text" in chunk_data["delta"]:
                    response_payload += chunk_data["delta"]["text"]

        print(f"Bedrock response payload: {response_payload}")

        # Send final response to Slack
        slack_response = {
            "response_type": "in_channel",
            "text": f"*Prompt:* {user_prompt}\n*Response:* {response_payload}",
        }
        send_to_slack(response_url, slack_response)

    except Exception as e:
        print(f"Error during async processing: {e}")
        error_response = {
            "response_type": "ephemeral",
            "text": "An error occurred while processing your request.",
        }
        send_to_slack(response_url, error_response)


def invoke_bedrock(payload):
    """Invoke Bedrock without retries."""
    try:
        response = bedrock_client.invoke_model_with_response_stream(
            modelId=payload["modelId"],
            contentType=payload["contentType"],
            accept=payload["accept"],
            body=json.dumps(payload["body"]),
        )
        print("Bedrock invocation succeeded.")
        return response
    except ClientError as e:
        print(f"Bedrock invocation failed: {e}")
        raise e


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
            print(f"Response sent to Slack: {res.read()}")
    except (HTTPError, URLError) as e:
        print(f"Error sending to Slack: {e}")
