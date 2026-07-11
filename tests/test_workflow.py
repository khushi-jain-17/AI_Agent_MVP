import json
import tempfile
from pathlib import Path
from unittest.mock import patch, MagicMock
from langgraph.graph import StateGraph

from src.workflow.graph import app
from src.models.state import AgentState, AnalysisResult, ValidationResult
from src.config import settings

@patch("src.agents.base.BaseAgent._call_llm")
@patch("src.agents.base.BaseAgent._call_llm_text")
def test_workflow_end_to_end(mock_call_llm_text, mock_call_llm):
    github_path = Path(__file__).parent.parent / "data" / "sample_github_data.json"
    jira_path = Path(__file__).parent.parent / "data" / "sample_jira_data.json"
    
    # Merge datasets to test combined dynamic parsing
    with open(github_path, "r", encoding="utf-8") as f:
        gh = json.load(f)
    with open(jira_path, "r", encoding="utf-8") as f:
        jr = json.load(f)
    
    combined = {**gh, **jr}
    
    # Use context manager to handle temporary file safely
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        json.dump(combined, tmp)
        tmp_path = tmp.name
        
    initial_state: AgentState = {
        "raw_filepath": tmp_path,
        "github_data": None,
        "jira_data": None,
        "metrics": None,
        "analysis": None,
        "report": None,
        "validation": None,
        "revision_count": 0,
        "max_revisions": 3,
        "logs": [],
        "errors": []
    }
    
    # Configure mock behaviors to simulate LLM endpoints offline
    mock_call_llm_text.return_value = "# Mock Markdown Status Report"
    
    mock_call_llm.side_effect = [
        AnalysisResult(
            executive_summary="The sprint completion rate is 42.31%.",
            velocity_analysis="Completed 11 out of 26 SP.",
            bottleneck_insights=["PR lead time is 30.2 hours."],
            quality_status="Codebase is stable.",
            recommendations=["Add estimates."]
        ),
        ValidationResult(
            is_valid=False,
            errors=["Mock validation failure to trigger correction loop."],
            suggestions=["Please fix stats."]
        ),
        ValidationResult(
            is_valid=True,
            errors=[],
            suggestions=[]
        )
    ]
    
    # Temporarily set API key settings to pass initialization checks if run offline
    original_key = settings.openai_api_key
    settings.openai_api_key = "mock-key-for-testing"
    
    try:
        final_state = app.invoke(initial_state)
        
        # Verify execution and self-correction
        assert not final_state.get("errors")
        assert final_state["github_data"] is not None
        assert final_state["jira_data"] is not None
        assert final_state["metrics"] is not None
        assert final_state["analysis"] is not None
        assert final_state["report"] == "# Mock Markdown Status Report"
        assert final_state["validation"] is not None
        
        # Verify correction loop ran exactly once
        assert final_state["revision_count"] == 1
        assert final_state["validation"].is_valid is True
        
    finally:
        settings.openai_api_key = original_key
        # Clean up temporary file
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
        
@patch("src.agents.base.BaseAgent._call_llm")
@patch("src.agents.base.BaseAgent._call_llm_text")
def test_workflow_max_revisions(mock_call_llm_text, mock_call_llm):
    github_path = Path(__file__).parent.parent / "data" / "sample_github_data.json"
    jira_path = Path(__file__).parent.parent / "data" / "sample_jira_data.json"
    
    with open(github_path, "r", encoding="utf-8") as f:
        gh = json.load(f)
    with open(jira_path, "r", encoding="utf-8") as f:
        jr = json.load(f)
    
    combined = {**gh, **jr}
    with tempfile.NamedTemporaryFile("w", delete=False, suffix=".json", encoding="utf-8") as tmp:
        json.dump(combined, tmp)
        tmp_path = tmp.name
        
    from src.workflow.graph import parse_data_node, analyze_metrics_node, draft_report_node, increment_revision_node, route_after_validation
    
    # Stub nodes and build a temporary graph to evaluate max revision thresholds
    temp_graph = StateGraph(AgentState)
    temp_graph.add_node("parser", parse_data_node)
    temp_graph.add_node("analyzer", analyze_metrics_node)
    temp_graph.add_node("reporter", draft_report_node)
    temp_graph.add_node("validator", lambda state: {
        "validation": ValidationResult(
            is_valid=False,
            errors=["Force failure to trigger max loops."],
            suggestions=[]
        ),
        "logs": state.get("logs", []) + ["Injected validation failure."]
    })
    temp_graph.add_node("increment_revision", increment_revision_node)
    
    temp_graph.add_edge("parser", "analyzer")
    temp_graph.add_edge("analyzer", "reporter")
    temp_graph.add_edge("reporter", "validator")
    temp_graph.add_conditional_edges(
        "validator",
        route_after_validation,
        {
            "increment_revision": "increment_revision",
            "__end__": "__end__"
        }
    )
    temp_graph.add_edge("increment_revision", "reporter")
    temp_graph.set_entry_point("parser")
    
    temp_app = temp_graph.compile()
    
    # Configure stubs
    mock_call_llm_text.return_value = "# Mock Markdown Status Report"
    mock_call_llm.return_value = AnalysisResult(
        executive_summary="Executive summary stats.",
        velocity_analysis="Velocity stats.",
        bottleneck_insights=[],
        quality_status="Quality stats.",
        recommendations=[]
    )
    
    initial_state: AgentState = {
        "raw_filepath": tmp_path,
        "github_data": None,
        "jira_data": None,
        "metrics": None,
        "analysis": None,
        "report": None,
        "validation": None,
        "revision_count": 0,
        "max_revisions": 2,
        "logs": [],
        "errors": []
    }
    
    original_key = settings.openai_api_key
    settings.openai_api_key = "mock-key-for-testing"
    
    try:
        final_state = temp_app.invoke(initial_state)
        # Should stop after reaching max revisions (2)
        assert final_state["revision_count"] == 2
        assert final_state["validation"].is_valid is False
    finally:
        settings.openai_api_key = original_key
        try:
            Path(tmp_path).unlink()
        except OSError:
            pass
