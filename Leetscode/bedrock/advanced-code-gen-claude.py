import boto3
import json
import logging
import pandas as pd
from io import BytesIO
from botocore.exceptions import ClientError
from typing import Dict, List, Tuple, Any
from langchain.prompts import PromptTemplate
from datetime import datetime

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class ETLPromptManager:
    """Manages prompts for ETL code generation and validation."""
    
    @staticmethod
    def get_code_generation_prompt() -> PromptTemplate:
        """Returns the prompt template for ETL code generation."""
        return PromptTemplate(
            input_variables=["transformations"],
            template="""You are an ETL Development Expert Agent, powered by Anthropic's Claude-3.5-Sonnet model, specialized in generating data transformation code. Your capabilities include:

<capabilities>
1. Analyzing source and target data structures
2. Creating efficient ETL transformation logic
3. Implementing data quality checks and validations
4. Writing production-ready Python code with proper error handling
5. Applying best practices for logging and monitoring
6. Optimizing code performance for large datasets
7. Ensuring code maintainability and readability
8. Validating transformation outputs
9. Generating comprehensive documentation
</capabilities>

<technical_requirements>
1. Use pandas for data manipulation
2. Implement proper error handling and logging
3. Follow PEP 8 style guidelines
4. Create reusable and modular functions
5. Include input validation checks
6. Add appropriate type hints
7. Write clear docstrings and comments
8. Include unit tests where appropriate
</technical_requirements>

<input_data_schema>
The transformation specifications are provided in the following format:
{transformations}
</input_data_schema>

<output_requirements>
Generate a complete Python ETL script that includes:
1. All necessary imports
2. Logging configuration
3. A main transform_data function implementing all transformations
4. A validate_transformations function
5. Error handling for all operations
6. Sample usage in a main function
7. Appropriate logging statements
8. Input validation checks
9. Performance optimization considerations
</output_requirements>

<code_style_guidelines>
1. Use meaningful variable and function names
2. Include type hints for function parameters and return values
3. Add docstrings for all functions
4. Use appropriate logging levels
5. Follow the single responsibility principle
6. Implement proper exception handling
7. Use consistent formatting
8. Add helpful comments for complex logic
</code_style_guidelines>

Based on these requirements, generate a production-ready Python ETL script that implements all the specified transformations while following best practices for code quality, performance, and maintainability."""
        )

    @staticmethod
    def get_validation_prompt() -> PromptTemplate:
        """Returns the prompt template for code validation."""
        return PromptTemplate(
            input_variables=["script"],
            template="""As an ETL Code Validation Expert, review the following Python script:

{script}

Validate the code against these criteria:

<functional_requirements>
1. Implements all required transformations correctly
2. Contains proper error handling and logging
3. Includes input validation checks
4. Has appropriate documentation
5. Follows coding best practices
</functional_requirements>

<technical_validation>
1. Uses pandas efficiently
2. Implements proper error handling
3. Includes comprehensive logging
4. Follows PEP 8 guidelines
5. Contains required functions:
   - transform_data
   - validate_transformations
6. Has clear documentation
7. Includes sample usage
8. Is self-contained and runnable
</technical_validation>

<performance_considerations>
1. Efficient data operations
2. Proper memory management
3. Optimized transformations
4. Scalability considerations
</performance_considerations>

Analyze the code and respond with either:
1. "VALID" if all requirements are met
2. "INVALID" with specific issues if any requirements are not met

Provide a brief explanation of your validation decision."""
        )

class S3Manager:
    """Handles S3 operations for ETL code generation."""
    
    def __init__(self, bucket: str):
        """
        Initialize S3Manager.
        
        Args:
            bucket (str): S3 bucket name
        """
        self.bucket = bucket
        self.s3_client = boto3.client('s3')
        
    def read_excel_file(self, key: str) -> pd.DataFrame:
        """
        Read Excel file from S3.
        
        Args:
            key (str): S3 object key
            
        Returns:
            pd.DataFrame: DataFrame containing the Excel data
        """
        try:
            response = self.s3_client.get_object(Bucket=self.bucket, Key=key)
            return pd.read_excel(BytesIO(response['Body'].read()))
        except Exception as e:
            logger.error(f"Error reading Excel file from S3: {e}")
            raise
            
    def save_python_script(self, script: str, key: str) -> None:
        """
        Save Python script to S3.
        
        Args:
            script (str): Generated Python script
            key (str): S3 object key
        """
        try:
            self.s3_client.put_object(
                Body=script.encode("utf-8"),
                Bucket=self.bucket,
                Key=key,
                ContentType='text/plain'
            )
            logger.info(f"Successfully saved script to s3://{self.bucket}/{key}")
        except Exception as e:
            logger.error(f"Error saving script to S3: {e}")
            raise

