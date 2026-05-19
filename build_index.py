import sys
from schema.indexer import build_index

force = "--force" in sys.argv

print("Building schema index…  (this may take 1-3 minutes on first run)")
build_index(force=force)
print("Done. Run main.py to start the assistant.")