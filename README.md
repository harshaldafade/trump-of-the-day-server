# Scraper for trumpoftheday.com
## Install

1. Create and activate virtual environment
```bash
$ python -m venv env
$ source env/bin/activate
```
2. Install dependencies
```bash
$ pip install -r requirements.txt
```

3. Create an .env file for supabase secrets
```
# Supabase connection details
SUPABASE_URL=<your supabase url>
SUPABASE_KEY=<your supabase key>
```

# Start Server

```bash
$ npx ts-node server.ts
```