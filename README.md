# Server for trumpoftheday.com
 Backend, scraper, ranking algorithm

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

## Features running on server
<ul>
<li>User authorization
<li>News Scraping
<li>Ranking Algorithm
<li>AI Summarize news
<li>Upvotes/Downvotes/Comments
</ul>