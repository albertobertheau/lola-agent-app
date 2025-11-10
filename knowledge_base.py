import chromadb
from chromadb.utils import embedding_functions

# NOTE: We no longer need 'google.generativeai', 'os', or 'dotenv' in this file
# because we are handling embeddings locally.

class KnowledgeBase:
    def __init__(self, collection_name="chainbrief_docs"):
        """
        Initializes the KnowledgeBase using a local sentence-transformer model for embeddings.
        This runs on your machine and does not require an API key or internet connection
        after the initial model download.
        """
        self.is_functional = False
        self.collection = None
        
        try:
            # Initialize the ChromaDB client, which will store data in the './chroma_db' directory.
            self.client = chromadb.PersistentClient(path="./chroma_db")
            
            # --- THE KEY CHANGE IS HERE ---
            # Use a built-in, high-performance SentenceTransformer model for local embeddings.
            # The model 'all-MiniLM-L6-v2' is small, fast, and effective for semantic search.
            # It will be downloaded automatically by the library on the first run.
            print("🧠 Inicializando función de embedding local (modelo: all-MiniLM-L6-v2)...")
            self.embedding_function = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="all-MiniLM-L6-v2"
            )
            
            # Create or get the collection, now configured to use the local embedding function.
            self.collection = self.client.get_or_create_collection(
                name=collection_name,
                embedding_function=self.embedding_function
            )
            print(f"✅ ChromaDB collection '{collection_name}' inicializada con éxito usando embeddings locales.")
            self.is_functional = True

        except Exception as e:
            print("="*60)
            print(f"⚠️ ADVERTENCIA CRÍTICA: ChromaDB no pudo inicializarse. Error: {e}")
            print("La búsqueda semántica (RAG) estará deshabilitada.")
            print("="*60)

    def add_document(self, doc_id, content, metadata):
        """Adds a single document chunk to the collection."""
        if not self.is_functional: return
        try:
            # The embedding is now handled automatically by the collection's configured function.
            self.collection.add(documents=[content], metadatas=[metadata], ids=[doc_id])
            print(f"Added document chunk {doc_id} to knowledge base.")
        except Exception as e:
            print(f"Error al añadir documento {doc_id} a ChromaDB: {e}")

    def update_document(self, doc_id, new_content, new_metadata):
        """Updates a document by deleting the old version and adding the new one."""
        if not self.is_functional: return
        try:
            # Using upsert is more efficient for updating
            self.collection.upsert(documents=[new_content], metadatas=[new_metadata], ids=[doc_id])
            print(f"Updated (upserted) document chunk {doc_id} in knowledge base.")
        except Exception as e:
            print(f"Error al actualizar documento {doc_id} en ChromaDB: {e}")

    def query(self, query_text, n_results=5):
        """Queries the collection for documents similar to the query text."""
        if not self.is_functional:
            print("❌ ChromaDB no funcional. Consulta fallida.")
            return {'documents': [[]], 'metadatas': [[]]}
        
        try:
            return self.collection.query(
                query_texts=[query_text],
                n_results=n_results,
            )
        except Exception as e:
            print(f"Error en la consulta de ChromaDB: {e}")
            return {'documents': [[]], 'metadatas': [[]]}