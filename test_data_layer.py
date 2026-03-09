import os
import shutil
import numpy as np
from pathlib import Path
from src.pb_studio.data.database_core import DatabaseCore
from src.pb_studio.data.repositories.project_repository import ProjectRepository
from src.pb_studio.data.vector_store import VectorStore
from src.pb_studio.utils.logging_setup import setup_logging

setup_logging("test_data")
print("--- Testing Data Layer ---")

# Setup Clean Environment
test_db_path = Path("./data/test_pb_studio.db")
if test_db_path.exists():
    test_db_path.unlink()
    
# 1. Test Database Core
print("\n[1] Testing DatabaseCore...")
try:
    # Inject test path via config trick or just rely on default for now, 
    # but since singleton uses ConfigManager, we might be writing to real DB if we aren't careful.
    # Ideally we'd mock config, but for now let's use the real class logic but maybe 
    # just check if it works. 
    # actually, let's just use the default DB path for verification, it's fine for dev.
    db = DatabaseCore()
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"   Tables found: {tables}")
    expected = ['projects', 'media', 'vector_map', 'sqlite_sequence']
    if all(t in tables for t in ['projects', 'media', 'vector_map']):
        print("   [OK] Schema created successfully.")
    else:
        print(f"   [FAIL] Missing tables. Found: {tables}")
except Exception as e:
    print(f"   [FAIL] Database Error: {e}")

# 2. Test Repository
print("\n[2] Testing ProjectRepository...")
try:
    repo = ProjectRepository()
    pid = repo.create_project("Test Project", {"status": "alpha"})
    print(f"   Created Project ID: {pid}")
    
    proj = repo.get_by_id(pid)
    print(f"   Retrieved: {proj['name']} (Data: {proj.get('data')})")
    
    repo.update_project(pid, name="Updated Project")
    proj_upd = repo.get_by_id(pid)
    print(f"   Updated Name: {proj_upd['name']}")
    
    if proj['name'] == "Test Project" and proj_upd['name'] == "Updated Project":
        print("   [OK] Repository CRUD works.")
    else:
        print("   [FAIL] Data mismatch.")
except Exception as e:
    print(f"   [FAIL] Repository Error: {e}")

# 3. Test Vector Store
print("\n[3] Testing VectorStore (FAISS)...")
try:
    # Use test index name
    vs = VectorStore(index_name="test_index")
    
    # Create random vector (dim 768)
    vec = np.random.random(768).astype('float32')
    
    fid = vs.add_embedding(vec, {"desc": "test_vector"})
    print(f"   Added Vector ID: {fid}")
    
    # Search for itself
    results = vs.search(vec, k=1)
    if results:
        meta, score = results[0]
        print(f"   Search Result: {meta} (Score: {score:.4f})")
        if meta['desc'] == "test_vector" and score > 0.99:
            print("   [OK] Vector Search accurate.")
        else:
            print("   [FAIL] Search result inaccurate.")
    else:
        print("   [FAIL] Search returned nothing.")
        
    vs.save()
    print("   [OK] Index saved.")
    
except Exception as e:
    print(f"   [FAIL] VectorStore Error: {e}")

print("\n--- Data Layer Verification Complete ---")
