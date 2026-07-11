import json
from pathlib import Path
from src.models.state import AgentState
from src.agents.parser import DataParserAgent

def test_data_parser_github():
    github_path = Path(__file__).parent.parent / "data" / "sample_github_data.json"
    
    state: AgentState = {
        "raw_filepath": str(github_path),
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
    
    agent = DataParserAgent()
    result = agent.run(state)
    
    assert not result.get("errors")
    assert result["github_data"] is not None
    assert result["jira_data"] is None
    assert result["metrics"] is not None
    
    metrics = result["metrics"]
    assert metrics.commits_count == 8
    assert len(metrics.developer_commit_counts) == 3

def test_data_parser_jira():
    jira_path = Path(__file__).parent.parent / "data" / "sample_jira_data.json"
    
    state: AgentState = {
        "raw_filepath": str(jira_path),
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
    
    agent = DataParserAgent()
    result = agent.run(state)
    
    assert not result.get("errors")
    assert result["github_data"] is None
    assert result["jira_data"] is not None
    assert result["metrics"] is not None
    
    metrics = result["metrics"]
    assert metrics.total_tickets == 6
    assert metrics.completed_tickets == 3
    assert metrics.sprint_velocity_percent == 42.31
    assert len(metrics.bottlenecks) == 0
