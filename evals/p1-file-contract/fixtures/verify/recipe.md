# Verify recipe

## Launch

`npm ci && npm run build`, then run the tool as `node dist/quill.js` with `QUILL_HOME` set to a
fresh temporary folder.

## Drive

Run the commands a criterion names. Read standard output, standard error, the exit code and the
files under `QUILL_HOME`.

## Clean up

Delete the temporary folder before any model-free run.

## Evidence

Each criterion's test is a Playwright test file under `e2e/` that spawns the CLI, renders its
terminal output to a page and screenshots that page. Run them model-free with
`npx playwright test e2e/ --reporter=json`.
