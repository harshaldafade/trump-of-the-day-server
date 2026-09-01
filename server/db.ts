// server/db.ts
import { Pool } from 'pg';
import dotenv from 'dotenv';
dotenv.config();

const databaseUrl = process.env.DATABASE_URL;

if (!databaseUrl) {
  throw new Error("❌ Missing DATABASE_URL in environment");
}

// Neon requires TLS; rejectUnauthorized: false matches the standard node-postgres
// setup for Neon's connection strings (they don't ship a locally-trusted CA chain).
export const pool = new Pool({
  connectionString: databaseUrl,
  ssl: { rejectUnauthorized: false },
});
