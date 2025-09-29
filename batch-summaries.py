"""python script to summarize texts stored in a sqllite database through gemini api. 
Batches requests together to use minimal requests within free tier token limits. Creates sumamry/metadata for each row based on prompt below. 
Note to self, initialize key with bash: export GOOGLE_API_KEY='API-KEY' // generate a new key at https://aistudio.google.com/api-keys? """


import os
import sqlite3
import time
import google.generativeai as genai
import logging
import json
from datetime import datetime

# --- Configuration ---
CONFIG = {
    'db_filename': 'scraped_data.db',
    'model_name': 'gemini-2.0-flash',
    'max_text_length_per_article': 16000,
    'DB_PROCESSING_LIMIT': 200,          # Max articles to fetch from DB in one script run
    'TOKEN_BUDGET_PER_BATCH': 100000,    # Target token count for one API call (safely below 250k limit)
    'CHARS_PER_TOKEN_ESTIMATE': 4,       # Standard estimation: 1 token ~ 4 chars
    'request_delay_seconds': 3,          # Delay between batch API calls
    'max_retries': 3,
    'db_metadata_columns': {
        'category': 'TEXT',
        'technical_depth': 'INTEGER',
        'keywords': 'TEXT',
        'summary': 'TEXT',
        'model_version': 'TEXT',
        'last_analyzed_utc': 'TEXT'
    }
}

# --- Logging & API Setup ---
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

try:
    API_KEY = os.environ["GOOGLE_API_KEY"]
    genai.configure(api_key=API_KEY)
except KeyError:
    logging.error("❌ FATAL: GOOGLE_API_KEY environment variable not set.")
    exit()

model = genai.GenerativeModel(CONFIG['model_name'])

# --- Advanced Batch Prompt (Escaped for .format()) ---
PROMPT_TEMPLATE = """
**Role:** You are a highly efficient technical content analyst. Your task is to analyze a BATCH of articles and return structured metadata for EACH article.

**Instructions:**
1.  You will be provided with multiple articles, each marked with a unique identifier (e.g., "--- ARTICLE article_123 ---").
2.  Analyze each article independently based on the JSON schema provided below.
3.  Your response MUST be a single, valid JSON object.
4.  The keys of this JSON object MUST be the exact article identifiers (e.g., "article_123").
5.  The value for each key MUST be the JSON analysis object for that article. Do not include any text or markdown outside of the main JSON object.

**JSON Schema for EACH Article's Analysis:**
{{
  "category": "Choose one of: 'Partnership Announcement', 'Product Feature/Guide', 'Customer Story/Case Study', '#SolvedStories Recap', 'General Marketing', 'Deep Technical Analysis'",
  "technical_depth": "Rate the technical depth on a scale of 1 to 5, where 1 = Marketing fluff and 5 = In-depth guide for engineers.",
  "keywords": "Provide an array of 3-5 relevant technical keywords or phrases from the article.",
  "summary": "Write a concise, one-sentence summary of the article's main point."
}}

**Batch of Articles to Analyze:**
{batch_text}
"""
# --- End of Configuration ---

def setup_database(cursor: sqlite3.Cursor):
    """Ensures all required metadata columns exist in the database."""
    logging.info("Verifying database schema...")
    for column, col_type in CONFIG['db_metadata_columns'].items():
        try:
            cursor.execute(f"ALTER TABLE scraped_content ADD COLUMN {column} {col_type}")
            logging.info(f"Added '{column}' column to the database.")
        except sqlite3.OperationalError as e:
            if "duplicate column name" not in str(e):
                logging.error(f"DB error adding column '{column}': {e}", exc_info=True)
    logging.info("Database schema verification complete.")

