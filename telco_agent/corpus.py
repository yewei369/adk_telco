from google.cloud import storage
from vertexai import rag
from vertexai.generative_models import GenerativeModel, Tool
import vertexai

# -----------------------
# Configuration Variables
# -----------------------
PROJECT_ID = "hacker2025-team-212-dev"
LOCATION = "us-central1" # e.g., "us-central1"
GCS_BUCKET_NAME = "northern_lights_bucket"
RAG_CORPUS_NAME = "northern_lights_rag_corpus"
EMBEDDING_MODEL = "publishers/google/models/text-embedding-005"  # Or choose another suitable model


# -----------------------
# Initialize Vertex AI
# -----------------------
vertexai.init(project=PROJECT_ID, location=LOCATION)

# -----------------------
# 1. Create a RAG Corpus (if it doesn't exist)
# -----------------------

try:
    # Attempt to retrieve the corpus (check if it exists)
    rag_corpus = rag.get_corpus(display_name=RAG_CORPUS_NAME)
    print(f"RAG Corpus '{RAG_CORPUS_NAME}' already exists.")

except: #TODO specify exception if corpus does not exist
    #Create embedding model config
    embedding_model_config = rag.RagEmbeddingModelConfig(
        vertex_prediction_endpoint=rag.VertexPredictionEndpoint(
            publisher_model=EMBEDDING_MODEL
        )
    )
    # Create the corpus
    rag_corpus = rag.create_corpus(
        display_name=RAG_CORPUS_NAME,
        backend_config=rag.RagVectorDbConfig(
            rag_embedding_model_config=embedding_model_config
        ),
    )
    print(f"RAG Corpus '{RAG_CORPUS_NAME}' created.")

# -----------------------
# 2. Upload Documents from GCS to the RAG Corpus
# -----------------------

def import_gcs_files_to_corpus(bucket_name, corpus_name):
    """
    Imports all files from a GCS bucket into a RAG Corpus.
    """
    storage_client = storage.Client()
    bucket = storage_client.bucket(bucket_name)
    blobs = bucket.list_blobs() # Get all files in the bucket

    file_paths = [f"gs://{bucket_name}/{blob.name}" for blob in blobs] # Create paths for RAG import
    print(f"Importing files: {file_paths}")

    # Import files into the RAG Corpus
    rag.import_files(
        corpus_name,
        file_paths,
        transformation_config=rag.TransformationConfig(
            chunking_config=rag.ChunkingConfig(
                chunk_size=512,
                chunk_overlap=100,
            ),
        ),
        max_embedding_requests_per_min=1000,  # Optional
    )

#Call the upload function
#import_gcs_files_to_corpus(GCS_BUCKET_NAME, rag_corpus.name)


