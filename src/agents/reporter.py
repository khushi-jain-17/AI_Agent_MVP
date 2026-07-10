from typing import Dict, Any
from src.agents.base import BaseAgent
from src.models.state import AgentState, ParsedMetrics, AnalysisResult
from src.utils.logger import logger
from src.config import settings

REPORTER_SYSTEM_PROMPT = """You are a Technical Writer and Communications Specialist for engineering teams.
Your goal is to compile structured PM analysis and raw development metrics into a comprehensive, beautifully formatted markdown MVP status report.
Your output must be the raw Markdown text of the report. Use tables, bold headers, and structured bullet lists."""

class ReporterAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Status Reporter", system_prompt=REPORTER_SYSTEM_PROMPT)

    def run(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Drafting status report...")
        logs = list(state.get("logs", []))
        errors = list(state.get("errors", []))
        
        metrics = state["metrics"]
        analysis = state["analysis"]
        
        if not metrics or not analysis:
            err_msg = "Cannot run Reporter without parsed metrics and PM analysis."
            logger.error(f"[{self.name}] {err_msg}")
            errors.append(err_msg)
            return {"errors": errors}

        report_markdown = None
        
        # If live OpenAI client is available, call it
        if self.client and not settings.mock_mode:
            try:
                prompt = self._build_prompt(metrics, analysis)
                report_markdown = self._call_llm_text(prompt)
                logs.append("Drafted comprehensive markdown report via LLM.")
            except Exception as e:
                err_msg = f"LLM report compilation failed: {e}. Falling back to simulation."
                logger.warning(f"[{self.name}] {err_msg}")
                logs.append(err_msg)

        # Fallback simulation mode
        if not report_markdown:
            report_markdown = self._simulate_report(metrics, analysis, state.get("revision_count", 0))
            logs.append("Compiled simulated status report using markdown template.")

        return {
            "report": report_markdown,
            "logs": logs,
            "errors": errors
        }

    def _build_prompt(self, metrics: ParsedMetrics, analysis: AnalysisResult) -> str:
        return f"""Compile a professional, publication-ready Markdown Status Report using the following inputs:

### Executive Analysis:
{analysis.executive_summary}

### Velocity & Estimations:
{analysis.velocity_analysis}

### Quality Metrics:
{analysis.quality_status}

### High-Priority Recommendations:
{chr(10).join("- " + r for r in analysis.recommendations)}

### Quantitative Stats:
- Total Tickets: {metrics.total_tickets}
- Completed: {metrics.completed_tickets} | In Progress: {metrics.in_progress_tickets} | In Review: {metrics.in_review_tickets} | To Do: {metrics.to_do_tickets}
- Story Points: {metrics.completed_story_points} completed of {metrics.total_story_points} total
- Velocity: {metrics.sprint_velocity_percent}%
- Commits: {metrics.commits_count} ({metrics.linked_commits_count} linked)
- Average PR Lead Time: {metrics.average_pr_lead_time_hours} hours

Please format the output report using clean Markdown. Include:
1. Title: MVP Sprint Progress & Velocity Dashboard
2. A Markdown Table presenting all the key metrics.
3. Detailed sections for: Executive Summary, Velocity & Timeline, Quality Assessment.
4. Blockers & Bottlenecks highlighting team struggles (use a blockquote format).
5. Next Steps & Recommendations.
"""

    def _simulate_report(self, metrics: ParsedMetrics, analysis: AnalysisResult, revision_count: int) -> str:
        """Simulates Markdown status report compilation."""
        # Include revision marker to verify validation loop worked in testing/logs
        rev_marker = f"\n*Report Revision: v1.{revision_count} (Self-Corrected)*\n" if revision_count > 0 else ""
        
        # Build developer activity commits string
        dev_table_rows = "\n".join(
            f"| {dev} | {commits} |" for dev, commits in metrics.developer_commit_counts.items()
        )
        
        bottleneck_items = "\n".join(
            f"> - **Blocker**: {b}" for b in analysis.bottleneck_insights
        )
        
        recs_list = "\n".join(
            f"- {r}" for r in analysis.recommendations
        )

        return f"""# MVP Sprint Progress & Velocity Dashboard
{rev_marker}
## 1. Executive Summary
{analysis.executive_summary}

## 2. Key Sprint Metrics

| Metric | Value | Details |
| :--- | :---: | :--- |
| **Total Tickets** | {metrics.total_tickets} | Stories and Bugs in current backlog |
| **Completed Tickets** | {metrics.completed_tickets} | Fully resolved / merged to main |
| **Active/In Progress** | {metrics.in_progress_tickets} | Developer effort currently applied |
| **Pending Review** | {metrics.in_review_tickets} | Open PRs awaiting approvals |
| **Not Started** | {metrics.to_do_tickets} | Tickets in Backlog / To Do |
| **Story Points Completed** | {metrics.completed_story_points} / {metrics.total_story_points} | Point completion velocity |
| **Sprint Completion** | {metrics.sprint_velocity_percent}% | Overall sprint fulfillment percentage |
| **Average PR Lead Time** | {metrics.average_pr_lead_time_hours} hrs | Code integration turnaround cycle |
| **Total Git Commits** | {metrics.commits_count} | Codebase updates in Git |
| **Linked Commits** | {metrics.linked_commits_count} | Commits with explicit Jira keys |

### Developer Activity (Commits)
| Developer | Commits Contributed |
| :--- | :---: |
{dev_table_rows}

## 3. Sprint Velocity & Timeline Analysis
{analysis.velocity_analysis}

## 4. Quality & Codebase Health Assessment
{analysis.quality_status}

## 5. Identified Blockers & Bottlenecks
{bottleneck_items}

## 6. PM Recommendations & Action Items
{recs_list}
"""
