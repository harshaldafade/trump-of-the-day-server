// server/supabaseClient.ts
import { createClient } from '@supabase/supabase-js';
import dotenv from 'dotenv';
dotenv.config();

const supabaseUrl = process.env.SUPABASE_URL;
const supabaseKey = process.env.SUPABASE_KEY;

if (!supabaseUrl || !supabaseKey) {
  throw new Error("❌ Missing Supabase URL or Key in environment");
}

export const supabase = createClient(supabaseUrl, supabaseKey);
