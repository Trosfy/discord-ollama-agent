# Deployment Reference

This guide covers deploying Strands agents to AWS and production environments.

## Table of Contents
1. [Deployment Options Overview](#deployment-options-overview)
2. [Amazon Bedrock AgentCore](#amazon-bedrock-agentcore)
3. [AWS Lambda](#aws-lambda)
4. [Amazon ECS/Fargate](#amazon-ecsfargate)
5. [Observability](#observability)
6. [Model Providers](#model-providers)

---

## Deployment Options Overview

| Platform | Best For | Long-Running | Serverless | Native Strands Support |
|----------|----------|--------------|------------|------------------------|
| **Bedrock AgentCore** | Production agents | Up to 8 hours | Yes | Built-in |
| **AWS Lambda** | Event-driven, short tasks | Up to 15 min | Yes | Manual |
| **ECS/Fargate** | Long-running, custom infra | Unlimited | Container | Manual |
| **EC2** | Full control, GPU workloads | Unlimited | No | Manual |

---

## Amazon Bedrock AgentCore

Fully managed runtime for production Strands agents with built-in security, observability, and memory.

### Basic Setup

```python
from strands import Agent
from bedrock_agentcore.runtime import BedrockAgentCoreApp

# Initialize agent
agent = Agent(
    system_prompt="You are a helpful assistant.",
    tools=[...]
)

# Wrap with AgentCore
app = BedrockAgentCoreApp()

@app.entrypoint
def invoke(payload):
    """Process incoming requests."""
    user_message = payload.get("prompt", "Hello")
    response = agent(user_message)
    return str(response)  # Must be JSON serializable

if __name__ == "__main__":
    app.run()
```

### With Memory Integration

```python
from datetime import datetime
from strands import Agent
from bedrock_agentcore.memory import MemoryClient
from bedrock_agentcore.memory.integrations.strands.config import (
    AgentCoreMemoryConfig, 
    RetrievalConfig
)
from bedrock_agentcore.memory.integrations.strands.session_manager import (
    AgentCoreMemorySessionManager
)

# Setup memory
client = MemoryClient(region_name="us-east-1")
memory = client.create_memory(
    name="AgentMemory",
    description="Memory for user preferences"
)

# Configure memory integration
memory_config = AgentCoreMemoryConfig(
    memory_id=memory.get('id'),
    session_id=f"session_{datetime.now().strftime('%Y%m%d%H%M%S')}",
    actor_id="user_123"
)

session_manager = AgentCoreMemorySessionManager(
    client=client,
    config=memory_config,
    retrieval_config=RetrievalConfig(include_short_term=True)
)

# Create agent with memory
agent = Agent(
    system_prompt="Use your memory to provide personalized responses.",
    session_manager=session_manager
)
```

### AgentCore Features
- **Identity**: OAuth, Cognito, IAM authentication
- **Memory**: Built-in session and long-term memory
- **Observability**: CloudWatch and OpenTelemetry
- **Tool Interop**: MCP, A2A, API Gateway integration
- **Long-running**: Tasks up to 8 hours
- **Async tools**: Asynchronous tool execution

---

## AWS Lambda

For event-driven, short-duration agent tasks.

### Lambda Handler

```python
# lambda_function.py
from strands import Agent
from strands_tools import calculator

# Initialize agent outside handler for reuse
agent = Agent(
    system_prompt="You are a calculation assistant.",
    tools=[calculator]
)

def lambda_handler(event, context):
    """Lambda entry point."""
    user_input = event.get("body", {}).get("message", "")
    
    try:
        response = agent(user_input)
        return {
            "statusCode": 200,
            "body": {
                "response": str(response),
                "success": True
            }
        }
    except Exception as e:
        return {
            "statusCode": 500,
            "body": {
                "error": str(e),
                "success": False
            }
        }
```

### Lambda Considerations
- **Timeout**: Max 15 minutes—ensure agents complete within limit
- **Cold starts**: Initialize agent outside handler
- **Memory**: Allocate sufficient memory for model calls
- **IAM**: Grant Bedrock permissions if using Bedrock models
- **Layers**: Consider Lambda layers for dependencies

### SAM Template

```yaml
# template.yaml
AWSTemplateFormatVersion: '2010-09-09'
Transform: AWS::Serverless-2016-10-31

Resources:
  AgentFunction:
    Type: AWS::Serverless::Function
    Properties:
      CodeUri: src/
      Handler: lambda_function.lambda_handler
      Runtime: python3.11
      Timeout: 300
      MemorySize: 1024
      Policies:
        - Version: '2012-10-17'
          Statement:
            - Effect: Allow
              Action:
                - bedrock:InvokeModel
                - bedrock:InvokeModelWithResponseStream
              Resource: '*'
```

---

## Amazon ECS/Fargate

For long-running agents or custom infrastructure requirements.

### Dockerfile

```dockerfile
FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application
COPY . .

# Run agent server
EXPOSE 8080
CMD ["python", "server.py"]
```

### FastAPI Server

```python
# server.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from strands import Agent
from strands_tools import calculator, file_read

app = FastAPI()

agent = Agent(
    system_prompt="You are a helpful assistant.",
    tools=[calculator, file_read]
)

class AgentRequest(BaseModel):
    message: str
    session_id: str = None

class AgentResponse(BaseModel):
    response: str
    success: bool

@app.post("/invoke", response_model=AgentResponse)
async def invoke_agent(request: AgentRequest):
    try:
        response = agent(request.message)
        return AgentResponse(response=str(response), success=True)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    return {"status": "healthy"}
```

### ECS Task Definition

```json
{
  "family": "strands-agent",
  "networkMode": "awsvpc",
  "requiresCompatibilities": ["FARGATE"],
  "cpu": "1024",
  "memory": "2048",
  "executionRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskExecutionRole",
  "taskRoleArn": "arn:aws:iam::ACCOUNT:role/ecsTaskRole",
  "containerDefinitions": [
    {
      "name": "agent",
      "image": "ACCOUNT.dkr.ecr.REGION.amazonaws.com/strands-agent:latest",
      "portMappings": [
        {
          "containerPort": 8080,
          "protocol": "tcp"
        }
      ],
      "logConfiguration": {
        "logDriver": "awslogs",
        "options": {
          "awslogs-group": "/ecs/strands-agent",
          "awslogs-region": "us-east-1",
          "awslogs-stream-prefix": "agent"
        }
      }
    }
  ]
}
```

---

## Observability

### OpenTelemetry Integration

```python
from strands import Agent
from strands.telemetry import setup_otel

# Configure OpenTelemetry
setup_otel(
    service_name="my-strands-agent",
    otlp_endpoint="http://localhost:4317"  # Collector endpoint
)

agent = Agent(tools=[...])
# All agent operations now emit traces
```

### CloudWatch Logging

```python
import logging
from strands import Agent

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("strands")

# Enable Strands debug logging
logging.getLogger("strands").setLevel(logging.DEBUG)
logging.getLogger("strands.multiagent").setLevel(logging.DEBUG)

agent = Agent(tools=[...])
```

### Tracing Agent Loops

```python
# Stream events to observe agent decision-making
async for event in agent.stream_async("Process this request"):
    if event.get("type") == "tool_call":
        print(f"Tool: {event['tool_name']}")
    elif event.get("type") == "thinking":
        print(f"Thinking: {event['content'][:100]}...")
```

---

## Model Providers

### Amazon Bedrock (Default)

```python
from strands import Agent
from strands.models.bedrock import BedrockModel

# Default configuration
agent = Agent()  # Uses Claude on Bedrock

# Explicit configuration
agent = Agent(
    model=BedrockModel(
        model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
        region_name="us-east-1"
    )
)
```

### Anthropic Direct

```python
from strands.models.anthropic import AnthropicModel

agent = Agent(
    model=AnthropicModel(
        model_id="claude-sonnet-4-20250514",
        client_args={"api_key": "your-api-key"}
    )
)
```

### OpenAI

```python
from strands.models.openai import OpenAIModel

agent = Agent(
    model=OpenAIModel(
        model_id="gpt-4o",
        client_args={"api_key": "your-api-key"}
    )
)
```

### Ollama (Local)

```python
from strands.models.ollama import OllamaModel

agent = Agent(
    model=OllamaModel(
        model_id="llama3.1",
        host="http://localhost:11434"
    )
)
```

### LiteLLM (Multiple Providers)

```python
from strands.models.litellm import LiteLLMModel

agent = Agent(
    model=LiteLLMModel(
        model_id="gpt-4o",  # or any LiteLLM supported model
    )
)
```

### Model Configuration

```python
from strands.models.bedrock import BedrockModel

model = BedrockModel(
    model_id="us.anthropic.claude-sonnet-4-20250514-v1:0",
    region_name="us-east-1",
    params={
        "temperature": 0.7,
        "max_tokens": 4096,
        "top_p": 0.9
    }
)

agent = Agent(model=model)
```
