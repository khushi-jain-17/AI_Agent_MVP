from pathlib import Path
from langgraph.graph import StateGraph
from src.workflow.graph import app
from src.models.state import AgentState
from src.config import settings

def test_workflow_end_to_end():
    github_path = Path(__file__).parent.parent / "data" / "sample_github_data.json"
    jira_path = Path(__file__).parent.parent / "data" / "sample_jira_data.json"
    
    initial_state: AgentState = {
        "raw_github_filepath": str(github_path),
        "raw_jira_filepath": str(jira_path),
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
    
    # Save original settings and force mock_mode to True
    original_mock = settings.mock_mode
    settings.mock_mode = True
    
    try:
        final_state = app.invoke(initial_state)
        
        # Verify execution and self-correction
        assert not final_state.get("errors")
        assert final_state["github_data"] is not None
        assert final_state["jira_data"] is not None
        assert final_state["metrics"] is not None
        assert final_state["analysis"] is not None
        assert final_state["report"] is not None
        assert final_state["validation"] is not None
        
        # Check self-correction triggered and executed correctly
        # The mock validator fails validation on revision 0 and passes on revision 1,
        # so revision_count should end at exactly 1.
        assert final_state["revision_count"] == 1
        assert final_state["validation"].is_valid is True
        
        # Logs should verify loops
        logs = final_state["logs"]
        assert any("Revision incremented to 1" in log for log in logs)
        assert any("Is Valid: True" in log for log in logs)
        
    finally:
        settings.mock_mode = original_mock
        
def test_workflow_max_revisions():
    github_path = Path(__file__).parent.parent / "data" / "sample_github_data.json"
    jira_path = Path(__file__).parent.parent / "data" / "sample_jira_data.json"
    
    # Mocking validator to always fail validation to test max revisions
    from src.workflow.graph import workflow, parse_data_node, analyze_metrics_node, draft_report_node, increment_revision_node, route_after_validation
    from src.models.state import ValidationResult
    
    def mock_always_invalid_node(state):
        return {
            "validation": ValidationResult(
                is_valid=False,
                errors=["Force failure for testing max limits."],
                suggestions=[]
            ),
            "logs": state.get("logs", []) + ["Injected validation failure."]
        }
        
    # Build a temporary graph to avoid polluting global `app`
    temp_graph = StateGraph(AgentState)
    temp_graph.add_node("parser", parse_data_node)
    temp_graph.add_node("analyzer", analyze_metrics_node)
    temp_graph.add_node("reporter", draft_report_node)
    temp_graph.add_node("validator", mock_always_invalid_node)
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
    
    # Set max revisions to 2 for quick limit check
    initial_state: AgentState = {
        "raw_github_filepath": str(github_path),
        "raw_jira_filepath": str(jira_path),
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
    
    original_mock = settings.mock_mode
    settings.mock_mode = True
    
    try:
        final_state = temp_app.invoke(initial_state)
        # Should stop after reaching max revisions (2) even though it keeps failing
        assert final_state["revision_count"] == 2
        assert final_state["validation"].is_valid is False
    finally:
        settings.mock_mode = original_mock
