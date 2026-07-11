from typing import Dict, Any
from langgraph.graph import StateGraph, START, END

from src.models.state import AgentState
from src.agents.parser import DataParserAgent
from src.agents.analyzer import AnalyzerAgent
from src.agents.reporter import ReporterAgent
from src.agents.validator import ValidatorAgent
from src.utils.logger import logger

# Initialize agents
parser_agent = DataParserAgent()
analyzer_agent = AnalyzerAgent()
reporter_agent = ReporterAgent()
validator_agent = ValidatorAgent()

# Define node wrappers to match graph signature
def parse_data_node(state: AgentState) -> Dict[str, Any]:
    return parser_agent.run(state)

def analyze_metrics_node(state: AgentState) -> Dict[str, Any]:
    return analyzer_agent.run(state)

def draft_report_node(state: AgentState) -> Dict[str, Any]:
    return reporter_agent.run(state)

def validate_report_node(state: AgentState) -> Dict[str, Any]:
    return validator_agent.run(state)

def increment_revision_node(state: AgentState) -> Dict[str, Any]:
    current_revisions = state.get("revision_count", 0)
    logs = list(state.get("logs", []))
    logs.append(f"Validation failed. Routing back to Reporter. Revision incremented to {current_revisions + 1}.")
    logger.info(f"[Workflow] Incrementing revision count: {current_revisions} -> {current_revisions + 1}")
    return {
        "revision_count": current_revisions + 1,
        "logs": logs
    }

# Conditional routing logic
def route_after_validation(state: AgentState) -> str:
    validation = state.get("validation")
    revision_count = state.get("revision_count", 0)
    max_revisions = state.get("max_revisions", 3)
    
    if not validation:
        logger.warning("[Workflow] No validation result found. Ending workflow.")
        return END
        
    if validation.is_valid:
        logger.info("[Workflow] Report passed QA validation! Ending workflow.")
        return END
        
    if revision_count >= max_revisions:
        logger.warning(f"[Workflow] Max revision cycles ({max_revisions}) reached. Forcing completion.")
        return END
        
    logger.info(f"[Workflow] Report failed validation with {len(validation.errors)} error(s). Routing to self-correction.")
    return "increment_revision"

# StateGraph
workflow = StateGraph(AgentState)

# Nodes
workflow.add_node("parser", parse_data_node)
workflow.add_node("analyzer", analyze_metrics_node)
workflow.add_node("reporter", draft_report_node)
workflow.add_node("validator", validate_report_node)
workflow.add_node("increment_revision", increment_revision_node)

# Edges
workflow.add_edge(START, "parser")
workflow.add_edge("parser", "analyzer")
workflow.add_edge("analyzer", "reporter")
workflow.add_edge("reporter", "validator")

# Conditional Edge for self-correction loop
workflow.add_conditional_edges(
    "validator",
    route_after_validation,
    {
        "increment_revision": "increment_revision",
        END: END
    }
)

# Edge from revision increments back to reporter node
workflow.add_edge("increment_revision", "reporter")

# Compile Graph
app = workflow.compile()
