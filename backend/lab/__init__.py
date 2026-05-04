"""Lab module — experimental features that compare against / extend the main pipeline.

Design contract
---------------
* Lab features NEVER mutate the global pipeline_manager. They borrow strategy
  classes from the registry but build their own pipeline graphs on demand.
* All endpoints under /api/lab/* degrade gracefully: missing layout, missing
  sklearn, dead worker, empty index — each returns a structured response with
  Chinese error message rather than a 500.
* Code paths and config knobs are isolated under backend/lab/* so the main
  Pipeline class stays unaffected and the demo's main flow keeps working
  even if a lab module crashes at import time.
"""
