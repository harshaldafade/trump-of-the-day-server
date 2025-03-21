// userDb.ts - Database hook for user management

import { Pool } from 'pg';
// You could also use another database like MongoDB, MySQL, etc.

// Interface for user data
export interface User {
  id?: string;
  username: string;
  email: string;
  authProvider: string;
  providerId: string;
  createdAt?: Date;
  updatedAt?: Date;
}

// Database connection
const pool = new Pool({
  user: process.env.DB_USER || 'postgres',
  host: process.env.DB_HOST || 'localhost',
  database: process.env.DB_NAME || 'auth_db',
  password: process.env.DB_PASSWORD || 'password',
  port: parseInt(process.env.DB_PORT || '5432'),
});

// Initialize database - create tables if they don't exist
export const initDatabase = async () => {
  const client = await pool.connect();
  try {
    await client.query(`
      CREATE TABLE IF NOT EXISTS users (
        id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
        username VARCHAR(255) NOT NULL,
        email VARCHAR(255) UNIQUE,
        auth_provider VARCHAR(50) NOT NULL,
        provider_id VARCHAR(255) NOT NULL,
        created_at TIMESTAMP NOT NULL DEFAULT NOW(),
        updated_at TIMESTAMP NOT NULL DEFAULT NOW(),
        UNIQUE(auth_provider, provider_id)
      );
    `);
    console.log('Database initialized');
  } catch (error) {
    console.error('Error initializing database:', error);
    throw error;
  } finally {
    client.release();
  }
};

// Create a new user
export const createUser = async (userData: User): Promise<User> => {
  const { username, email, authProvider, providerId } = userData;
  
  const query = `
    INSERT INTO users (username, email, auth_provider, provider_id)
    VALUES ($1, $2, $3, $4)
    RETURNING id, username, email, auth_provider as "authProvider", provider_id as "providerId", created_at as "createdAt", updated_at as "updatedAt"
  `;
  
  const values = [username, email, authProvider, providerId];
  
  try {
    const result = await pool.query(query, values);
    return result.rows[0];
  } catch (error) {
    console.error('Error creating user:', error);
    throw error;
  }
};

// Find user by email
export const findUserByEmail = async (email: string): Promise<User | null> => {
  const query = `
    SELECT 
      id, 
      username, 
      email, 
      auth_provider as "authProvider", 
      provider_id as "providerId", 
      created_at as "createdAt", 
      updated_at as "updatedAt"
    FROM users
    WHERE email = $1
  `;
  
  try {
    const result = await pool.query(query, [email]);
    return result.rows[0] || null;
  } catch (error) {
    console.error('Error finding user by email:', error);
    throw error;
  }
};

// Find user by provider ID
export const findUserByProviderId = async (provider: string, providerId: string): Promise<User | null> => {
  const query = `
    SELECT 
      id, 
      username, 
      email, 
      auth_provider as "authProvider", 
      provider_id as "providerId", 
      created_at as "createdAt", 
      updated_at as "updatedAt"
    FROM users
    WHERE auth_provider = $1 AND provider_id = $2
  `;
  
  try {
    const result = await pool.query(query, [provider, providerId]);
    return result.rows[0] || null;
  } catch (error) {
    console.error('Error finding user by provider ID:', error);
    throw error;
  }
};

// Find user by ID
export const findUserById = async (id: string): Promise<User | null> => {
  const query = `
    SELECT 
      id, 
      username, 
      email, 
      auth_provider as "authProvider", 
      provider_id as "providerId", 
      created_at as "createdAt", 
      updated_at as "updatedAt"
    FROM users
    WHERE id = $1
  `;
  
  try {
    const result = await pool.query(query, [id]);
    return result.rows[0] || null;
  } catch (error) {
    console.error('Error finding user by ID:', error);
    throw error;
  }
};

// Update user
export const updateUser = async (id: string, userData: Partial<User>): Promise<User | null> => {
  const { username, email } = userData;
  
  const query = `
    UPDATE users
    SET 
      username = COALESCE($2, username),
      email = COALESCE($3, email),
      updated_at = NOW()
    WHERE id = $1
    RETURNING id, username, email, auth_provider as "authProvider", provider_id as "providerId", created_at as "createdAt", updated_at as "updatedAt"
  `;
  
  try {
    const result = await pool.query(query, [id, username, email]);
    return result.rows[0] || null;
  } catch (error) {
    console.error('Error updating user:', error);
    throw error;
  }
};

// Delete user
export const deleteUser = async (id: string): Promise<boolean> => {
  const query = 'DELETE FROM users WHERE id = $1';
  
  try {
    const result = await pool.query(query, [id]);
    return result.rowCount > 0;
  } catch (error) {
    console.error('Error deleting user:', error);
    throw error;
  }
};

// Get all users (with pagination)
export const getUsers = async (limit = 10, offset = 0): Promise<User[]> => {
  const query = `
    SELECT 
      id, 
      username, 
      email, 
      auth_provider as "authProvider", 
      provider_id as "providerId", 
      created_at as "createdAt", 
      updated_at as "updatedAt"
    FROM users
    ORDER BY created_at DESC
    LIMIT $1 OFFSET $2
  `;
  
  try {
    const result = await pool.query(query, [limit, offset]);
    return result.rows;
  } catch (error) {
    console.error('Error getting users:', error);
    throw error;
  }
};

// Count total users
export const countUsers = async (): Promise<number> => {
  const query = 'SELECT COUNT(*) FROM users';
  
  try {
    const result = await pool.query(query);
    return parseInt(result.rows[0].count);
  } catch (error) {
    console.error('Error counting users:', error);
    throw error;
  }
};