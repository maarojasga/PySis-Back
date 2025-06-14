import os
import fitz
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import FAISS
from dotenv import load_dotenv

load_dotenv()

def get_embeddings_local():
    """
    Crea y devuelve una instancia de embeddings de Google Generative AI.
    """
    google_api_key = os.getenv("GOOGLE_API_KEY")
    if not google_api_key:
        raise ValueError("GOOGLE_API_KEY no encontrada en el archivo .env")
    return GoogleGenerativeAIEmbeddings(model="models/embedding-001", google_api_key=google_api_key)

def extract_text_from_pdf(file_path: str) -> str:
    """
    Extrae texto de un archivo PDF de forma robusta usando PyMuPDF (fitz).
    """
    text = ""
    try:
        with fitz.open(file_path) as doc:
            for page in doc:
                try:
                    text += page.get_text() + "\n"
                except Exception as page_error:
                    print(f"  - Advertencia: Error extrayendo texto de una página en {file_path}. Error: {page_error}")
                    continue
    except Exception as e:
        print(f"Error crítico abriendo o leyendo el PDF {file_path} con PyMuPDF: {e}")
    return text

def main():
    """
    Script principal para procesar los PDFs y crear los vectorstores diarios.
    """
    pdf_source_directory = "course_content/"
    vectorstore_base_path = "../PySis-Back/"

    if not os.path.exists(pdf_source_directory):
        print(f"Error: El directorio fuente de PDFs '{pdf_source_directory}' no existe. Por favor, créalo y añade tus PDFs.")
        return

    os.makedirs(vectorstore_base_path, exist_ok=True)
    
    try:
        embeddings = get_embeddings_local()
    except ValueError as e:
        print(f"Error crítico: {e}")
        return

    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=150, length_function=len)

    print("Iniciando preprocesamiento de documentos...")
    for day_number in range(1, 31):
        pdf_filename = f"dia_{day_number}.pdf"
        pdf_filepath = os.path.join(pdf_source_directory, pdf_filename)

        if not os.path.exists(pdf_filepath):
            continue

        print(f"Procesando documento para el Día {day_number}: {pdf_filepath}...")
        raw_text = extract_text_from_pdf(pdf_filepath)
        
        if not raw_text.strip():
            print(f"Advertencia: No se extrajo texto del PDF para el día {day_number}. El archivo puede estar vacío o corrupto.")
            continue

        chunks = text_splitter.split_text(raw_text)
        print(f"Día {day_number}: {len(chunks)} chunks generados.")

        try:
            vectorstore = FAISS.from_texts(texts=chunks, embedding=embeddings)
            day_store_path = os.path.join(vectorstore_base_path, f"dia_{day_number}")
            os.makedirs(day_store_path, exist_ok=True)
            vectorstore.save_local(day_store_path)
            print(f"Vectorstore para el Día {day_number} guardado en: {day_store_path}")
        except Exception as e:
            print(f"Error creando/guardando vectorstore para el Día {day_number}: {e}")

    print("\nPreprocesamiento de todos los documentos completado.")

if __name__ == "__main__":
    main()