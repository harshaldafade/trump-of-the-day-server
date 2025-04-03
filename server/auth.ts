// auth.ts
import express from 'express';
import Router from 'express';
import passport from 'passport';
import { Strategy as GoogleStrategy, Profile as GoogleProfile, VerifyCallback } from 'passport-google-oauth20';
import dotenv from 'dotenv';
import bcrypt from 'bcrypt';
import { supabase } from './supabaseClient';

dotenv.config();

// Fix: Correct router initialization
const router = Router();
console.log('🚀 Auth router initialized');

// Define User type
interface User {
  id: string;
  email: string;
  name: string;
  profile_picture?: string;
  password_hash?: string;
}

// ✅ Google OAuth Setup
if (!process.env.GOOGLE_CLIENT_ID || !process.env.GOOGLE_CLIENT_SECRET) {
  console.error('❌ Missing Google OAuth credentials in .env');
  process.exit(1);
}
console.log('✅ Google OAuth credentials found');

passport.use(
  new GoogleStrategy(
    {
      clientID: process.env.GOOGLE_CLIENT_ID,
      clientSecret: process.env.GOOGLE_CLIENT_SECRET,
      callbackURL: process.env.GOOGLE_CALLBACK_URL!,
      scope: ['profile', 'email'],
    },
    async (
      accessToken: string, 
      refreshToken: string, 
      profile: GoogleProfile, 
      done: VerifyCallback
    ) => {
      console.log('🔍 Google auth callback triggered for profile:', profile.id);
      try {
        // Use the correct structure based on the Profile interface
        const email = profile.emails?.[0]?.value;
        if (!email) {
          console.error('❌ No email found in Google profile');
          return done(new Error('No email in profile'));
        }
        console.log(`📧 Processing Google login for email: ${email}`);

        // ✅ Upsert user into Supabase directly
        console.log('🔄 Upserting user in Supabase');
        const { data, error } = await supabase
          .from('users')
          .upsert(
            {
              email,
              // Use the name from _json if available, or fallback to email username
              name: profile._json.name || email.split('@')[0],
              // Use picture URL from _json if available
              profile_picture: profile._json.picture || null,
            },
            { onConflict: 'email' }
          )
          .select();

        if (error || !data || !data[0]) {
          console.error("❌ Supabase user upsert error:", error?.message);
          return done(error || new Error("User upsert failed"));
        }

        const user = data[0] as User;
        console.log(`✅ User ${user.id} upserted successfully`);
        return done(null, user);
      } catch (err) {
        console.error('❌ Exception in Google auth callback:', err);
        return done(err as Error);
      }
    }
  )
);

// ✅ Passport Sessions
passport.serializeUser((user: User, done) => {
  console.log("🔒 Serializing user:", user.id, user.email);
  done(null, user.id);
});

passport.deserializeUser(async (id: string, done) => {
  console.log("🔓 Deserializing user with ID:", id);
  try {
    console.log(`🔍 Looking up user ${id} in Supabase`);
    const { data: users, error } = await supabase
      .from('users')
      .select('*')
      .eq('id', id)
      .limit(1);

    if (error) {
      console.error("❌ Supabase error during user deserialization:", error.message);
      return done(error, null);
    }
    
    if (!users || users.length === 0) {
      console.error("⚠️ User not found during deserialization");
      return done(null, null);
    }

    console.log(`✅ User ${id} deserialized successfully`);
    done(null, users[0] as User);
  } catch (err) {
    console.error('❌ Exception in deserializeUser:', err);
    done(err, null);
  }
});

// ✅ Auth Routes
router.get('/google', (req, res, next) => {
  console.log('📣 Google auth route accessed');
  next();
}, passport.authenticate('google', { scope: ['profile', 'email'] }));

router.get('/google/callback', (req, res, next) => {
  console.log('📣 Google auth callback route accessed');
  next();
}, 
  passport.authenticate('google', {
    failureRedirect: process.env.CLIENT_URL + '/login',
    failureMessage: true
  }),
  (req, res) => {
    console.log('✅ Google authentication successful, redirecting to client');
    res.redirect(process.env.CLIENT_URL!);
  }
);

router.get('/user', (req, res) => {
  console.log('📣 User info route accessed, authenticated:', req.isAuthenticated?.());
  if (req.isAuthenticated?.()) {
    console.log(`✅ Returning user info for ${(req.user as User).id}`);
    res.json(req.user);
  } else {
    console.log('❌ User not authenticated');
    res.status(401).json({ error: 'Not authenticated' });
  }
});

