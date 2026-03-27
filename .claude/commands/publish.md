Run the ADAS weekly report production pipeline and push to GitHub Pages.

Execute the following steps:

1. Run `bash scripts/run_and_push.sh` from the project root `/Users/qirui/momenta/ADAS_weekly/` with a 600-second timeout. Stream the output so the user can see progress.

2. If the script fails:
   - If the error mentions `LLM_API_KEY`: tell the user to check `.env`
   - If the error mentions a network/connection issue: tell the user to check they're on Momenta VPN
   - Otherwise: show the error and ask the user how to proceed

3. If the script succeeds with "Done. Report pushed.":
   Report to the user: pipeline complete, report published at https://mibumonk.github.io/adas-weekly/

Note: The pipeline requires Momenta VPN (LLM gateway is internal-only) and takes ~3 minutes to complete.
