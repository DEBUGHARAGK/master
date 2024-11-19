import boto3
import pandas as pd
import json
import logging
from io import BytesIO
from datetime import datetime
from typing import Dict, Any, List
from langchain.prompts import PromptTemplate

# Set up logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class S3Manager:
    """Handles S3 operations."""

    def __init__(self, bucket: str):
        self.bucket = bucket
        self.s3_client = boto3.client("s3")

    def read_excel_file(self, key: str) -> pd.DataFrame:
        """Reads an Excel file from S3 and returns it as a DataFrame."""
        try:
            logger.info(f"Reading Excel file from S3: s3://{self.bucket}/{key}")
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return pd.read_excel(BytesIO(response["Body"].read()))
        except Exception as e:
            logger.error(f"Error reading Excel file: {e}")
            raise

    def save_python_script(self, script: str, key: str) -> None:
        """Saves a Python script as a plain text file in S3."""
        try:
            logger.info(f"Saving Python script to S3: s3://{self.bucket}/{key}")
            self.s3_client.put_object(
                Body=script.encode("utf-8"),
                Bucket=self.bucket,
                Key=key,
                ContentType="text/plain",
            )
            logger.info(f"Python script saved successfully to s3://{self.bucket}/{key}")
        except Exception as e:
            logger.error(f"Error saving Python script: {e}")
            raise


class BedrockLLM:
    """Wrapper for invoking Bedrock's Claude model."""

    def __init__(self, model_id: str, region_name: str):
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=region_name)

    def invoke_model(self, prompt: str) -> str:
        """Invokes the Bedrock Claude model with the given prompt."""
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2500,
            "temperature": 0.2,
            "top_p": 0.95,
            "messages": [
                {"role": "user", "content": [{"type": "text", "text": prompt}]}
            ],
        }
        try:
            logger.info("Invoking Bedrock Claude model...")
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(payload),
                contentType="application/json",
                accept="application/json",
            )
            response_body = json.loads(response["body"].read())
            return response_body["content"][0]["text"]
        except Exception as e:
            logger.error(f"Error invoking Bedrock model: {e}")
            raise


class ETLCodeGenerator:
    """Manages ETL code generation and validation."""

    def __init__(self, bucket: str, model_id: str, region_name: str):
        self.s3_manager = S3Manager(bucket)
        self.bedrock_llm = BedrockLLM(model_id, region_name)

    def extract_transformations(self, df: pd.DataFrame) -> List[Dict[str, str]]:
        """Extracts transformations from an Excel DataFrame."""
        return [
            {
                "source_table": row["Source Table"],
                "source_column": row["Source Column"],
                "target_table": row["Target Table"],
                "target_column": row["Target Column"],
                "logic": row["Transformation Logic"],
            }
            for _, row in df.iterrows()
        ]

    def generate_python_code_with_mock_data(
        self, transformations: List[Dict[str, str]]
    ) -> str:
        """Generates Python ETL code with mock data using LangChain PromptTemplate and Bedrock Claude."""
        prompt_template = PromptTemplate(
            input_variables=["transformations"],
            template="""You are an ETL Development Expert Agent.
Based on the following transformations:
{transformations}

Generate a Python script that:
1. Dynamically creates mock data based on the columns and transformation rules.
2. Uses pandas to perform data transformations.
3. Includes a `transform_data` function.
4. Includes a `main` function to demonstrate loading the mock data, applying the transformations, and saving the results.
5. Handles logging and error management.
6. Implements proper data validation.
7. Is production-ready and adheres to Python best practices.""",
        )
        prompt = prompt_template.format(
            transformations=json.dumps(transformations, indent=2)
        )
        return self.bedrock_llm.invoke_model(prompt)

    def validate_python_code(self, script: str) -> str:
        """Validates the generated Python code using LangChain PromptTemplate and Bedrock Claude."""
        prompt_template = PromptTemplate(
            input_variables=["script"],
            template="""You are a Python Code Validator.
Review the following Python ETL script:
{script}

Check for:
1. Correct implementation of transformations.
2. Proper error handling, logging, and modularity.
3. Adherence to Python best practices (PEP 8).
4. Optimization for large data operations.

Respond with "VALID" if the code is valid or provide issues if invalid.""",
        )
        prompt = prompt_template.format(script=script)
        return self.bedrock_llm.invoke_model(prompt)


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for generating, validating, and saving Python ETL code with mock data.

    Args:
        event (Dict[str, Any]): Input event for transformations.
        context (Any): Lambda execution context.

    Returns:
        Dict[str, Any]: Lambda response with generated Python code and validation results.
    """
    try:
        # Configuration
        bucket = "genius-llm-test"  # Replace with your bucket name
        input_key = "input/STT-sample.xlsx"  # Replace with your input file key
        output_key = f"output/python-etl-{datetime.now().strftime('%Y%m%d_%H%M%S')}.py"
        model_id = "anthropic.claude-3-5-sonnet-20241022-v2:0"
        region_name = "us-west-2"

        # Initialize ETL Code Generator
        generator = ETLCodeGenerator(bucket, model_id, region_name)

        # Step 1: Read Excel file from S3
        logger.info("Reading Excel file from S3...")
        input_df = generator.s3_manager.read_excel_file(input_key)

        # Step 2: Extract transformations
        logger.info("Extracting transformations from Excel...")
        transformations = generator.extract_transformations(input_df)
        logger.info(f"Extracted Transformations: {transformations}")

        # Step 3: Generate Python ETL code with mock data
        logger.info("Generating Python ETL code with mock data...")
        python_code = generator.generate_python_code_with_mock_data(transformations)
        logger.info(f"Generated Python Code:\n{python_code}")

        # Step 4: Validate Python ETL code
        logger.info("Validating Python ETL code...")
        validation_result = generator.validate_python_code(python_code)
        logger.info(f"Validation Result: {validation_result}")

        if "VALID" not in validation_result:
            raise Exception(f"Generated code failed validation: {validation_result}")

        # Step 5: Save Python script to S3
        logger.info("Saving validated Python code to S3...")
        generator.s3_manager.save_python_script(python_code, output_key)

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "message": "Python ETL code generated, validated, and saved successfully.",
                    "output_location": f"s3://{bucket}/{output_key}",
                    "validation_result": validation_result,
                }
            ),
        }

    except Exception as e:
        logger.error(f"Error in Lambda function: {e}")
        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
