import os
import sys
import ast
import traceback
from pathlib import Path

def scan_file(filepath: Path):
    """Surgically analyzes a Python file for common bugs and anti-patterns."""
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8")
        tree = ast.parse(content)
        
        # AST analysis
        has_vram_mgr = False
        has_sqlite = False
        
        for node in ast.walk(tree):
            # Check for imports
            if isinstance(node, ast.Import):
                for name in node.names:
                    if "sqlite3" in name.name:
                        has_sqlite = True
            elif isinstance(node, ast.ImportFrom):
                if node.module and "vram_budget_manager" in node.module:
                    has_vram_mgr = True
                if node.module and "sqlite3" in node.module:
                    has_sqlite = True
                    
            # Check for cap.setCAP_PROP_POS_FRAMES inside loops
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr == "set":
                        # Check if cv2.CAP_PROP_POS_FRAMES is passed
                        for arg in node.args:
                            if isinstance(arg, ast.Attribute) and arg.attr == "CAP_PROP_POS_FRAMES":
                                # Found slow seek
                                issues.append({
                                    "type": "PERFORMANCE",
                                    "message": "Slow random seek cap.set(CAP_PROP_POS_FRAMES) detected. Prefer sequential cap.grab()/cap.read().",
                                    "line": node.lineno
                                })
                                
            # Check for SQLite transaction issues (missing BEGIN IMMEDIATE on writes)
            if isinstance(node, ast.Str) and isinstance(node.parent, ast.Call) if hasattr(node, 'parent') else False:
                # We can do basic string matches instead for robustness
                pass
                
        # Simple text matches for critical issues
        lines = content.splitlines()
        for idx, line in enumerate(lines):
            line_no = idx + 1
            # Check for raw sqlite3.connect without WAL/immediate
            if "sqlite3.connect" in line and "isolation_level" not in line and "embedding_repository" not in str(filepath):
                issues.append({
                    "type": "CONCURRENCY",
                    "message": "Raw sqlite3.connect without immediate transaction lock or WAL mode. Risk of SQLITE_BUSY.",
                    "line": line_no
                })
            # Check for sys.path manipulation
            if "sys.path.append" in line:
                issues.append({
                    "type": "ARCHITECTURE",
                    "message": "Path manipulation sys.path.append detected. Risk of import drifts.",
                    "line": line_no
                })
            # Check for unfinished TODOs
            if "TODO" in line or "FIXME" in line:
                issues.append({
                    "type": "MARKER",
                    "message": f"Found TODO/FIXME marker: {line.strip()}",
                    "line": line_no
                })
                
    except SyntaxError as se:
        issues.append({
            "type": "SYNTAX",
            "message": f"Syntax error: {se}",
            "line": se.lineno or 0
        })
    except Exception as e:
        issues.append({
            "type": "ERROR",
            "message": f"Failed to parse file: {e}",
            "line": 0
        })
        
    return issues

def run_surgical_audit():
    root_dir = Path("C:/Users/david/Documents/Pb_studio_AMD_version")
    src_dir = root_dir / "src"
    backend_dir = root_dir / "backend"
    
    python_files = list(src_dir.glob("**/*.py")) + list(backend_dir.glob("**/*.py"))
    
    print(f"Starting surgical audit over {len(python_files)} Python files...")
    all_issues = {}
    
    for f in python_files:
        rel_path = f.relative_to(root_dir)
        issues = scan_file(f)
        if issues:
            all_issues[str(rel_path)] = issues
            
    print("\n--- AUDIT REPORT ---\n")
    if not all_issues:
        print("Success: 0 critical issues found across all files!")
    else:
        for path, file_issues in all_issues.items():
            print(f"File: {path}")
            for issue in file_issues:
                print(f"  [{issue['type']}] Line {issue['line']}: {issue['message']}")
            print()
            
if __name__ == "__main__":
    run_surgical_audit()
