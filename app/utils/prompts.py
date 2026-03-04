from langchain_core.prompts import ChatPromptTemplate

# --- PLANNER PROMPTS ---
PLANNER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", "You are an expert research planner. Your task is to break down the user's main query into a set of highly targeted, independent sub-questions that can be researched in parallel. Keep sub-questions concise, specific, and actionable. Do not answer the question, only output the sub-questions."),
    ("human", "Query: {query}\n\nProvide the sub-questions.")
])

# --- RETRIEVER PROMPTS ---
TOOL_ROUTER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a strategic tool selection agent. Your job is to decide the best source to answer a specific research sub-question.
Available tools:
- web_search: Best for recent events, broad factual queries, and general knowledge.
- vector_store: Best for analyzing specific internal documents or proprietary knowledge bases (if relevant context provided).
- cache: Best if the query seems trivial or a repeat of general knowledge that doesn't strictly need real-time search.

Select the best tool and provide a concise search query for it."""),
    ("human", "Sub-question: {sub_question}")
])

# --- SYNTHESIZER PROMPTS ---
SYNTHESIZER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an expert report synthesizer. Your task is to combine information from multiple retrieved sources into a comprehensive, well-structured report.
    
CRITICAL REQUIREMENT - CITATIONS:
You MUST cite your sources inline using brackets with the source URL or name, e.g., [https://example.com/article]. 
Do NOT make up citations. Only use the sources provided in the context below.

The report should have the following structure:
1. Introduction: Brief overview of the topic.
2. Key Findings: Main factual points discovered, well-cited.
3. Analysis: Deeper context or implications of the findings.
4. Conclusion: Summary of the research.

If there is contradictory information in the sources, acknowledge the conflict.
"""),
    ("human", """User Query: {query}
    
Retrieved Documents:
{documents}

Draft the comprehensive report with strict inline citations:""")
])

# --- CRITIC PROMPTS ---
CRITIC_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are an elite, multi-metric evaluation agent. Your job is to critique a draft research report.
You evaluate the report across three metrics on a scale of 0.0 to 1.0:
1. Factuality: Are the claims supported by the provided sources? Are citations present?
2. Completeness: Does the report fully address the original user query?
3. Clarity: Is the report well-structured, readable, and professional?

Provide an overall score (average of the three) and specific, actionable feedback on what is missing or needs improvement.
"""),
    ("human", """User Query: {query}

Draft Report:
{draft}

Evaluate the report:""")
])

# --- REFINER PROMPTS ---
REFINER_PROMPT = ChatPromptTemplate.from_messages([
    ("system", """You are a senior editor and refiner. Your task is to improve a draft research report based on a critique.
Address all feedback provided in the critique. Ensure citations are maintained or added if requested. 
Do not hallucinate new information; stick to refining the existing text or integrating suggested improvements based on the critique context.
"""),
    ("human", """User Query: {query}
    
Original Draft:
{draft}

Critique & Feedback:
{critique}

Provide the refined, updated report:""")
])
