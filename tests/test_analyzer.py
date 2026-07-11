from unittest.mock import MagicMock
from src.agents.analyzer import AnalyzerAgent
from src.models.state import AgentState, ParsedMetrics, AnalysisResult

def test_analyzer_run():
    metrics = ParsedMetrics(
        total_tickets=10,
        completed_tickets=6,
        in_progress_tickets=2,
        to_do_tickets=2,
        in_review_tickets=0,
        total_story_points=30,
        completed_story_points=18,
        sprint_velocity_percent=60.0,
        bugs_count=3,
        features_count=7,
        average_pr_lead_time_hours=26.5,
        commits_count=15,
        linked_commits_count=12,
        developer_commit_counts={"alex": 10, "dev_b": 5},
        bottlenecks=["Blocker: Ticket MVP-123 is blocked by payment gateway API down time."]
    )
    
    state: AgentState = {
        "raw_github_filepath": "",
        "raw_jira_filepath": "",
        "github_data": None,
        "jira_data": None,
        "metrics": metrics,
        "analysis": None,
        "report": None,
        "validation": None,
        "revision_count": 0,
        "max_revisions": 3,
        "logs": [],
        "errors": []
    }
    
    agent = AnalyzerAgent()
    
    # Mock the LLM call directly for clean unit testing without external APIs
    agent._call_llm = MagicMock(return_value=AnalysisResult(
        executive_summary="The sprint velocity is at 60.0% completion rate.",
        velocity_analysis="Completed 18 out of 30 SP.",
        bottleneck_insights=["PR lead time is 26.5 hours."],
        quality_status="Stable codebase.",
        recommendations=["Refine story estimates."]
    ))
    
    result = agent.run(state)
    
    assert not result.get("errors")
    assert result["analysis"] is not None
    
    analysis = result["analysis"]
    assert "60.0%" in analysis.executive_summary or "60%" in analysis.executive_summary
    assert len(analysis.recommendations) > 0
    assert any("26.5" in b for b in analysis.bottleneck_insights)
