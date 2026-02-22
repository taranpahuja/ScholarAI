import os
import csv
import json
import requests
import time
import sys
import threading
from typing import List, Optional
from dotenv import load_dotenv
from pydantic import BaseModel, Field
from tqdm import tqdm
from pathlib import Path

load_dotenv()

# Add backend path to import supabase service
sys.path.insert(0, str(Path(__file__).parent / "backend"))



class ScholarshipCriteria(BaseModel):
    scholarship_name: str = Field(description="Name of the Scholarship")
    min_gpa: Optional[float] = Field(default=None, description="Minimum GPA required, e.g., 3.5")
    max_gpa: Optional[float] = Field(default=None, description="Maximum GPA if specified")
    eligible_majors: List[str] = Field(default_factory=list, description="List of majors like 'Computer Science'")
    deadline: Optional[str] = Field(default=None, description="Application deadline in YYYY-MM-DD")
    max_income: Optional[int] = Field(default=None, description="Maximum annual family income allowed")
    min_income: Optional[int] = Field(default=None, description="Minimum annual family income if specified")
    amount: Optional[float] = Field(default=None, description="Scholarship amount in USD")
    location: Optional[str] = Field(default=None, description="Geographic restrictions")
    eligible_years: List[str] = Field(default_factory=list, description="Eligible year levels (freshman, sophomore, etc.)")
    ethnicity: Optional[str] = Field(default=None, description="Ethnicity requirements")
    gender: Optional[str] = Field(default=None, description="Gender requirements")
    citizenship: Optional[str] = Field(default=None, description="Citizenship requirements")
    age_limit: Optional[int] = Field(default=None, description="Maximum age limit")
    membership_required: Optional[str] = Field(default=None, description="Organization membership requirements")
    restrictions: Optional[str] = Field(default=None, description="Other specific restrictions")
    link: Optional[str] = Field(default=None, description="Application link")


def call_megallm(prompt: str) -> dict:
    """Call MegaLLM API with JSON response, handles rate limits"""
    api_key = os.getenv("MEGALLM_API_KEY")
    if not api_key:
        raise RuntimeError("MEGALLM_API_KEY is not set")
    
    max_retries = 5  # Increased from 3 to 5
    retry_count = 0
    
    while retry_count < max_retries:
        try:
            response = requests.post(
                "https://ai.megallm.io/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": "openai-gpt-oss-20b",
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0
                },
                timeout=30  # Increased from 15 to 30 seconds
            )
            
            result = response.json()
            
            # Check for rate limit error
            if response.status_code == 429:
                retry_after = result.get('retryAfter', 15 * (2 ** retry_count))
                print(f"\n⏱️ Rate limit hit. Waiting {retry_after} seconds before retry...")
                time.sleep(retry_after + 2)  # Add 2 second buffer
                retry_count += 1
                continue
            
            if response.status_code != 200:
                raise RuntimeError(f"MegaLLM API error: {result}")
            
            return result
            
        except (requests.exceptions.Timeout, requests.exceptions.ConnectionError, 
                requests.exceptions.RequestException) as e:
            retry_count += 1
            if retry_count < max_retries:
                wait_time = 10 * (2 ** retry_count)  # Longer waits: 20s, 40s, 80s
                print(f"\n⏱️ Network error ({type(e).__name__}). Waiting {wait_time} seconds before retry {retry_count}/{max_retries}...")
                time.sleep(wait_time)
            else:
                raise RuntimeError(f"API error after {max_retries} retries: {str(e)}")
    
    raise RuntimeError("Max retries exceeded")


def extract_criteria_from_row(row: dict) -> ScholarshipCriteria:
    """Extract structured criteria from a CSV row using MegaLLM"""
    prompt = f"""You are an expert scholarship data extraction assistant.
Extract the eligibility criteria from the following scholarship information.
Return ONLY valid JSON with no markdown formatting - no ```json wrapper, just raw JSON.
If a specific field is missing or not mentioned, use null.
Do not make up information - only extract what is explicitly stated.

SCHOLARSHIP INFORMATION:
Name: {row['Scholarship Name']}
Deadline: {row['Deadline']}
Amount: {row['Amount']}
Description: {row['Description']}
Location: {row['Location']}
Eligible Years: {row['Years']}
Link: {row['Link']}

Return JSON with these fields:
{{
  "scholarship_name": "string",
  "min_gpa": number or null,
  "max_gpa": number or null,
    "eligible_majors": ["string"],
  "deadline": "YYYY-MM-DD or null",
  "max_income": number or null,
  "min_income": number or null,
  "amount": number or null,
  "location": "string or null",
    "eligible_years": ["string"],
  "ethnicity": "string or null",
  "gender": "string or null",
  "citizenship": "string or null",
  "age_limit": number or null,
  "membership_required": "string or null",
  "restrictions": "string or null",
  "link": "string or null"
}}"""
    
    try:
        response = call_megallm(prompt)
        content = response["choices"][0]["message"]["content"]
        
        # Parse JSON from response
        try:
            data = json.loads(content)
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            if "```json" in content:
                data = json.loads(content.split("```json")[1].split("```")[0].strip())
            elif "```" in content:
                data = json.loads(content.split("```")[1].split("```")[0].strip())
            else:
                raise ValueError(f"Could not parse JSON from response: {content}")
        
        # Normalize list fields that may come back as null
        if data.get("eligible_majors") is None:
            data["eligible_majors"] = []
        if data.get("eligible_years") is None:
            data["eligible_years"] = []

        # Create ScholarshipCriteria instance
        result = ScholarshipCriteria(**data)
        return result
        
    except Exception as e:
        raise RuntimeError(f"Error extracting criteria: {str(e)}")


