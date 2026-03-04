import streamlit as st
import os
import sys
from urllib.parse import urlparse

# Ensure project root is in path
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
from app.graph.builder import get_compiled_graph

load_dotenv()


def _is_safe_url(url: str) -> bool:
    """Reject non-http(s) URLs and private/loopback addresses (SSRF guard)."""
    try:
        parsed = urlparse(url)
        if parsed.scheme not in ("http", "https", ""):
            return False
        host = parsed.hostname or ""
        # Block localhost and common private ranges
        if host in ("localhost", "127.0.0.1", "0.0.0.0", "::1", ""):
            return False
        if host.startswith("10.") or host.startswith("192.168.") or host.startswith("172."):
            return False
        return True
    except Exception:
        return False

st.set_page_config(
    page_title="Autonomous Research Agent",
    page_icon="🤖",
    layout="wide"
)

st.title("🤖 Autonomous Research + Report Agent")
st.markdown("""
This multi-agent system uses LangGraph to plan, execute parallel tool-routed retrieval, synthesize citations, and cyclically refine the report until a high quality bar is met.
""")

query = st.text_input("Enter your research query:", placeholder="e.g., What are the latest advancements in Quantum Computing?")

if st.button("Start Research"):
    if not query.strip():
        st.warning("Please enter a query.")
    else:
        st.write("---")
        st.subheader("Observability Trace")
        
        # UI Elements for progress
        progress_container = st.container()
        
        # L-06 / H-04: Store execution state in st.session_state so it
        #   survives Streamlit script reruns triggered by user interactions
        #   mid-stream.  get_compiled_graph() initialises the graph lazily.
        st.session_state["current_state"] = {
            "query": query,
            "plan": [],
            "current_step": 0,
            "documents": [],
            "draft": "",
            "critique": {},
            "score": 0.0,
            "iteration": 0,
            "history": [f"Streamlit UI Triggered Query: {query}"],
            "metadata": {},
        }
        current_state = st.session_state["current_state"]

        with progress_container:
            status_text = st.empty()
            
            try:
                # Stream execution
                for output in get_compiled_graph().stream(current_state):
                    for node_name, state_update in output.items():
                        # Update local state tracking
                        if "draft" in state_update:
                            current_state["draft"] = state_update["draft"]
                        if "score" in state_update:
                            current_state["score"] = state_update["score"]
                        if "critique" in state_update:
                            current_state["critique"] = state_update["critique"]
                        if "iteration" in state_update:
                            current_state["iteration"] = state_update["iteration"]
                        if "plan" in state_update:
                            current_state["plan"] = state_update["plan"]
                        if "documents" in state_update:
                            current_state["documents"].extend(state_update["documents"])
                        if "history" in state_update:
                            current_state["history"].extend(state_update["history"])
                        
                        st.markdown(f"**🟢 Node executed:** `{node_name}`")
                        
                        if "history" in state_update and state_update["history"]:
                            latest_event = state_update["history"][-1]
                            st.info(f"Trace: {latest_event}")
                            
                        if node_name == "planner":
                            with st.expander("Sub-questions Plan", expanded=False):
                                st.write(state_update.get("plan", []))
                                
                        elif node_name == "retriever":
                            with st.expander("Retrieved Sources", expanded=False):
                                st.write(f"Added {len(state_update.get('documents', []))} documents.")
                                
                        elif node_name == "synthesizer":
                            with st.expander(f"Draft (Iteration {current_state['iteration']})", expanded=False):
                                st.markdown(current_state["draft"])
                                
                        elif node_name == "critic":
                            st.write(f"**Score:** {current_state['score']} / 1.0")
                            with st.expander("Critique Details", expanded=False):
                                st.json(current_state["critique"])
            except Exception as e:
                st.error(f"Research execution failed: {e}")
                st.stop()
        
        st.write("---")
        st.subheader("🏆 Final Output Report")
        st.markdown(current_state["draft"])
        
        st.subheader("📊 Final Metrics")
        col1, col2 = st.columns(2)
        col1.metric("Final Score", current_state["score"])
        col2.metric("Total Iterations", current_state["iteration"])
        
        with st.expander("Show Document Sources", expanded=False):
            # deduplicate and show sources with URL sanitization
            seen = set()
            for doc in current_state.get("documents", []):
                src = doc.get("source", "Unknown")
                if src not in seen:
                    seen.add(src)
                    if _is_safe_url(src):
                        st.markdown(f"- [{src}]({src})")
                    else:
                        st.markdown(f"- {src} *(non-http source)*")
