import os
from pathlib import Path

def scan_csharp_file(filepath: Path):
    issues = []
    try:
        content = filepath.read_text(encoding="utf-8")
        lines = content.splitlines()
        
        for idx, line in enumerate(lines):
            line_no = idx + 1
            # Check for event subscriptions without -=
            if "+=" in line and ("EventHandler" in line or "PropertyChanged" in line or "CollectionChanged" in line):
                # Verify if there is a corresponding -= in the file
                event_name = line.split("+=")[0].strip().split()[-1]
                if "-=" not in content:
                    issues.append({
                        "type": "MEMORY_LEAK",
                        "message": f"Event subscription '{event_name} += ...' without corresponding '-=' in same file. High risk of memory retention in WPF Views.",
                        "line": line_no
                    })
            # Check for async void (classic WPF anti-pattern causing unhandled crashes)
            if "async void" in line:
                # Check if it's an event handler (which is allowed)
                if not ("_Click" in line or "OnUnloaded" in line or "OnLoaded" in line or "Command" in line or "sender," in line or "EventArgs" in line):
                    issues.append({
                        "type": "CRASH_RISK",
                        "message": "Async void method detected. Risk of unhandled exception crashes. Use async Task instead.",
                        "line": line_no
                    })
            # Check for missing DI ViewModel scope resolution
            if "GetRequiredService" in line and "ViewModel" in line:
                issues.append({
                    "type": "DI_LIFECYCLE",
                    "message": "ViewModel resolved directly from root IServiceProvider instead of scoped scope. Potential lifecycle leak.",
                    "line": line_no
                })
    except Exception as e:
        issues.append({
            "type": "ERROR",
            "message": f"Failed to parse file: {e}",
            "line": 0
        })
    return issues

def run_deep_audit():
    root_dir = Path("C:/Users/david/Documents/Pb_studio_AMD_version/PBStudio.UI")
    csharp_files = list(root_dir.glob("**/*.cs"))
    
    print(f"Starting deep concurrency and memory leak audit over {len(csharp_files)} C# files...")
    all_issues = {}
    
    for f in csharp_files:
        rel_path = f.relative_to(root_dir)
        issues = scan_csharp_file(f)
        if issues:
            all_issues[str(rel_path)] = issues
            
    print("\n--- DEEP C# AUDIT REPORT ---\n")
    if not all_issues:
        print("Success: 0 memory leak or crash risks found across WPF files!")
    else:
        for path, file_issues in all_issues.items():
            print(f"File: {path}")
            for issue in file_issues:
                print(f"  [{issue['type']}] Line {issue['line']}: {issue['message']}")
            print()

if __name__ == "__main__":
    run_deep_audit()