def upload_batch_to_supabase_async(batch_results: List[dict], batch_num: int):
    """Upload a batch of scholarships to Supabase asynchronously"""
    try:
        from services.supabase_service import upload_scholarships_to_supabase
        
        print(f"\n📤 [Background] Uploading batch {batch_num} ({len(batch_results)} scholarships) to Supabase...")
        result = upload_scholarships_to_supabase(batch_results)
        
        if result["success"]:
            print(f"✅ [Background] Batch {batch_num} uploaded: {result['uploaded']}/{result['total']} scholarships")
        else:
            print(f"⚠️ [Background] Batch {batch_num} upload failed: {result.get('error', 'Unknown error')}")
            
    except ImportError:
        print(f"⚠️ [Background] Could not import supabase service")
    except Exception as e:
        print(f"⚠️ [Background] Error uploading batch {batch_num}: {str(e)[:100]}")



def process_csv_to_structured(input_csv: str, output_json: str, start_row: int = 0, max_rows: int = None):
    """
    Process CSV file and extract structured criteria for each scholarship
    
    Args:
        input_csv: Path to input CSV file
        output_json: Path to output JSON file
        start_row: Row to start from (for resuming after errors)
        max_rows: Maximum number of rows to process (None for all)
    """
    # Load existing results if file exists (APPEND mode instead of overwrite)
    if os.path.exists(output_json):
        try:
            with open(output_json, 'r', encoding='utf-8') as f:
                results = json.load(f)
            print(f"✓ Loaded {len(results)} existing scholarships from {output_json}")
        except:
            results = []
    else:
        results = []
    
    upload_batch = []
    batch_num = 0
    
    with open(input_csv, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Determine the range to process
    end_row = len(rows) if max_rows is None else min(start_row + max_rows, len(rows))
    rows_to_process = rows[start_row:end_row]
    
    print(f"Processing rows {start_row} to {end_row} ({len(rows_to_process)} scholarships)")
    print("📤 Supabase uploads will happen automatically every 50 scholarships\n")
    
    for idx, row in enumerate(tqdm(rows_to_process, desc="Extracting criteria"), start=start_row):
        try:
            criteria = extract_criteria_from_row(row)
            
            # Add original CSV data
            result = {
                "id": idx,
                "raw_data": row,
                "structured_criteria": criteria.model_dump()
            }
            results.append(result)
            upload_batch.append(result)
            
            # Add delay to avoid rate limiting (free tier = ~8 req/minute safe limit)
            time.sleep(8)  # 8 seconds = ~7.5 requests per minute (safer)
            
            # Save intermediate results every 10 scholarships
            if len(results) % 10 == 0:
                with open(output_json, 'w', encoding='utf-8') as f:
                    json.dump(results, f, indent=2)
                print(f"\nSaved progress: {len(results)} scholarships processed")
            
            # Upload to Supabase every 20 scholarships (asynchronously) - based on items in upload_batch
            if len(upload_batch) >= 20:
                batch_num += 1
                batch_to_upload = upload_batch.copy()
                upload_batch = []
                
                # Start upload in background thread
                upload_thread = threading.Thread(
                    target=upload_batch_to_supabase_async,
                    args=(batch_to_upload, batch_num),
                    daemon=True
                )
                upload_thread.start()
                
        except Exception as e:
            print(f"\n❌ Error processing row {idx} ({row.get('Scholarship Name', 'Unknown')}): {e}")
            print(f"⏭️  Skipping this scholarship and continuing with next...")
            # Save what we have so far
            with open(output_json, 'w', encoding='utf-8') as f:
                json.dump(results, f, indent=2)
            # Log the error to a file
            with open('processing_errors.log', 'a', encoding='utf-8') as log:
                log.write(f"Row {idx}: {row.get('Scholarship Name', 'Unknown')} - Error: {str(e)}\n")
            # ✅ CONTINUE instead of crashing
            continue
    
    # Final save to JSON
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n✓ Processing complete! {len(results)} scholarships extracted to {output_json}")
    
    # Upload any remaining scholarships that weren't in a 50-batch
    if upload_batch:
        batch_num += 1
        upload_thread = threading.Thread(
            target=upload_batch_to_supabase_async,
            args=(upload_batch, batch_num),
            daemon=True
        )
        upload_thread.start()
        print(f"📤 Uploading final batch {batch_num} ({len(upload_batch)} scholarships) to Supabase...")
    
    return results


if __name__ == "__main__":
    input_file = "output.csv"
    output_file = "scholarships_structured.json"
    
    print("Starting batch processing of scholarships...")
    print("Using MegaLLM API to extract structured criteria from each scholarship.\n")
    
    # Process in batches - start with first 5 as a test
    # Change max_rows=None to process all scholarships
    try:
        results = process_csv_to_structured(
            input_csv=input_file,
            output_json=output_file,
            start_row=0,
            max_rows=None  # Process all scholarships
        )
        
        print(f"\n✓ Sample extraction successful!")
        print(f"First scholarship criteria:")
        print(json.dumps(results[0]['structured_criteria'], indent=2))
        
        # Display completion summary
        print("\n" + "=" * 60)
        print("✅ PROCESSING COMPLETE")
        print("=" * 60)
        print(f"Total scholarships: {len(results)}")
        print(f"Saved to: {output_file}")
        print(f"\n📤 Supabase uploads are happening in the background:")
        print(f"   Batch uploads: Every 50 scholarships")
        print(f"   Check Supabase dashboard to see data arriving...")
        print("=" * 60)
        
    except Exception as e:
        print(f"\n✗ Error: {e}")
        print("Check the output file for partial results.")

