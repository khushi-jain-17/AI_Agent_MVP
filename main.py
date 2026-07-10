import argparse
import sys
from pathlib import Path
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

# Add src to python path to ensure imports work correctly when run from workspace root
sys.path.append(str(Path(__file__).resolve().parent))

from src.config import settings
from src.utils.logger import logger
from src.workflow.graph import app
from src.models.state import AgentState

console = Console()

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="AI Agent MVP Tracker - Multi-Agent Dev Status pipeline using LangGraph."
    )
    parser.add_argument(
        "--github",
        type=str,
        default="data/sample_github_data.json",
        help="Path to the JSON file containing GitHub event data"
    )
    parser.add_argument(
        "--jira",
        type=str,
        default="data/sample_jira_data.json",
        help="Path to the JSON file containing Jira tickets data"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="sample_output/report.md",
        help="Path where the final markdown status report will be written"
    )
    parser.add_argument(
        "--mock",
        action="store_true",
        help="Force execution in simulation mode (bypasses live OpenAI API calls)"
    )
    parser.add_argument(
        "--max-revisions",
        type=int,
        default=3,
        help="Maximum self-correction cycles the validation agent can trigger"
    )
    return parser.parse_args()

def main():
    args = parse_args()
    
    # Configure mock mode
    if args.mock:
        settings.mock_mode = True
        logger.info("[Main] Forcing simulation mock mode via CLI flag.")
    elif not settings.openai_api_key:
        settings.mock_mode = True
        logger.info("[Main] OPENAI_API_KEY not found in environment. Automatically falling back to simulation mock mode.")
    else:
        settings.mock_mode = False
        logger.info("[Main] OPENAI_API_KEY detected. Running live LLM execution.")
        
    settings.max_revisions = args.max_revisions
    
    console.print(Panel.fit(
        "[bold cyan]AI Agent MVP Tracking Pipeline[/bold cyan]\n"
        "[dim]Multi-Agent Orchestration with self-correction using LangGraph & Pydantic[/dim]",
        border_style="cyan"
    ))
    
    # Verify input paths
    github_path = Path(args.github)
    jira_path = Path(args.jira)
    
    if not github_path.exists():
        console.print(f"[bold red]Error:[/bold red] GitHub file not found at [yellow]{github_path.absolute()}[/yellow]")
        sys.exit(1)
    if not jira_path.exists():
        console.print(f"[bold red]Error:[/bold red] Jira file not found at [yellow]{jira_path.absolute()}[/yellow]")
        sys.exit(1)

    # Initialize agent state
    initial_state: AgentState = {
        "raw_github_filepath": str(github_path.absolute()),
        "raw_jira_filepath": str(jira_path.absolute()),
        "github_data": None,
        "jira_data": None,
        "metrics": None,
        "analysis": None,
        "report": None,
        "validation": None,
        "revision_count": 0,
        "max_revisions": settings.max_revisions,
        "logs": [],
        "errors": []
    }
    
    logger.info("[Workflow] Starting pipeline execution...")
    
    # Run the LangGraph application
    try:
        final_state = app.invoke(initial_state)
    except Exception as e:
        logger.critical(f"[Workflow] Graph execution crashed: {e}")
        console.print(f"[bold red]Workflow Failed:[/bold red] {e}")
        sys.exit(1)
        
    # Check for execution errors in state
    if final_state.get("errors"):
        console.print("[bold red]Pipeline completed with errors:[/bold red]")
        for err in final_state["errors"]:
            console.print(f"- [red]{err}[/red]")
        sys.exit(1)
        
    # Log details and output metrics
    metrics = final_state.get("metrics")
    if metrics:
        console.print("\n[bold green]Compiled Sprint Metrics:[/bold green]")
        table = Table(show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")
        
        table.add_row("Total Tickets (Stories/Bugs)", str(metrics.total_tickets))
        table.add_row("Completed Tickets", str(metrics.completed_tickets))
        table.add_row("In Progress Tickets", str(metrics.in_progress_tickets))
        table.add_row("In Review / PR", str(metrics.in_review_tickets))
        table.add_row("Total Story Points", f"{metrics.completed_story_points} / {metrics.total_story_points}")
        table.add_row("Sprint Velocity", f"{metrics.sprint_velocity_percent}%")
        table.add_row("GitHub Commits Count", str(metrics.commits_count))
        table.add_row("Avg PR Lead Time (Hours)", str(metrics.average_pr_lead_time_hours))
        
        console.print(table)
        
    # Save Report
    report = final_state.get("report")
    if report:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        try:
            with open(output_path, "w", encoding="utf-8") as f:
                f.write(report)
            console.print(
                f"\n[bold green]SUCCESS:[/bold green] Status report written to "
                f"[yellow]{output_path.absolute()}[/yellow]"
            )
        except Exception as e:
            logger.error(f"[Main] Failed to write report: {e}")
            console.print(f"[bold red]Error saving report:[/bold red] {e}")
            sys.exit(1)
            
    # Print Workflow execution log
    console.print("\n[bold cyan]Workflow Trace Logs:[/bold cyan]")
    for log in final_state.get("logs", []):
        console.print(f"[dim]•[/dim] {log}")
        
    console.print("\n[bold green]Pipeline finished successfully![/bold green]")

if __name__ == "__main__":
    main()
