from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.models.findings import AgentOutput, SpecialistResult


class AgentState(TypedDict):
    diff: str
    collection_name: str
    owner: str
    repo_name: str
    bug_output: AgentOutput | None
    security_output: AgentOutput | None
    pattern_output: AgentOutput | None


def collect_results(state: AgentState) -> dict:
    return {
        "bug_output":      state["bug_output"],
        "security_output": state["security_output"],
        "pattern_output":  state["pattern_output"],
    }


def build_graph(
    run_bug_agent,
    run_security_agent,
    run_pattern_agent,
) -> object:
    graph = StateGraph(AgentState)

    graph.add_node("bug",      run_bug_agent)
    graph.add_node("security", run_security_agent)
    graph.add_node("pattern",  run_pattern_agent)
    graph.add_node("collect",  collect_results)

    graph.set_entry_point("bug")
    graph.add_edge("__start__", "bug")
    graph.add_edge("__start__", "security")
    graph.add_edge("__start__", "pattern")

    graph.add_edge("bug",      "collect")
    graph.add_edge("security", "collect")
    graph.add_edge("pattern",  "collect")

    graph.add_edge("collect", END)

    return graph.compile()