class BedrockLLM:
    """Wrapper for Amazon Bedrock's Claude model."""
    
    def __init__(self, model_id: str, region_name: str = "us-west-2"):
        """
        Initialize BedrockLLM.
        
        Args:
            model_id (str): Bedrock model identifier
            region_name (str): AWS region name
        """
        self.model_id = model_id
        self.client = boto3.client("bedrock-runtime", region_name=region_name)
        
    def generate_code(self, prompt: str) -> str:
        """
        Generate code using Bedrock model.
        
        Args:
            prompt (str): Input prompt
            
        Returns:
            str: Generated code or validation result
        """
        payload = {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 2500,
            "temperature": 0.2,
            "top_p": 0.999,
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}]}]
        }

        try:
            response = self.client.invoke_model(
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

class ETLCodeGenerator:
    """Main class for ETL code generation process."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize ETLCodeGenerator.
        
        Args:
            config (Dict[str, Any]): Configuration dictionary containing:
                - bucket: S3 bucket name
                - model_id: Bedrock model identifier
                - region_name: AWS region name
        """
        self.s3_manager = S3Manager(config['bucket'])
        self.llm = BedrockLLM(config['model_id'], config['region_name'])
        self.prompt_manager = ETLPromptManager()
        
    def extract_transformations(self, df: pd.DataFrame) -> List[Dict[str, str]]:
        """
        Extract transformations from DataFrame.
        
        Args:
            df (pd.DataFrame): Input DataFrame
            
        Returns:
            List[Dict[str, str]]: List of transformation specifications
        """
        transformations = []
        for _, row in df.iterrows():
            transformations.append({
                'source_table': row['Source Table'],
                'source_column': row['Source Column'],
                'target_table': row['Target Table'],
                'target_column': row['Target Column'],
                'logic': row['Transformation Logic']
            })
        return transformations
        
    def generate_and_validate_code(
        self, 
        transformations: List[Dict[str, str]]
    ) -> Tuple[str, bool, str]:
        """
        Generate and validate ETL code.
        
        Args:
            transformations (List[Dict[str, str]]): Transformation specifications
            
        Returns:
            Tuple[str, bool, str]: Generated code, validation status, and validation message
        """
        # Generate code
        code_prompt = self.prompt_manager.get_code_generation_prompt().format(
            transformations=json.dumps(transformations, indent=2)
        )
        generated_code = self.llm.generate_code(code_prompt)
        
        # Validate code
        validation_prompt = self.prompt_manager.get_validation_prompt().format(
            script=generated_code
        )
        validation_result = self.llm.generate_code(validation_prompt)
        
        is_valid = "VALID" in validation_result
        return generated_code, is_valid, validation_result

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """
    AWS Lambda handler for ETL code generation.
    
    Args:
        event (Dict[str, Any]): Lambda event
        context (Any): Lambda context
        
    Returns:
        Dict[str, Any]: Response containing status and message
    """
    try:
        # Configuration
        config = {
            'bucket': 'genius-llm-test',
            'model_id': 'anthropic.claude-3-5-sonnet-20241022-v2:0',
            'region_name': 'us-west-2'
        }
        
        # Initialize generator
        generator = ETLCodeGenerator(config)
        
        # Input/output paths
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        input_key = "input/STT-sample.xlsx"
        output_key = f"output/python-etl-mapping-{timestamp}.py"
        
        # Read input file
        df = generator.s3_manager.read_excel_file(input_key)
        transformations = generator.extract_transformations(df)
        
        # Generate and validate code
        generated_code, is_valid, validation_result = generator.generate_and_validate_code(
            transformations
        )
        
        # Save generated code
        generator.s3_manager.save_python_script(generated_code, output_key)
        
        if is_valid:
            logger.info("ETL code generation successful and validated")
            return {
                "statusCode": 200,
                "body": json.dumps({
                    "message": "ETL code generation, validation, and upload successful",
                    "output_location": f"s3://{config['bucket']}/{output_key}"
                })
            }
        else:
            logger.error(f"Generated ETL script failed validation: {validation_result}")
            return {
                "statusCode": 400,
                "body": json.dumps({
                    "error": "Generated ETL script failed validation",
                    "details": validation_result,
                    "output_location": f"s3://{config['bucket']}/{output_key}"
                })
            }
            
    except Exception as e:
        logger.error(f"An error occurred: {e}")
        return {
            "statusCode": 500,
            "body": json.dumps({
                "error": str(e)
            })
        }

# For local testing
if __name__ == "__main__":
    # Sample event for testing
    test_event = {}
    result = lambda_handler(test_event, None)
    print(json.dumps(result, indent=2))