import argparse
import sys
from datetime import datetime
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
        "--input",
        type=str,
        default="data/sample_github_data.json",
        help="Path to the JSON file containing GitHub or Jira dataset to analyze"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Path where the final markdown status report will be written"
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
    
    # Configure API check
    if not settings.openai_api_key:
        console.print("[bold red]Configuration Error:[/bold red] OPENAI_API_KEY is not configured in .env or environment variables.")
        console.print("Please configure a valid API key to run this official pipeline.")
        sys.exit(1)
        
    logger.info("[Main] OPENAI_API_KEY detected. Running live LLM execution.")
    settings.max_revisions = args.max_revisions
    
    console.print(Panel.fit(
        "[bold cyan]AI Agent MVP Tracking Pipeline[/bold cyan]\n"
        "[dim]Multi-Agent Orchestration with self-correction using LangGraph & Pydantic[/dim]",
        border_style="cyan"
    ))
    
    # Dynamic Input Selection
    # If run directly with no command-line arguments, prompt the user interactively
    if len(sys.argv) == 1:
        input_val = ""
        while not input_val:
            input_val = input("Enter a custom path: ").strip()
            if not input_val:
                console.print("[yellow]Path cannot be empty. Please enter a valid JSON file path.[/yellow]")
        
        # Output path selection - automatic without prompting the user
        output_val = f"sample_output/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
    else:
        input_val = args.input
        output_val = args.output if args.output else "sample_output/report.md"
        
    # Verify input path
    file_path = Path(input_val)
    if not file_path.exists():
        console.print(f"[bold red]Error:[/bold red] JSON file not found at [yellow]{file_path.absolute()}[/yellow]")
        sys.exit(1)

    # Initialize agent state
    initial_state: AgentState = {
        "raw_filepath": str(file_path.absolute()),
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
        output_path = Path(output_val)
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
