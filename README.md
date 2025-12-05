# Server for trumpoftheday.com
 Backend, scraper, ranking algorithm
 
![Docker Image Build](https://img.shields.io/github/actions/workflow/status/harshaldafade/trump-of-the-day-server/build-push.yml?label=Docker%20Image%20Build)
![Daily News Update](https://img.shields.io/github/actions/workflow/status/harshaldafade/trump-of-the-day-server/daily-run.yml?label=Daily%20News%20Update)


## Install Scraper and Ranking algorithm
1. Create and activate virtual environment
```bash
$ python -m venv env
$ source env/bin/activate
`` 
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

## Install and Start Server
The server is created using express js and currently uses [Supabase](https://supabase.com/). In recent future, we plan to move to an [EC2 Instance](https://aws.amazon.com/ec2/).

Install server
```bash
$ cd server
$ npm install
$ touch .env
```
Create env with following variables in server
```
SUPABASE_URL=
SUPABASE_KEY=

GOOGLE_CLIENT_ID=
GOOGLE_CLIENT_SECRET=



GOOGLE_CALLBACK_URL=http://localhost:3001/api/auth/google/callback
CLIENT_URL=http://localhost:3000

PORT=3001

SECRET=
NODE_ENV=development  # for local development or 'production' for deploying

```
Run server
```bash
$ npx ts-node server.ts
```
## Run insert script
The `insert_news` script fetches and stores news articles in Supabase
for a given date range.

### Running the script

You can run the script directly from the command line:

``` bash
python insert_news.py [start_date] [end_date]
```

#### Arguments

-   `start_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   You can also pass `today` or `t` to fetch news for the current
        date.\
    -   If not provided, the utility will use its default logic.
-   `end_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   If not provided, the utility will only fetch news for the
        `start_date`.

#### Examples

1.  Fetch news for **today**:

``` bash
python insert_news.py today
```

2.  Fetch news for a specific date:

``` bash
python insert_news.py 2025-09-10
```

3.  Fetch news for a date range:

``` bash
python insert_news.py 2025-09-01 2025-09-05
```

### Output

-   The script prints progress logs while fetching and saving articles.\
-   At the end, it shows the total number of articles saved.

Example output:

    🔍 Processing news from 2025-09-01 to 2025-09-05
    📊 Total articles saved: 120

If no news is fetched, you will see:

    ⚠️ No news fetched for 2025-09-10.

If there is an insertion error, you will see:

    ❌ Error inserting data for 2025-09-03: <error_message>

## Run delete script
The `delete_news` script deletes news articles from Supabase for a
given date range.

### Running the script

You can run the script directly from the command line:

``` bash
python delete_news.py [start_date] [end_date] [--force]
```

#### Arguments

-   `start_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   You can also pass `today` or `t` to delete news for the current
        date.\
    -   If not provided, the utility will use its default logic.
-   `end_date` (optional):
    -   Accepts `YYYY-MM-DD` format.\
    -   If not provided, the utility will only delete news for the
        `start_date`.
-   `--force`, `-f`, `yes`, or `y` (optional):
    -   Skips the confirmation prompt and directly deletes the articles.

#### Examples

1.  Delete news for **today** (with confirmation prompt):

``` bash
python delete_news.py today
```

2.  Delete news for a specific date (without confirmation prompt):

``` bash
python delete_news.py 2025-09-10 --force
```

3.  Delete news for a date range:

``` bash
python delete_news.py 2025-09-01 2025-09-05
```

#### Confirmation Prompt

If `--force` is not passed, you will see a prompt:

    ⚠️ You are about to delete all news articles from 2025-09-01 to 2025-09-05
    Are you sure you want to proceed? (yes/no): 

Type `yes` to proceed, or anything else to cancel.

### Output

-   The script prints logs while deleting articles.\
-   At the end, it shows the total number of articles deleted.

Example output:

    🗑️ Deleting news from 2025-09-01 to 2025-09-05
    📊 Total articles deleted: 45

If no news is found for a date, you will see:

    ℹ️ No news articles found for 2025-09-10

If there is a deletion error, you will see:

    ❌ Error deleting data for 2025-09-03: <error_message>

## Features running on server
<ul>
<li>User authorization
<li>News Scraping
<li>Ranking Algorithm
<li>AI Summarize news
<li>Upvotes/Downvotes/Comments
</ul>