router.get('/logout', (req, res) => {
  console.log('📣 Logout route accessed');
  req.logout((err) => {
    if (err) {
      console.error('❌ Logout error:', err);
      return res.status(500).json({ error: 'Logout failed' });
    }
    console.log('🔄 Destroying session');
    req.session.destroy((err) => {
      if (err) {
        console.error('❌ Session destruction error:', err);
        return res.status(500).json({ error: 'Session destruction failed' });
      }
      console.log('✅ Session destroyed, clearing cookie and redirecting');
      res.clearCookie('connect.sid');
      res.redirect(process.env.CLIENT_URL!);
    });
  });
});

// ✅ Email/Password Login
router.post('/login', async (req, res) => {
  console.log('📣 Login attempt for email:', req.body.email);
  const { email, password } = req.body;

  if (!email || !password) {
    console.log('❌ Login failed: Missing email or password');
    return res.status(400).json({ error: 'Email and password required' });
  }

  try {
    console.log(`🔍 Looking up user with email: ${email}`);
    const { data: users, error } = await supabase
      .from('users')
      .select('*')
      .eq('email', email)
      .limit(1);

    if (error) {
      console.error('❌ Supabase error during login:', error.message);
      return res.status(500).json({ error: 'Server error during login' });
    }

    if (!users || users.length === 0) {
      console.log(`❌ Login failed: No user found with email ${email}`);
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    const user = users[0] as User;
    console.log(`✅ User found: ${user.id}`);

    if (!user.password_hash) {
      console.log(`❌ Login failed: User ${user.id} has no password (social login only)`);
      return res.status(401).json({ error: 'Use Google login' });
    }

    console.log('🔐 Verifying password');
    const match = await bcrypt.compare(password, user.password_hash);
    if (!match) {
      console.log(`❌ Login failed: Invalid password for user ${user.id}`);
      return res.status(401).json({ error: 'Invalid credentials' });
    }

    console.log(`✅ Password verified for user ${user.id}, logging in`);
    req.login(user, (err) => {
      if (err) {
        console.error('❌ Login session error:', err);
        return res.status(500).json({ error: 'Login error' });
      }
      console.log(`🎉 Login successful for user ${user.id}`);
      return res.json({ message: 'Login successful', user });
    });
  } catch (err) {
    console.error('❌ Exception during login:', err);
    return res.status(500).json({ error: 'Server error during login' });
  }
});

// ✅ Signup Route
router.post('/signup', async (req, res) => {
  console.log('📣 Signup attempt for email:', req.body.email);
  const { email, name, password } = req.body;
  
  if (!email || !password || !name) {
    console.log('❌ Signup failed: Missing required fields');
    return res.status(400).json({ error: 'Missing required fields' });
  }

  try {
    console.log('🔐 Hashing password');
    const password_hash = await bcrypt.hash(password, 10);

    console.log(`🔄 Creating new user with email: ${email}`);
    const { data, error } = await supabase
      .from('users')
      .insert([{ email, name, password_hash }])
      .select();

    if (error) {
      if (error.message.includes('duplicate key')) {
        console.log(`❌ Signup failed: Email ${email} already exists`);
        return res.status(400).json({ error: 'Email already exists' });
      }
      console.error('❌ Supabase error during signup:', error.message);
      return res.status(500).json({ error: 'Signup failed' });
    }

    if (!data || !data[0]) {
      console.error('❌ Signup failed: No user returned after insert');
      return res.status(500).json({ error: 'Signup failed (no user returned)' });
    }

    console.log(`🎉 Signup successful for user ${data[0].id}`);
    return res.status(200).json({ message: 'Signup successful', user: data[0] });
  } catch (err) {
    console.error('❌ Exception during signup:', err);
    return res.status(500).json({ error: 'Server error during signup' });
  }
});

// ✅ All Users
router.get('/users', async (_req, res) => {
  console.log('📣 Fetching all users');
  try {
    console.log('🔍 Querying users from Supabase');
    const { data: users, error } = await supabase
      .from('users')
      .select('id, email, name, profile_picture');
    
    if (error) {
      console.error('❌ Supabase error fetching users:', error.message);
      throw error;
    }
    
    console.log(`✅ Successfully fetched ${users?.length || 0} users`);
    res.json(users);
  } catch (err) {
    console.error('❌ Exception while fetching users:', err);
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

console.log('✅ Auth routes loaded successfully');

export = router;