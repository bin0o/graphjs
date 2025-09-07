const express = require('express');
const app = express();
const PORT = 3000;

// ---------- GLOBAL MIDDLEWARES ----------
function logger(req, res, next) {
  console.log(`[GLOBAL] ${req.method} ${req.url}`);
  next();
}

function auth(req, res, next) {
  console.log('[GLOBAL] Checking authentication...');
  next();
}

// Register global middlewares
app.use(logger);
app.use(auth);

// ---------- ROUTE MIDDLEWARES ----------
function blogAuth(req, res, next) {
  console.log('[BLOG] Blog-specific auth');
  next();
}

function blogLogger(req, res, next) {
  console.log('[BLOG] Blog-specific logger');
  next();
}

function userAuth(req, res, next) {
  console.log('[BLOG/USER] User-specific auth');
  next();
}

// Attach route-specific middlewares
app.use('/blog', blogAuth, blogLogger);   // applies to /blog and any subroutes
app.use('/blog/user', userAuth);          // applies only to /blog/user/*

// ---------- ROUTES ----------
app.get('/', rip, (req, res) => {
  res.send('Home page');
});

app.get('/blog', (req, res) => {
  res.send('Blog main page');
});

app.get('/blog/user', blogginatorForUser,(req, res) => {
  res.send('Blog user page');
});

app.get('/blog/list', blogginatorForList, (req, res) => {
  res.send('Blog list page');
});

// ---------- START SERVER ----------
app.listen(PORT, () => {
  console.log(`Server running at http://localhost:${PORT}`);
});
