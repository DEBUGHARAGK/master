import boto3
import json
import logging
import pandas as pd
from io import BytesIO
from botocore.exceptions import ClientError

# Set up logging
logger = logging.getLogger()
logger.setLevel(logging.INFO)

# Initialize Bedrock client
client = boto3.client("bedrock-runtime", region_name="us-west-2")

class BedrockLLM:
    def __init__(self, model_id):
        self.model_id = model_id

    def generate_code(self, prompt: str) -> str:
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2500,
            "temperature": 0.2,
            "top_p": 0.999,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        }

        try:
            response = client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json"
            )
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except ClientError as e:
            logger.error(f"Error invoking Bedrock model: {e}")
            raise

def lambda_handler(event, context):
    try:
        # S3 bucket and key information
        input_bucket = "genius-llm-test"
        input_key = "input/STT-sample.xlsx"
        output_bucket = "genius-llm-test"
        output_key = "output/python-etl-mapping-output-pradeep.py"

        # Initialize S3 client and read Excel file
        s3 = boto3.client('s3')
        response = s3.get_object(Bucket=input_bucket, Key=input_key)
        df = pd.read_excel(BytesIO(response['Body'].read()))

        # Prepare transformation details
        transformations = []
        for _, row in df.iterrows():
            transformations.append({
                'source_table': row['Source Table'],
                'source_column': row['Source Column'],
                'target_table': row['Target Table'],
                'target_column': row['Target Column'],
                'logic': row['Transformation Logic']
            })

        # Initialize Bedrock LLM
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        llm = BedrockLLM(model_id=model_id)

        # Generate ETL code with self-validation
        prompt = f"""
        Create a Python ETL script that performs all the following transformations in a single function:

        {json.dumps(transformations, indent=2)}

        Requirements:
        1. Use pandas for data manipulation.
        2. Create a single `transform_data` function that applies all transformations.
        3. The `transform_data` function should take a DataFrame as input and return the transformed DataFrame.
        4. Implement basic error handling and logging within the `transform_data` function.
        5. Add brief comments explaining each transformation step.
        6. Follow PEP 8 style guidelines.
        7. Keep the code concise and efficient.
        8. Include a `validate_transformations` function that checks if all transformations were applied correctly.
        9. In the main function, use `validate_transformations` to verify the results.

        Provide the complete Python script, including:
        - Necessary imports
        - Logging setup
        - The `transform_data` function containing all transformations
        - The `validate_transformations` function
        - A main function that demonstrates usage with a sample DataFrame

        Ensure the script is self-contained and can be run independently.
        """

        full_script = llm.generate_code(prompt)

        # Save the generated Python code to the output S3 file
        s3.put_object(Body=full_script.encode("utf-8"), Bucket=output_bucket, Key=output_key)
        logger.info(f"Successfully wrote ETL script to s3://{output_bucket}/{output_key}")

        # Validate the generated code
        validation_prompt = f"""
        The following Python script was generated for an ETL process:

        {full_script}

        Please review this script and confirm if it meets all the requirements:
        1. Uses pandas for data manipulation
        2. Includes a single `transform_data` function that applies all transformations
        3. The `transform_data` function takes a DataFrame as input and returns the transformed DataFrame
        4. Implements error handling and logging within the `transform_data` function
        5. Contains comments explaining each transformation step
        6. Follows PEP 8 style guidelines
        7. Includes a `validate_transformations` function
        8. Has a main function demonstrating usage with a sample DataFrame
        9. Is self-contained and can be run independently

        If all requirements are met, respond with "VALID". If not, respond with "INVALID" and provide a brief explanation of what's missing or incorrect.
        """

        validation_result = llm.generate_code(validation_prompt)

        if "VALID" in validation_result:
            logger.info("Generated ETL script passed validation.")
            return {
                "statusCode": 200,
                "body": json.dumps({"message": "ETL code generation, validation, and upload successful"})
            }
        else:
            logger.error(f"Generated ETL script failed validation: {validation_result}")
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Generated ETL script failed validation", "details": validation_result})
            }

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({"error": str(e)})
        }
