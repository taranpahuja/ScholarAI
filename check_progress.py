#!/usr/bin/env python3
"""Quick progress checker for batch processing"""

import os
import sys
import json
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Add backend path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

try:
    from services.supabase_service import supabase
    
    print("=" * 70)
    print("📊 BATCH PROCESSING PROGRESS REPORT")
    print("=" * 70)
    
    # Check JSON file
    json_file = "scholarships_structured.json"
    data = []
    if os.path.exists(json_file):
        with open(json_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        first_id = data[0]['id'] if data else None
        last_id = data[-1]['id'] if data else None
        
        print(f"\n📁 JSON File Status:")
        print(f"   • File: {json_file}")
        print(f"   • Total scholarships: {len(data)}")
        print(f"   • ID range: {first_id} to {last_id}")
        print(f"   • Scholarships processed: {len(data)}/410 (from row 90)")
        
        if len(data) > 0:
            percentage = (len(data) / 410) * 100
            remaining = 410 - len(data)
            print(f"   • Progress: {percentage:.1f}%")
            print(f"   • Remaining: {remaining} scholarships")
            
            # Estimate time (assuming ~10 seconds per scholarship)
            est_minutes = (remaining * 10) / 60
            print(f"   • Estimated time remaining: ~{est_minutes:.0f} minutes")
    else:
        print(f"\n📁 JSON File: Not found")
    
    # Check Supabase
    print(f"\n☁️  Supabase Status:")
    try:
        result = supabase.table('scholarships').select('id', count='exact').execute()
        
        if result.count is not None:
            print(f"   • Total scholarships in database: {result.count}")
            
            # Get ID range
            min_result = supabase.table('scholarships').select('id').order('id', desc=False).limit(1).execute()
            max_result = supabase.table('scholarships').select('id').order('id', desc=True).limit(1).execute()
            
            if min_result.data and max_result.data:
                min_id = min_result.data[0]['id']
                max_id = max_result.data[0]['id']
                print(f"   • ID range: {min_id} to {max_id}")
        else:
            print(f"   • Could not get count")
            
    except Exception as e:
        print(f"   • Error connecting to Supabase: {str(e)}")
    
    print(f"\n📋 Next Steps:")
    if data and len(data) < 410:
        est_minutes = ((410 - len(data)) * 10) / 60
        print(f"   • Batch processor is still running")
        print(f"   • Wait for completion (~{est_minutes:.0f} more minutes)")
        print(f"   • Uploads to Supabase happen every 50 scholarships")
    elif data and len(data) >= 410:
        print(f"   • Phase 1 complete! ✅")
        print(f"   • Ready to run Phase 2: python process_missing_90.py")
    
    print("=" * 70)
    
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
