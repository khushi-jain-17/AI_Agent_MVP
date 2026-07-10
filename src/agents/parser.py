import json
import re
from pathlib import Path
from typing import Dict, Any, List
from datetime import datetime

from src.models.raw_data import GitHubData, JiraData, JiraTicket, Commit, PullRequest, Issue
from src.models.state import AgentState, ParsedMetrics
from src.utils.logger import logger

class DataParserAgent:
    def __init__(self):
        self.name = "Data Parser"

    def run(self, state: AgentState) -> Dict[str, Any]:
        """Loads and structures the JSON raw data from files, calculating initial metrics."""
        logger.info(f"[{self.name}] Starting parsing and validation...")
        logs = list(state.get("logs", []))
        errors = list(state.get("errors", []))
        
        github_path = Path(state["raw_github_filepath"])
        jira_path = Path(state["raw_jira_filepath"])
        
        github_data = None
        jira_data = None
        metrics = None
        
        try:
            # Parse GitHub file
            if not github_path.exists():
                raise FileNotFoundError(f"GitHub data file not found at {github_path}")
            
            with open(github_path, "r", encoding="utf-8") as f:
                github_raw = json.load(f)
                github_data = GitHubData.model_validate(github_raw)
            
            # Parse Jira file
            if not jira_path.exists():
                raise FileNotFoundError(f"Jira data file not found at {jira_path}")
                
            with open(jira_path, "r", encoding="utf-8") as f:
                jira_raw = json.load(f)
                jira_data = JiraData.model_validate(jira_raw)
                
            logs.append("Successfully loaded and validated raw JSON data with Pydantic.")
            
            # Calculate initial metrics
            metrics = self._calculate_metrics(github_data, jira_data)
            logs.append("Computed baseline developer metrics and identified core bottlenecks.")
            
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

    def _calculate_metrics(self, github: GitHubData, jira: JiraData) -> ParsedMetrics:
        """Calculates exact quantitative metrics from Pydantic data."""
        # Ticket status counts
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
        
        # PR Lead Time
        pr_durations_hrs: List[float] = []
        for pr in github.pull_requests:
            if pr.state.lower() == "merged" and pr.merged_at and pr.created_at:
                duration = (pr.merged_at - pr.created_at).total_seconds() / 3600.0
                pr_durations_hrs.append(duration)
                
        avg_pr_lead_time = sum(pr_durations_hrs) / len(pr_durations_hrs) if pr_durations_hrs else 0.0
        
        # Link commits to Jira tickets
        commits_count = len(github.commits)
        linked_commits = 0
        dev_commits: Dict[str, int] = {}
        
        jira_keys = {t.key.lower() for t in jira.issues}
        
        for commit in github.commits:
            dev = commit.author
            dev_commits[dev] = dev_commits.get(dev, 0) + 1
            
            # search for Jira key in commit message
            match = re.search(r"([A-Z]+-\d+)", commit.message)
            if match:
                key = match.group(1).lower()
                if key in jira_keys:
                    linked_commits += 1

        # Simple rules to identify bottlenecks
        bottlenecks: List[str] = []
        
        # 1. Unassigned tickets in progress
        unassigned_ip = [t for t in in_progress if not t.assignee]
        if unassigned_ip:
            bottlenecks.append(f"{len(unassigned_ip)} ticket(s) in 'In Progress' state have no assignee (e.g. {', '.join(t.key for t in unassigned_ip[:2])}).")
            
        # 2. Critical priority issues not resolved
        critical_unresolved = [t for t in tickets if t.priority.lower() == "critical" and t.status.lower() != "done"]
        if critical_unresolved:
            bottlenecks.append(f"{len(critical_unresolved)} Critical priority ticket(s) are unresolved (e.g. {', '.join(t.key for t in critical_unresolved[:2])}).")
            
        # 3. Unestimated stories (excluding bugs which might not need points, though stories should)
        unestimated_stories = [t for t in tickets if t.type.lower() == "story" and t.story_points == 0]
        if unestimated_stories:
            bottlenecks.append(f"{len(unestimated_stories)} Story ticket(s) are unestimated (0 points) (e.g. {', '.join(t.key for t in unestimated_stories[:2])}).")

        # 4. Long review PR cycles (PR open but not merged, or PR comments > 4)
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
