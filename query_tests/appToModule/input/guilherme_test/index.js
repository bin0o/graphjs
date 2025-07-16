const express = requre('express')
let g = require('./g.js');


app.use(express.json())
app.use(express.urlencoded({ extended: true}))


app.get("/",(req, res) => {
    g(req);
})