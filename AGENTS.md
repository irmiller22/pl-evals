# Agent safety rules

- Never open, read, search, print, or include the contents of `.env` or any `.env.*` file.
- `.env.example` is safe to read because it contains placeholders only.
- Do not run commands that expose environment-file contents, including `cat`, `sed`, `rg`, `grep`, or equivalent against `.env` files.
- Use documented variable names and `.env.example` when discussing configuration. Treat real credentials as unavailable.
