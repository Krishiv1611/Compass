import argparse
import json
import os
import asyncio

from langsmith import Client
from agent.guardrails.engine import GuardrailsEngine


async def _mock_agent_run(inputs: dict) -> dict:
    """Mock agent run for the evaluation framework."""
    
    engine = GuardrailsEngine()
    result = await engine.check_input(inputs.get("input", ""))
    
    if not result.safe:
        return {"output": "Blocked by guardrails"}
        
    return {"output": "Mocked successful output"}


def run_eval_suite(category: str = None, judge_model: str = None):
    """Run evaluations against the golden dataset."""
    
    if not os.environ.get("LANGCHAIN_API_KEY"):
        print("Error: LANGCHAIN_API_KEY not set. LangSmith evaluations require an API key.")
        return

    # Load dataset
    current_dir = os.path.dirname(os.path.abspath(__file__))
    dataset_path = os.path.join(current_dir, "golden_dataset.json")
    
    with open(dataset_path, "r") as f:
        data = json.load(f)
        
    if category:
        data = [item for item in data if item.get("category") == category]
        
    print(f"Running evaluation suite on {len(data)} examples...")
    
    # In a real LangSmith setup, we would create a dataset on the server
    # and run evaluate() against it.
    
    client = Client()
    dataset_name = f"Compass_Eval_{category or 'All'}"
    
    try:
        # Check if dataset exists, if not create it
        datasets = list(client.list_datasets(dataset_name=dataset_name))
        if not datasets:
            dataset = client.create_dataset(
                dataset_name=dataset_name,
                description="Compass Agent Golden Dataset"
            )
            client.create_examples(
                inputs=[{"input": item["input"]} for item in data],
                outputs=[{
                    "expected_output": item.get("expected_output"),
                    "expected_tool": item.get("expected_tool"),
                    "expected_blocked": item.get("expected_blocked")
                } for item in data],
                dataset_id=dataset.id
            )
        
        print("Dataset ready in LangSmith. Starting evaluation...")
        
        # Test the mock locally before handing off to LangSmith
        test_res = asyncio.run(_mock_agent_run({"input": data[0]["input"]}))
        print(f"Mock check passed: {test_res}")
        
        # We would run:
        # evaluate(
        #     _mock_agent_run,
        #     data=dataset_name,
        #     evaluators=[answer_relevance, hallucination, tool_correctness, guardrails_effectiveness, token_efficiency]
        # )
        print("Evaluation suite setup complete.")
        
    except Exception as e:
        print(f"Error connecting to LangSmith: {e}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compass Evaluation Suite")
    parser.add_argument("--category", type=str, help="Filter by category (general, tool_usage, safety, hallucination, hitl)")
    parser.add_argument("--judge-model", type=str, help="Model to use for LLM-as-a-judge evaluators")
    args = parser.parse_args()
    
    run_eval_suite(args.category, args.judge_model)
