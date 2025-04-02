// auth.ts
const express = require('express');
const router = express.Router();

const passport = require('passport');
const GoogleStrategy = require('passport-google-oauth20').Strategy;
const dotenv = require('dotenv');
const { findUserById, createUser, findUserByEmail, getAllUsers } = require('./userDb');
const { supabase } = require('./supabaseClient');
const bcrypt = require('bcrypt');
const { User } = require('./userDb');
//const FacebookStrategy = require('passport-facebook').Strategy;


dotenv.config();

const app = express();

// Facebook OAuth
// passport.use(new FacebookStrategy(
//   {
//     clientID: process.env.FACEBOOK_CLIENT_ID,
//     clientSecret: process.env.FACEBOOK_CLIENT_SECRET,
//     callbackURL: process.env.FACEBOOK_CALLBACK_URL,
//     profileFields: ['id', 'emails', 'name', 'picture.type(large)'],
//   },
//   async (_accessToken, _refreshToken, profile, done) => {
//     try {
//       const email = profile.emails?.[0]?.value;
//       const name = `${profile.name.givenName} ${profile.name.familyName}`;
//       const avatar = profile.photos?.[0]?.value;

//       if (!email) return done(new Error('No email in Facebook profile'), null);

//       let user = await findUserByEmail(email);
//       if (!user) {
//         user = await createUser({
//           id: Date.now().toString(),
//           email,
//           name,
//           avatar,
//         });
//       }

//       await supabase
//         .from('users')
//         .upsert({
//           email,
//           name,
//           profile_picture: avatar,
//         }, { onConflict: 'email' });

//       return done(null, user);
//     } catch (err) {
//       return done(err, null);
//     }
//   }
// ));


// ✅ Google OAuth Setup
if (!process.env.GOOGLE_CLIENT_ID || !process.env.GOOGLE_CLIENT_SECRET) {
  console.error('❌ Missing Google OAuth credentials in .env');
  process.exit(1);
}

passport.use(new GoogleStrategy(
  {
    clientID: process.env.GOOGLE_CLIENT_ID,
    clientSecret: process.env.GOOGLE_CLIENT_SECRET,
    callbackURL: process.env.GOOGLE_CALLBACK_URL,
    scope: ['profile', 'email'],
  },
  async (_accessToken, _refreshToken, profile, done) => {
    try {
      const email = profile.emails?.[0]?.value;
      if (!email) return done(new Error('No email in profile'), null);

      // ✅ Upsert user into Supabase directly
      const { data, error } = await supabase
        .from('users')
        .upsert({
          email,
          name: profile.displayName,
          profile_picture: profile.photos?.[0]?.value,
        }, { onConflict: 'email' })
        .select();

      if (error || !data || !data[0]) {
        console.error("❌ Supabase user upsert error:", error?.message);
        return done(error || new Error("User upsert failed"), null);
      }

      const user = data[0]; // ✅ user with valid Supabase ID

      return done(null, user);
    } catch (err) {
      return done(err, null);
    }
  }
));


// ✅ Passport Sessions
passport.serializeUser((user, done) => {
  console.log("🔒 Serializing user:", user);
  done(null, user.id); // now a real Supabase UUID
});



passport.deserializeUser(async (id, done) => {
  console.log("🔓 Deserializing user with ID:", id); // Debug
  try {
    const { data: users, error } = await supabase
      .from('users')
      .select('*')
      .eq('id', id)
      .limit(1);

    if (error || !users || users.length === 0) {
      console.error("User not found during deserialization");
      return done(null, null);
    }

    done(null, users[0]);
  } catch (err) {
    done(err, null);
  }
});


// ✅ Auth Routes
router.get('/google', passport.authenticate('google', { scope: ['profile', 'email'] }));

router.get('/google/callback',
  passport.authenticate('google', {
    failureRedirect: process.env.CLIENT_URL + '/login',
  }),
  (req, res) => {
    res.redirect(process.env.CLIENT_URL);
  }
);

// ✅ Facebook OAuth Routes
router.get('/facebook', passport.authenticate('facebook', { scope: ['email'] }));

router.get('/facebook/callback',
  passport.authenticate('facebook', {
    failureRedirect: process.env.CLIENT_URL + '/login',
  }),
  (req, res) => {
    res.redirect(process.env.CLIENT_URL);
  }
);


router.get('/user', (req, res) => {
  if (req.isAuthenticated?.()) {
    res.json(req.user);
  } else {
    res.status(401).json({ error: 'Not authenticated' });
  }
});

router.get('/logout', (req, res) => {
  req.logout(() => {
    req.session.destroy(() => {
      res.clearCookie('connect.sid');
      res.redirect(process.env.CLIENT_URL);
    });
  });
});

// ✅ Email/Password Login
router.post('/login', async (req, res) => {
  const { email, password } = req.body;

  const { data: users, error } = await supabase
    .from('users')
    .select('*')
    .eq('email', email)
    .limit(1);

  if (error || !users || users.length === 0) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  const user = users[0];

  if (!user.password_hash) {
    return res.status(401).json({ error: 'Use Google or Facebook login' });
  }

  const match = await bcrypt.compare(password, user.password_hash);
  if (!match) {
    return res.status(401).json({ error: 'Invalid credentials' });
  }

  req.login(user, (err) => {
    if (err) return res.status(500).json({ error: 'Login error' });
    return res.json({ message: 'Login successful', user });
  });
});

// ✅ Signup Route
router.post('/signup', async (req, res) => {
  const { email, name, password } = req.body;
  if (!email || !password || !name) {
    return res.status(400).json({ error: 'Missing fields' });
  }

  const password_hash = await bcrypt.hash(password, 10);

  const { data, error } = await supabase
    .from('users')
    .insert([{ email, name, password_hash }])
    .select();

  if (error) {
    if (error.message.includes('duplicate key')) {
      return res.status(400).json({ error: 'Email already exists' });
    }
    return res.status(500).json({ error: 'Signup failed' });
  }

  if (!data || !data[0]) {
    return res.status(500).json({ error: 'Signup failed (no user returned)' });
  }

  return res.status(200).json({ message: 'Signup successful', user: data[0] });
});

// ✅ All Users
router.get('/users', async (_req, res) => {
  try {
    const users = await getAllUsers();
    res.json(users);
  } catch (err) {
    res.status(500).json({ error: 'Failed to fetch users' });
  }
});

export = router;
