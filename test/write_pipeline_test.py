"""
Manual smoke test for the WRITE pipeline (intent → preview → execute).

Run from the project root:
    python test/write_pipeline_test.py

This talks to the REAL configured database (.env) and the REAL LLM
(GROQ_API_KEY) — it does not mock anything. It previews a couple of
write requests and prints the generated action + validation result.
It does NOT call execute() automatically, since that would actually
write to your database; execution is shown but commented out so you
can opt in deliberately.
"""
from intent.classifier import detect_intent
from core.write_agent import WriteAgent

SAMPLE_QUESTIONS = [
    "show customers",                          # expect READ
    "add article Laptop HP priced at 1000",    # expect WRITE -> INSERT
    "update stock of article ABC123 to 50",    # expect WRITE -> UPDATE
    "increase stock by 10",                    # expect WRITE -> unsupported (relative update, Phase 1 limitation)
]

agent = WriteAgent()

for question in SAMPLE_QUESTIONS:
    print("\n" + "=" * 70)
    print(f"Question: {question}")

    intent_result = detect_intent(question)
    print(f"Intent: {intent_result.intent.value} (matched: {intent_result.matched_keyword})")

    if intent_result.intent.value != "WRITE":
        print("(Would be routed to the existing READ pipeline — core.agent.ERPAgent.ask)")
        continue

    preview = agent.preview(question)
    print(f"requires_confirmation: {preview.requires_confirmation}")
    print(f"valid:   {preview.valid}")
    print(f"action:  {preview.action}")
    print(f"errors:  {preview.errors}")
    print(f"warnings:{preview.warnings}")
    print(f"error:   {preview.error}")

    # Uncomment to actually execute a validated action against the DB:
    # if preview.requires_confirmation and preview.valid:
    #     exec_result = agent.execute(preview.action)
    #     print(f"executed: {exec_result.executed}, rows_affected: {exec_result.rows_affected}, error: {exec_result.error}")
