from typing import Dict, Any
from src.agents.base import BaseAgent
from src.models.state import AgentState, ValidationResult, ParsedMetrics
from src.utils.logger import logger

VALIDATOR_SYSTEM_PROMPT = """You are an elite Quality Assurance and Verification Agent.
Your role is to cross-examine the drafted Markdown report against the quantitative ParsedMetrics and raw data.
You must flag any mathematical inconsistencies, missed blockers, incorrect counts, or formatting errors.
You must return your output strictly matched to the ValidationResult schema."""

class ValidatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="Quality Validator", system_prompt=VALIDATOR_SYSTEM_PROMPT)

    def run(self, state: AgentState) -> Dict[str, Any]:
        logger.info(f"[{self.name}] Validating report accuracy...")
        logs = list(state.get("logs", []))
        errors = list(state.get("errors", []))
        
        metrics = state["metrics"]
        report = state["report"]
        
        if not metrics or not report:
            err_msg = "Cannot run Validator without parsed metrics and a draft report."
            logger.error(f"[{self.name}] {err_msg}")
            errors.append(err_msg)
            return {"errors": errors}

        try:
            prompt = self._build_prompt(metrics, report)
            validation_result = self._call_llm(prompt, ValidationResult)
            logs.append(f"Validation completed. Is Valid: {validation_result.is_valid}.")
        except Exception as e:
            err_msg = f"LLM validation failed: {e}"
            logger.error(f"[{self.name}] {err_msg}")
            errors.append(err_msg)
            return {"errors": errors, "logs": logs}

        return {
            "validation": validation_result,
            "logs": logs,
            "errors": errors
        }

    def _build_prompt(self, metrics: ParsedMetrics, report: str) -> str:
        return f"""Cross-verify the following report content against the source metrics:

### Source Metrics:
- Total Tickets: {metrics.total_tickets}
- Completed Tickets: {metrics.completed_tickets}
- In Progress: {metrics.in_progress_tickets}
- In Review: {metrics.in_review_tickets}
- To Do: {metrics.to_do_tickets}
- Story Points: {metrics.completed_story_points} completed of {metrics.total_story_points}
- Velocity: {metrics.sprint_velocity_percent}%
- Commits: {metrics.commits_count} ({metrics.linked_commits_count} linked)
- Average PR Lead Time: {metrics.average_pr_lead_time_hours} hours

### Draft Report:
\"\"\"
{report}
\"\"\"

Please evaluate if the numbers, counts, and issues mentioned in the report are accurate and consistent with the metrics.
Generate a ValidationResult:
- Set is_valid to true if all figures are correct.
- If there are discrepancies (e.g. wrong counts, mismatched percentages, ignored critical blockers), list them in errors and set is_valid to false.
"""
