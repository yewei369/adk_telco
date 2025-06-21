from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
import vertexai
import logging

# -----------------------
# 3. Create RAG Retrieval Tool
# -----------------------
rag_retrieval_config = rag.RagRetrievalConfig(
    top_k=3,  # Optional
    filter=rag.Filter(vector_distance_threshold=0.5),  # Optional
)

rag_retrieval_tool = Tool.from_retrieval(
    retrieval=rag.Retrieval(
        source=rag.VertexRagStore(
            rag_resources=[
                rag.RagResource(
                    rag_corpus='projects/hacker2025-team-212-dev/locations/us-central1/ragCorpora/4611686018427387904',  # Currently only 1 corpus is allowed.
                    # Optional: supply IDs from `rag.list_files()`.
                    # rag_file_ids=["rag-file-1", "rag-file-2", ...],
                )
            ],
            rag_retrieval_config=rag_retrieval_config,
        ),
    )
)

# -----------------------
# 4. Integrate Tool into Agent and Run Query
# -----------------------

def query_rag_tool(query: str):
    """
    Takes the RAG tool and generated a response to a query
    Args:
        query: the query and logged dialog with the user
    Returns:
        dict: A dictionary containing the RAG retrieval results.
    """

    try:
        # Create a Gemini model instance and pass in the tool
        llm = GenerativeModel(model_name="gemini-2.0-flash-001", tools=[rag_retrieval_tool])
        response = llm.generate_content(query)

        logging.info(f"Retrieved RAG response:{response.text}")
        return {"response": response.text}
    except Exception as e:
        logging.error(f"Error in query_rag_tool: {e}")
        return {"error": str(e)}

'''
# Example query
query = "What can I do with AX11000 having no connection to internet?"
# Run the query and print the response
rag_response = query_rag_tool(query)
print(rag_response)
'''