const axios = require('axios')
const express = require('express')
const bcrypt = require('bcrypt')
const session = require('express-session')
const flash = require('express-flash')
const passport = require('passport')
const db = require('../database/db')
const initializePassport = require('./passportConfig')

const app = express()

// middleware
initializePassport(passport)

app.set('view engine', 'ejs')

app.use(express.json())
app.use(express.urlencoded({ extended: true}))
app.use(session({
    secret: 'secret',
    resave: false, 
    saveUninitialized: false
}))
app.use(flash())
app.use(passport.initialize())
app.use(passport.session())


// index
app.get("/", checkNotAuthenticated, (req,res) => {
    res.render("index")
})

//posts route

app.get("/posts",checkNotAuthenticated, async (req,res) => {
    try {

        const result = await db.query('SELECT * FROM posts');
        res.render('posts', {data: result.rows})

      } catch (err) {

        console.error(err);
        res.status(500).send('Internal Server Error');

      }
})

app.get("/posts/new", checkNotAuthenticated, (req,res) => {
    res.render("posts/new")
})

app.post("/posts", checkNotAuthenticated, async (req,res) => {

    let results;

    if (req.body.urltext.length > 0) {
        try {
            const response = await axios.get(req.body.urltext, {headers: {Cookie: req.headers.cookie, "User-Agent": req.headers["user-agent"]} ,validateStatus: false, withCredentials: true });

            console.log("SSRF request sent:", req.body.urltext);
            console.log("Response status:", response.status);

            await db.query(
                `INSERT INTO posts (fullname, title, postmessage) VALUES ($1, $2, $3);`,
                [req.body.fullName, req.body.title, response.data]
            );

            results = await db.query(
                `SELECT post_id FROM posts WHERE fullname = $1 AND title = $2 AND postmessage = $3;`,
                [req.body.fullName, req.body.title, response.data]
            );
        } catch (error) {
            console.error('Request error:', error);
            return res.status(500).send("Error fetching URL");
        }
    } else {
        await db.query(
            `INSERT INTO posts (fullname, title, postmessage) VALUES ($1, $2, $3);`,
            [req.body.fullName, req.body.title, req.body.message]
        );

        results = await db.query(
            `SELECT post_id FROM posts WHERE fullname = $1 AND title = $2 AND postmessage = $3;`,
            [req.body.fullName, req.body.title, req.body.message]
        );
    }

    if (results && results.rows.length > 0) {
        res.redirect(`/posts/${results.rows[0].post_id}`);
    } else {
        res.status(500).send("Error retrieving post ID");
    }

})

app.get('/posts/:id', checkNotAuthenticated, async (req,res) => {

    try {

        const result = await db.query(`SELECT * FROM posts WHERE post_id=${req.params.id}`);

        console.log(result.rows[0].post_id)
        res.render('posts/post', {post_id: result.rows[0].post_id, title: result.rows[0].title, fullName: result.rows[0].fullname, text: result.rows[0].postmessage})

      } catch (err) {

        console.error(err);
        res.status(500).send('Internal Server Error');

      }
})

app.get("/posts/:id/edit", checkNotAuthenticated, async (req,res) => {

    const result = await db.query(`SELECT * FROM posts WHERE post_id=${req.params.id}`);

    res.render("posts/edit", {post_id: req.params.id, title: result.rows[0].title, fullName: result.rows[0].fullname, message: result.rows[0].postmessage})
})

app.post('/posts/:id/edit', checkNotAuthenticated, async (req,res) => {

    try {

        let { fullName, title, message} = req.body

        console.log(fullName)
        console.log(title)
        console.log(message)

        await db.query(`UPDATE posts SET fullname = '${fullName}', title = '${title}', postmessage = '${message}' WHERE post_id = '${req.params.id}';`)

        res.redirect(`/posts/${req.params.id}`)

      } catch (err) {

        console.error(err);
        res.status(500).send('Internal Server Error');

      }
})

app.get('/posts/:id/delete', checkAdmin, checkNotAuthenticated, async (req,res) => {

    try {

        await db.query(`DELETE FROM posts WHERE post_id = '${req.params.id}';`)

        console.log("deleted")

        res.send('<script>alert("Successfully deleted post"); window.location.href = "/posts"; </script>')

      } catch (err) {

        console.error(err);
        res.status(500).send('Internal Server Error');

      }
})


//users rout

app.get('/users/register', checkAuthenticated, (req,res) => {
    res.render("register")
})

app.get('/users/login', checkAuthenticated, (req,res) => {
    res.render("login")
})

app.get('/users/dashboard', checkNotAuthenticated, (req,res) => {
    res.render("dashboard", {user : req.user.name})
})

app.get('/users/logout', (req,res) => {
    req.logout( (err) => {
        if (err) {
            console.log(err);
        } else {
            req.flash("success_msg", "You have logged out")
            res.redirect("/users/login")
        }
    });
})

app.post('/users/register', async (req,res) => {
    let { name, email, password, password2} = req.body

    console.log({
        name,
        email,
        password,
        password2
    })

    let errors = [];

    if (!name || !email || !password || !password2){
        errors.push({message: "Please enter all fields"})
    }

    if (password.length < 6){
        errors.push({message: "Message should be atleast 6 characters"})
    }

    if (password != password2){
        errors.push({message: "Passwords do not match"})
    }

    if(errors.length > 0){
        res.render('register', {errors})
    }
    else {

        let hashedPassword = await bcrypt.hash(password, 10)
        console.log(hashedPassword)
        
        db.query(`SELECT * FROM users WHERE email = '${email}';`, (err, results) => {
            if (err) {
                throw err
            }
            console.log(results.rows)

            if (results.rows.length > 0){
                errors.push({message: "Email already registered"})
                res.render('register', {errors})
            }
            else {
                db.query(`INSERT INTO users (name, email, password) 
                    VALUES ('${name}', '${email}', '${hashedPassword}')
                    RETURNING id, password;`, (err, results) => {
                        if (err) {
                            throw err
                        }

                        console.log(results.rows)

                        req.flash('success_msg', "You are now registered. Please log in")
                        res.redirect("/users/login")
                    })
            }
        })
    }
})

app.post("/users/login", passport.authenticate('local', {
    successRedirect: '/users/dashboard',
    failureRedirect: "/users/login",
    failureFlash: true
}))

function checkAuthenticated(req, res, next) {
    if (req.isAuthenticated()){
        return res.redirect('/users/dashboard')
    }
    else {
        next()
    }
}

function checkNotAuthenticated(req, res, next) {
    if (req.isAuthenticated()) {
        return next()
    }
    else {
        res.redirect('/users/login')
    }
}

function checkAdmin(req,res, next) {
    const parseIp = (req) =>
        req.headers['x-forwarded-for']?.split(',').shift()
        || req.socket?.remoteAddress
    
    console.log(parseIp(req))
     // Allow only real internal requests
    if (parseIp(req) == "127.0.0.1") {
        return next();
    } else {
        res.sendStatus(403);
    }
}

app.listen(3000, '0.0.0.0')


