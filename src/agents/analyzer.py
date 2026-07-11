from typing import Dict, Any
from src.agents.base import BaseAgent
from src.models.state import AgentState, AnalysisResult, ParsedMetrics
from src.utils.logger import logger

ANALYZER_SYSTEM_PROMPT = """You are an elite Senior technical Product Manager and Scrum Master.
Your goal is to inspect sprint metrics, GitHub development logs, and Jira tickets for an MVP project, and write a high-level technical analysis.
Focus on actual productivity, developer velocity, process blockers, code quality, and delivery risk.
You must return your output strictly matched to the AnalysisResult schema."""

class AnalyzerAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Metrics Analyzer", system_prompt=ANALYZER_SYSTEM_PROMPT)

    def run(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Analyzing development metrics...")
        logs = list(state.get("logs", []))
        errors = list(state.get("errors", []))
        
        metrics = state["metrics"]
        if not metrics:
            err_msg = "Cannot run Analyzer without parsed metrics."
            logger.error(f"[{self.name}] {err_msg}")
            errors.append(err_msg)
            return {"errors": errors}

        try:
            prompt = self._build_prompt(metrics, state)
            analysis_result = self._call_llm(prompt, AnalysisResult)
            logs.append("Generated multi-dimensional LLM project velocity analysis.")
        except Exception as e:
            err_msg = f"LLM analysis failed: {e}"
            logger.error(f"[{self.name}] {err_msg}")
            errors.append(err_msg)
            return {"errors": errors, "logs": logs}

        return {
            "analysis": analysis_result,
            "logs": logs,
            "errors": errors
        }

    def _build_prompt(self, metrics: ParsedMetrics, state: AgentState) -> str:
        # Build prompt using metrics & details of Jira tickets / GitHub
        jira_summary = ""
        if state["jira_data"]:
            jira_summary = "\n".join(
                f"- [{t.key}] {t.summary} ({t.type}) - Status: {t.status}, Points: {t.story_points}, Assignee: {t.assignee}"
                for t in state["jira_data"].issues
            )
            
        github_summary = ""
        if state["github_data"]:
            github_summary += "\nPRs:\n"
            github_summary += "\n".join(
                f"- PR #{p.number}: {p.title} (State: {p.state}) - Creator: {p.creator}, Comments: {p.comments_count}"
                for p in state["github_data"].pull_requests
            )
            
        return f"""Please analyze the following sprint metrics and status details:

### Quantitative Metrics:
- Total Tickets (excluding Epics): {metrics.total_tickets}
- Completed: {metrics.completed_tickets}, In Progress: {metrics.in_progress_tickets}, In Review: {metrics.in_review_tickets}, To Do: {metrics.to_do_tickets}
- Story Points: Completed {metrics.completed_story_points} SP out of {metrics.total_story_points} total SP.
- Current Velocity: {metrics.sprint_velocity_percent}%
- Bugs Count: {metrics.bugs_count}, Feature Stories: {metrics.features_count}
- Avg PR Lead Time: {metrics.average_pr_lead_time_hours} hours
- Git Commits: {metrics.commits_count} total commits, with {metrics.linked_commits_count} successfully referencing Jira keys.
- Developer Commits: {metrics.developer_commit_counts}

### Core Blockers / Bottlenecks Identified:
{chr(10).join("- " + b for b in metrics.bottlenecks)}

### Active Jira Tickets:
{jira_summary}

### Git Activity Summary:
{github_summary}

Please generate an AnalysisResult containing:
1. Executive summary of MVP progress.
2. Development velocity analysis & timeline risk.
3. High-priority bottleneck details.
4. Codebase/sprint quality assessment.
5. Actionable PM recommendations.
"""
