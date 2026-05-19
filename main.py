"""
ERP AI SQL Assistant — main entry point.
Run:  python main.py
"""
import sys
from core.agent import ERPAgent
from utils.logger import get_logger

logger = get_logger("main")


def main():
    print("\n" + "=" * 65)
    print("  ERP AI SQL Assistant  |  Sage 100 / SQL Server")
    print("=" * 65)
    print("Type your question in natural language.")
    print("Commands:  :schema   :rebuild   :quit\n")

    agent = ERPAgent()

    
    while True:
        try:
            question = input("You: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            sys.exit(0)

        if not question:
            continue

        
        if question == ":quit":
            print("Goodbye.")
            sys.exit(0)

        if question == ":rebuild":
            print("Rebuilding schema index…")
            agent.rebuild_schema_index()
            print("Done.")
            continue

        if question == ":schema":
            tables = agent.list_indexed_tables()
            print(f"\nIndexed tables ({len(tables)}):")
            for t in tables:
                print(f"  {t}")
            print()
            continue

        
        result = agent.ask(question)

        print(f"\nSQL:   {result['sql']}")

        if result["error"]:
            print(f"Error: {result['error']}\n")
            continue

        data = result["data"]
        if not data or not data["rows"]:
            print("No rows returned.\n")
            continue

        
        cols = data["columns"]
        rows = data["rows"]
        col_w = max(18, max(len(str(c)) for c in cols) + 2)

        header = " | ".join(str(c).ljust(col_w) for c in cols)
        print("\n" + header)
        print("-" * len(header))
        for row in rows[:50]:         
            print(" | ".join(str(v).ljust(col_w) for v in row))
        if len(rows) > 50:
            print(f"  … {len(rows) - 50} more rows not shown")
        print(f"\n({len(rows)} row(s))\n")


if __name__ == "__main__":
    main()