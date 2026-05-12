from app.models.findings import SpecialistResult, AgentOutput
from .graph import AgentState, build_graph


async def run_specialist_agents(
    diff: str,
    collection_name: str,
    owner: str,
    repo_name: str,
) -> SpecialistResult:
    from .bug.agent import run_bug_agent
    from .security.agent import run_security_agent
    from .pattern.agent import run_pattern_agent

    graph = build_graph(run_bug_agent, run_security_agent, run_pattern_agent)

    initial_state: AgentState = {
        "diff": diff,
        "collection_name": collection_name,
        "owner": owner,
        "repo_name": repo_name,
        "bug_output": None,
        "security_output": None,
        "pattern_output": None,
    }

    final_state = await graph.ainvoke(initial_state)

    return SpecialistResult(
        bug=final_state["bug_output"] or AgentOutput(agent="bug", findings=[]),
        security=final_state["security_output"] or AgentOutput(agent="security", findings=[]),
        pattern=final_state["pattern_output"] or AgentOutput(agent="pattern", findings=[]),
    )
