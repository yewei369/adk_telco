from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
import vertexai

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
                    rag_corpus='northern_lights_corpus',  # Currently only 1 corpus is allowed.
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
        str: the generated response
    """

    # Create a Gemini model instance and pass in the tool
    llm = GenerativeModel(model_name="gemini-2.0-flash-001", tools=[rag_retrieval_tool])
    response = llm.generate_content(query)

    logging.info(f"Retrieved response:{response.text}")
    return {"response": response.text}

# Example query
#query = "What is RAG and why is it helpful?"

# Run the query and print the response
#rag_response = query_rag_tool(query, llm)
#print(rag_response)