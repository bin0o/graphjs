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

function index(method, req, res) {

    if (method === "get") {
        logger(req, res, () => auth(req, res, () => rip(req, res, () => index_get(req, res))));
    }

    function index_get(req, res) {
          res.send('Home page');
    }

}

function blog(method, req, res) {

    if (method === "get") {
        logger(req, res, () => auth(req, res, () => blogAuth(req, res, () => blogLogger(req, res, () => blog_get(req, res)))));
    }

    function blog_get(req, res) {
          res.send('Blog main page');
    }

}

function blog_user(method, req, res) {

    if (method === "get") {
        logger(req, res, () => auth(req, res, () => blogAuth(req, res, () => blogLogger(req, res, () => userAuth(req, res, () => blogginatorForUser(req, res, () => blog_user_get(req, res)))))));
    }

    function blog_user_get(req, res) {
          res.send('Blog user page');
    }

}

function blog_list(method, req, res) {

    if (method === "get") {
        logger(req, res, () => auth(req, res, () => blogAuth(req, res, () => blogLogger(req, res, () => blogginatorForList(req, res, () => blog_list_get(req, res))))));
    }

    function blog_list_get(req, res) {
          res.send('Blog list page');
    }

}


// ---------- START SERVER ----------
module.exports = {index, blog, blog_user, blog_list, app}