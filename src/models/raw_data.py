from pydantic import BaseModel, Field
from typing import List, Optional, Dict
from datetime import datetime

class Commit(BaseModel):
    sha: str = Field(..., description="Commit SHA hash")
    message: str = Field(..., description="Commit message, usually references a Jira ticket key")
    author: str = Field(..., description="Commit author username")
    date: datetime = Field(..., description="Timestamp of the commit")
    additions: int = Field(0, description="Number of lines added")
    deletions: int = Field(0, description="Number of lines deleted")
    files_changed: List[str] = Field(default_factory=list, description="List of files modified in this commit")

class PullRequest(BaseModel):
    id: int = Field(..., description="Internal PR ID")
    number: int = Field(..., description="GitHub PR number")
    title: str = Field(..., description="PR Title, which might reference a Jira ticket key")
    description: Optional[str] = Field(None, description="Detailed description of changes")
    state: str = Field(..., description="PR state: open, closed, merged")
    creator: str = Field(..., description="GitHub user who created the PR")
    created_at: datetime = Field(..., description="PR creation timestamp")
    closed_at: Optional[datetime] = Field(None, description="PR closing timestamp")
    merged_at: Optional[datetime] = Field(None, description="PR merge timestamp")
    assignee: Optional[str] = Field(None, description="User assigned to the PR")
    reviewers: List[str] = Field(default_factory=list, description="Assigned reviewers")
    comments_count: int = Field(0, description="Total review comments count")

class Issue(BaseModel):
    id: int = Field(..., description="Internal issue ID")
    number: int = Field(..., description="GitHub issue number")
    title: str = Field(..., description="Issue title")
    description: Optional[str] = Field(None, description="Detailed description of issue")
    state: str = Field(..., description="GitHub issue state: open, closed")
    creator: str = Field(..., description="Issue creator username")
    assignees: List[str] = Field(default_factory=list, description="Assigned usernames")
    labels: List[str] = Field(default_factory=list, description="Labels associated with the issue")
    created_at: datetime = Field(..., description="Creation timestamp")
    closed_at: Optional[datetime] = Field(None, description="Resolution timestamp")

class GitHubData(BaseModel):
    commits: List[Commit] = Field(default_factory=list)
    pull_requests: List[PullRequest] = Field(default_factory=list)
    issues: List[Issue] = Field(default_factory=list)

class JiraTicket(BaseModel):
    key: str = Field(..., description="Jira Key, e.g. MVP-101")
    summary: str = Field(..., description="Brief summary of the issue")
    description: Optional[str] = Field(None, description="Detailed ticket description")
    type: str = Field(..., description="Story, Bug, Task, or Epic")
    status: str = Field(..., description="To Do, In Progress, In Review, Done")
    priority: str = Field(..., description="Priority level: Low, Medium, High, Critical")
    assignee: Optional[str] = Field(None, description="Assignee username")
    reporter: str = Field(..., description="Reporter username")
    created_at: datetime = Field(..., description="Ticket creation timestamp")
    updated_at: datetime = Field(..., description="Ticket update timestamp")
    resolution_date: Optional[datetime] = Field(None, description="Ticket resolution timestamp")
    story_points: int = Field(0, description="Estimated story points (0 if unestimated or epic)")

class JiraData(BaseModel):
    issues: List[JiraTicket] = Field(default_factory=list)
