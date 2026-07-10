from typing import List, Dict, Any, Optional, TypedDict
from pydantic import BaseModel, Field
from src.models.raw_data import GitHubData, JiraData

class ParsedMetrics(BaseModel):
    total_tickets: int = 0
    completed_tickets: int = 0
    in_progress_tickets: int = 0
    to_do_tickets: int = 0
    in_review_tickets: int = 0
    total_story_points: int = 0
    completed_story_points: int = 0
    sprint_velocity_percent: float = 0.0
    bugs_count: int = 0
    features_count: int = 0
    average_pr_lead_time_hours: float = 0.0
    commits_count: int = 0
    linked_commits_count: int = 0
    developer_commit_counts: Dict[str, int] = Field(default_factory=dict)
    bottlenecks: List[str] = Field(default_factory=list)

class AnalysisResult(BaseModel):
    executive_summary: str = Field(..., description="High-level overview of sprint status and MVP progress.")
    velocity_analysis: str = Field(..., description="Analysis of story points completion, sprint velocity, and estimated release timeline.")
    bottleneck_insights: List[str] = Field(default_factory=list, description="Specific details of what is blocking progress (e.g. PR reviews, unestimated work).")
    quality_status: str = Field(..., description="Assessment of bugs, hotfixes, and overall codebase health.")
    recommendations: List[str] = Field(default_factory=list, description="List of actionable recommendations to speed up delivery or resolve issues.")

class ValidationResult(BaseModel):
    is_valid: bool = Field(..., description="True if the report is accurate and contains no hallucinations or mathematical errors.")
    errors: List[str] = Field(default_factory=list, description="List of direct discrepancies between the raw data/metrics and the report.")
    suggestions: List[str] = Field(default_factory=list, description="Suggestions for formatting, flow, or additional context.")

class AgentState(TypedDict):
    # Inputs
    raw_github_filepath: str
    raw_jira_filepath: str
    
    # Structured representations
    github_data: Optional[GitHubData]
    jira_data: Optional[JiraData]
    
    # Analysis & Reports
    metrics: Optional[ParsedMetrics]
    analysis: Optional[AnalysisResult]
    report: Optional[str]
    
    # Validation loops
    validation: Optional[ValidationResult]
    revision_count: int
    max_revisions: int
    
    # Logging / trace metadata
    logs: List[str]
    errors: List[str]
