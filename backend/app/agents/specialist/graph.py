from typing import TypedDict
from langgraph.graph import StateGraph, END
from app.models.findings import AgentOutput


class AgentState(TypedDict):
    diff: str
    collection_name: str
    owner: str
    repo_name: str
    bug_output: AgentOutput | None
    security_output: AgentOutput | None
    pattern_output: AgentOutput | None


def build_graph(
    run_bug_agent,
    run_security_agent,
    run_pattern_agent,
) -> object:
    graph = StateGraph(AgentState)

    graph.add_node("bug",      run_bug_agent)
    graph.add_node("security", run_security_agent)
    graph.add_node("pattern",  run_pattern_agent)

    graph.add_edge("__start__", "bug")
    graph.add_edge("__start__", "security")
    graph.add_edge("__start__", "pattern")

    graph.add_edge("bug",      END)
    graph.add_edge("security", END)
    graph.add_edge("pattern",  END)

    return graph.compile()