def create_dynamic_batches(rows: list, token_budget: int) -> list:
    """
    Creates batches of articles based on a total token budget per batch.
    Uses a greedy approach to pack as many articles as possible into each batch.
    """
    batches = []
    current_batch = []
    # Estimate token overhead for the prompt template instructions and structure
    prompt_overhead_tokens = len(PROMPT_TEMPLATE) // CONFIG['CHARS_PER_TOKEN_ESTIMATE']
    current_batch_tokens = prompt_overhead_tokens

    for row in rows:
        _, _, text = row
        text_content = text if isinstance(text, str) else ""

        # Estimate tokens for this article's content + its specific wrapper (e.g., "--- ARTICLE article_123 ---")
        article_tokens = (len(text_content) // CONFIG['CHARS_PER_TOKEN_ESTIMATE']) + 20

        if not current_batch or (current_batch_tokens + article_tokens) <= token_budget:
            current_batch.append(row)
            current_batch_tokens += article_tokens
        else:
            batches.append(current_batch)
            current_batch = [row]
            current_batch_tokens = prompt_overhead_tokens + article_tokens

    if current_batch:
        batches.append(current_batch)

    logging.info(f"Dynamically created {len(batches)} batches from {len(rows)} articles.")
    return batches

def analyze_batch_of_articles(batch: list) -> dict | None:
    """
    Constructs a single prompt for a batch of articles and calls the LLM API.
    """
    prompt_texts, article_ids = [], {}
    for rowid, _, text in batch:
        if not isinstance(text, str) or len(text.strip()) < 100:
            continue
        
        article_id = f"article_{rowid}"
        article_ids[rowid] = article_id
        truncated_text = text[:CONFIG['max_text_length_per_article']]
        prompt_texts.append(f"--- ARTICLE {article_id} ---\n{truncated_text}\n")

    if not prompt_texts:
        return {}

    final_prompt = PROMPT_TEMPLATE.format(batch_text="\n".join(prompt_texts))
    generation_config = genai.types.GenerationConfig(response_mime_type="application/json")

    for attempt in range(CONFIG['max_retries']):
        try:
            response = model.generate_content(final_prompt, generation_config=generation_config)
            parsed_response = json.loads(response.text)
            
            results_by_rowid = {rowid: parsed_response.get(article_id) 
                                for rowid, article_id in article_ids.items() 
                                if parsed_response.get(article_id)}
            return results_by_rowid
        except (json.JSONDecodeError, Exception) as e:
            logging.warning(f"API/JSON Error (Attempt {attempt + 1}): {e}")
            if attempt < CONFIG['max_retries'] - 1: time.sleep(2 ** attempt)
    return None

def main():
    """Main function to run the dynamic batched content analysis process."""
    conn = sqlite3.connect(CONFIG['db_filename'])
    cursor = conn.cursor()
    setup_database(cursor)
    conn.commit()

    query = f"SELECT rowid, filename, pagetext FROM scraped_content WHERE technical_depth IS NULL LIMIT {CONFIG['DB_PROCESSING_LIMIT']}"
    rows_to_process = cursor.execute(query).fetchall()

    if not rows_to_process:
        logging.info("All articles have already been analyzed. ✨")
        conn.close()
        return

    # Create batches dynamically based on token count
    all_batches = create_dynamic_batches(rows_to_process, CONFIG['TOKEN_BUDGET_PER_BATCH'])
    total_batches = len(all_batches)
    logging.info(f"Total articles to process: {len(rows_to_process)}. Batches created: {total_batches}.")

    for i, batch in enumerate(all_batches, 1):
        logging.info(f"--- Processing Batch {i}/{total_batches} ({len(batch)} articles) ---")
        batch_results = analyze_batch_of_articles(batch)

        if batch_results:
            logging.info(f"Successfully received analysis for {len(batch_results)} articles in the batch.")
            for rowid, analysis in batch_results.items():
                params = {
                    'category': analysis.get('category'), 'technical_depth': analysis.get('technical_depth'),
                    'keywords': json.dumps(analysis.get('keywords', [])), 'summary': analysis.get('summary'),
                    'model_version': CONFIG['model_name'], 'last_analyzed_utc': datetime.utcnow().isoformat(),
                    'rowid': rowid
                }
                update_query = """UPDATE scraped_content SET
                                    category = :category, technical_depth = :technical_depth, keywords = :keywords,
                                    summary = :summary, model_version = :model_version, last_analyzed_utc = :last_analyzed_utc
                                WHERE rowid = :rowid"""
                try:
                    cursor.execute(update_query, params)
                except sqlite3.Error as e:
                    logging.error(f"Failed to update DB for rowid {rowid}: {e}")
            conn.commit()
        else:
            logging.error(f"Failed to analyze batch {i} after multiple retries.")
        
        if i < total_batches:
            logging.info(f"Waiting for {CONFIG['request_delay_seconds']}s before next batch...")
            time.sleep(CONFIG['request_delay_seconds'])

    conn.close()
    logging.info("\n✅ Dynamic batch analysis complete! The database has been updated.")

if __name__ == "__main__":
    main()
