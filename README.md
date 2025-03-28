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