#!/usr/bin/env python3
"""Automatically create Supabase scholarships table"""

import sys
from pathlib import Path

# Add backend path
sys.path.insert(0, str(Path(__file__).parent / "backend"))

from services.supabase_service import supabase
from config import Config

# SQL to create the table
CREATE_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS scholarships (
  id INT PRIMARY KEY,
  scholarship_name VARCHAR(500),
  amount FLOAT,
  deadline VARCHAR(100),
  description TEXT,
  location VARCHAR(500),
  link VARCHAR(1000),
  min_gpa FLOAT,
  max_gpa FLOAT,
  eligible_majors TEXT[],
  eligible_years TEXT[],
  ethnicity VARCHAR(255),
  gender VARCHAR(50),
  citizenship VARCHAR(100),
  age_limit INT,
  membership_required VARCHAR(255),
  min_income BIGINT,
  max_income BIGINT,
  restrictions TEXT,
  raw_json JSONB,
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW()
);
"""

CREATE_INDEXES_SQL = """
CREATE INDEX IF NOT EXISTS idx_scholarship_name ON scholarships(scholarship_name);
CREATE INDEX IF NOT EXISTS idx_gpa_requirements ON scholarships(min_gpa, max_gpa);
CREATE INDEX IF NOT EXISTS idx_major ON scholarships USING GIN (eligible_majors);
"""

print("=" * 70)
print("🗄️  SUPABASE TABLE CREATION")
print("=" * 70)

try:
    # Test connection
    print("\n1️⃣  Testing Supabase connection...")
    test_response = supabase.table("scholarships").select("*", count="exact").limit(1).execute()
    print("   ✓ Connection successful!")
    print("   ℹ️ Table 'scholarships' already exists\n")
    
    print("=" * 70)
    print("✅ SUPABASE IS READY")
    print("=" * 70)
    print("The 'scholarships' table already exists!")
    print("\nYou can now:")
    print("  1. Run batch_processor.py to fill the table with data")
    print("  2. Data will automatically sync to Supabase every 50 rows")
    
except Exception as e:
    error_msg = str(e)
    
    # If table doesn't exist, try to create it
    if "relation" in error_msg.lower() or "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
        print("\n2️⃣  Table doesn't exist yet. Creating...")
        
        try:
            # Execute CREATE TABLE
            response = supabase.rpc('exec_sql', {
                'sql': CREATE_TABLE_SQL
            }).execute()
            print("   ✓ Table created!")
            
            # Execute CREATE INDEXES
            print("\n3️⃣  Creating indexes...")
            response = supabase.rpc('exec_sql', {
                'sql': CREATE_INDEXES_SQL
            }).execute()
            print("   ✓ Indexes created!")
            
            print("\n" + "=" * 70)
            print("✅ SUPABASE TABLE CREATED SUCCESSFULLY")
            print("=" * 70)
            print("\nScholarships table is ready!")
            print("Columns: id, scholarship_name, amount, deadline, location, link,")
            print("         min_gpa, max_gpa, eligible_majors, eligible_years, ethnicity,")
            print("         gender, citizenship, age_limit, membership_required, etc.")
            print("\nYou can now:")
            print("  1. Run batch_processor.py to extract and upload data")
            print("  2. Data will sync to Supabase every 50 scholarships")
            print("  3. Your API will query from both JSON and Supabase")
            
        except Exception as create_error:
            # RPC function might not exist, try alternative method
            print(f"   ⚠️ RPC method not available: {str(create_error)[:100]}")
            print("\n" + "=" * 70)
            print("⚠️  MANUAL TABLE CREATION NEEDED")
            print("=" * 70)
            print("\nSupabase 'exec_sql' RPC function not available.")
            print("Please create the table manually:\n")
            
            print("1. Go to: https://supabase.com/dashboard")
            print("2. Select your project")
            print("3. Go to: SQL Editor → New Query")
            print("4. Paste and run this SQL:\n")
            
            print("---START SQL---")
            print(CREATE_TABLE_SQL)
            print(CREATE_INDEXES_SQL)
            print("---END SQL---\n")
            
            print("After creating the table, run:")
            print("  python batch_processor.py")
            
    else:
        print(f"\n❌ Connection Error: {error_msg}")
        print("\nPlease check:")
        print("  1. SUPABASE_URL in .env is correct")
        print("  2. SUPABASE_KEY in .env is correct")
        print("  3. Internet connection is working")

print("=" * 70)
