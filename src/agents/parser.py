import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional
from datetime import datetime

from src.models.raw_data import GitHubData, JiraData, JiraTicket, Commit, PullRequest, Issue
from src.models.state import AgentState, ParsedMetrics
from src.utils.logger import logger

class DataParserAgent:
    def __init__(self):
        self.name = "Data Parser"

    def run(self, state: AgentState) -> Dict[str, Any]:
        """Loads and structures the JSON raw data from the input file path."""
        logger.info(f"[{self.name}] Starting parsing and validation...")
        logs = list(state.get("logs", []))
        errors = list(state.get("errors", []))
        
        file_path = Path(state["raw_filepath"])
        
        github_data = None
        jira_data = None
        metrics = None
        
        try:
            if not file_path.exists():
                raise FileNotFoundError(f"JSON data file not found at {file_path}")
                
            with open(file_path, "r", encoding="utf-8") as f:
                raw_json = json.load(f)
                
            github_dict = {}
            jira_dict = {}
            
            is_github = False
            is_jira = False
            
            if isinstance(raw_json, dict):
                # 1. Extract GitHub specific fields
                if "commits" in raw_json:
                    github_dict["commits"] = raw_json["commits"]
                    is_github = True
                if "pull_requests" in raw_json:
                    github_dict["pull_requests"] = raw_json["pull_requests"]
                    is_github = True
                    
                # 2. Inspect and route issues list (to avoid key conflicts)
                if "issues" in raw_json:
                    issues_list = raw_json["issues"]
                    if isinstance(issues_list, list) and len(issues_list) > 0:
                        first_item = issues_list[0]
                        if isinstance(first_item, dict):
                            if "key" in first_item:
                                jira_dict["issues"] = issues_list
                                is_jira = True
                            elif "number" in first_item or "labels" in first_item:
                                github_dict["issues"] = issues_list
                                is_github = True
                    else:
                        # Empty list is valid for both schemas
                        github_dict["issues"] = []
                        jira_dict["issues"] = []
                        if "commits" in raw_json or "pull_requests" in raw_json:
                            is_github = True
                        else:
                            is_jira = True
            
            # Load validated models based on classification
            if is_github:
                github_data = GitHubData.model_validate(github_dict)
                logs.append("Successfully identified and parsed GitHub activity data.")
            if is_jira:
                jira_data = JiraData.model_validate(jira_dict)
                logs.append("Successfully identified and parsed Jira tickets data.")
                
            if not is_github and not is_jira:
                raise ValueError("JSON file structure does not match expected GitHub or Jira schemas.")
                
            # Calculate initial metrics
            metrics = self._calculate_metrics(github_data, jira_data)
            logs.append("Computed baseline metrics based on the parsed dataset.")
            
        except Exception as e:
            err_msg = f"Error during data parsing: {str(e)}"
            logger.error(f"[{self.name}] {err_msg}")
            errors.append(err_msg)
            
        return {
            "github_data": github_data,
            "jira_data": jira_data,
            "metrics": metrics,
            "logs": logs,
            "errors": errors
        }

    def _calculate_metrics(self, github: Optional[GitHubData], jira: Optional[JiraData]) -> ParsedMetrics:
        """Calculates exact quantitative metrics from Pydantic data."""
        # Handle Jira ticket status counts
        tickets = []
        if jira:
            tickets = [t for t in jira.issues if t.type.lower() != "epic"]
            
        total_tickets = len(tickets)
        completed = [t for t in tickets if t.status.lower() in ("done", "resolved", "completed")]
        in_progress = [t for t in tickets if t.status.lower() in ("in progress", "active")]
        in_review = [t for t in tickets if t.status.lower() in ("in review", "review", "qa")]
        todo = [t for t in tickets if t.status.lower() in ("to do", "backlog", "todo")]
        
        total_sp = sum(t.story_points for t in tickets)
        completed_sp = sum(t.story_points for t in completed)
        velocity = (completed_sp / total_sp * 100) if total_sp > 0 else 0.0
        
        bugs = sum(1 for t in tickets if t.type.lower() == "bug")
        features = sum(1 for t in tickets if t.type.lower() in ("story", "feature"))
        
        # Handle GitHub Pull Requests Lead Time
        pr_durations_hrs: List[float] = []
        if github:
            for pr in github.pull_requests:
                if pr.state.lower() == "merged" and pr.merged_at and pr.created_at:
                    duration = (pr.merged_at - pr.created_at).total_seconds() / 3600.0
                    pr_durations_hrs.append(duration)
                    
        avg_pr_lead_time = sum(pr_durations_hrs) / len(pr_durations_hrs) if pr_durations_hrs else 0.0
        
        # Handle GitHub commits and linkages
        commits_count = len(github.commits) if github else 0
        linked_commits = 0
        dev_commits: Dict[str, int] = {}
        
        jira_keys = {t.key.lower() for t in jira.issues} if jira else set()
        
        if github:
            for commit in github.commits:
                dev = commit.author
                dev_commits[dev] = dev_commits.get(dev, 0) + 1
                
                # Search for Jira key in commit message
                match = re.search(r"([A-Z]+-\d+)", commit.message)
                if match:
                    key = match.group(1).lower()
                    if key in jira_keys:
                        linked_commits += 1

        # Simple rules to identify bottlenecks
        bottlenecks: List[str] = []
        if jira:
            unassigned_ip = [t for t in in_progress if not t.assignee]
            if unassigned_ip:
                bottlenecks.append(f"{len(unassigned_ip)} ticket(s) in 'In Progress' state have no assignee (e.g. {', '.join(t.key for t in unassigned_ip[:2])}).")
                
            critical_unresolved = [t for t in tickets if t.priority.lower() == "critical" and t.status.lower() != "done"]
            if critical_unresolved:
                bottlenecks.append(f"{len(critical_unresolved)} Critical priority ticket(s) are unresolved (e.g. {', '.join(t.key for t in critical_unresolved[:2])}).")
                
            unestimated_stories = [t for t in tickets if t.type.lower() == "story" and t.story_points == 0]
            if unestimated_stories:
                bottlenecks.append(f"{len(unestimated_stories)} Story ticket(s) are unestimated (0 points) (e.g. {', '.join(t.key for t in unestimated_stories[:2])}).")

        if github:
            noisy_prs = [pr for pr in github.pull_requests if pr.state.lower() == "open" and pr.comments_count > 4]
            if noisy_prs:
                bottlenecks.append(f"PR #{noisy_prs[0].number} has high review discussion ({noisy_prs[0].comments_count} comments) and remains unmerged.")

        return ParsedMetrics(
            total_tickets=total_tickets,
            completed_tickets=len(completed),
            in_progress_tickets=len(in_progress),
            to_do_tickets=len(todo),
            in_review_tickets=len(in_review),
            total_story_points=total_sp,
            completed_story_points=completed_sp,
            sprint_velocity_percent=round(velocity, 2),
            bugs_count=bugs,
            features_count=features,
            average_pr_lead_time_hours=round(avg_pr_lead_time, 1),
            commits_count=commits_count,
            linked_commits_count=linked_commits,
            developer_commit_counts=dev_commits,
            bottlenecks=bottlenecks
        )
